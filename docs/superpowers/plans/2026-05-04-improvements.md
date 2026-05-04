# genpwd-sh Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five independent issues: correct passphrase complexity labels, expand the SYMBOLS pool, fix the share button URL protocol, remove the Font Awesome CDN dependency, and gitignore internal plan docs.

**Architecture:** Single-file Flask app (`main.py`) and one Jinja2 template (`templates/index.html`). Tests in `tests/test_main.py`. All five tasks are independent and can be executed in any order.

**Tech Stack:** Python 3.13, Flask 3.x, Flask-Limiter, pytest, uv

---

### Task 1: Entropy-based complexity labels for passphrases

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Background:** `complexity_score()` uses character-based heuristics (uppercase, digits, symbols, length ≥ 12). Passphrases always have mixed case and are typically long, so they almost always score "Good" regardless of actual strength. A 4-word passphrase (~52 bits) should be "Fair", not "Good". We add `passphrase_complexity_label()` that maps entropy thresholds to labels, and update `build_response()` with an optional `passphrase` flag.

Thresholds:
| Entropy (bits) | Label  |
|----------------|--------|
| < 40           | Weak   |
| ≥ 40 and < 60  | Fair   |
| ≥ 60 and < 80  | Good   |
| ≥ 80           | Strong |

- [ ] **Step 1: Write failing tests**

In `tests/test_main.py`, update the top import line from:

```python
from main import app, generate_passphrase, load_eff_wordlist, WORDLIST, SYMBOLS, limiter
```

to:

```python
from main import app, generate_passphrase, load_eff_wordlist, WORDLIST, SYMBOLS, limiter, passphrase_complexity_label
```

Then add these tests after the existing `test_passphrase_*` block:

```python
def test_passphrase_complexity_label_weak():
    assert passphrase_complexity_label(25.0) == "Weak"
    assert passphrase_complexity_label(39.9) == "Weak"


def test_passphrase_complexity_label_fair():
    assert passphrase_complexity_label(40.0) == "Fair"
    assert passphrase_complexity_label(51.7) == "Fair"  # ~4-word passphrase
    assert passphrase_complexity_label(59.9) == "Fair"


def test_passphrase_complexity_label_good():
    assert passphrase_complexity_label(60.0) == "Good"
    assert passphrase_complexity_label(64.6) == "Good"  # ~5-word passphrase
    assert passphrase_complexity_label(79.9) == "Good"


def test_passphrase_complexity_label_strong():
    assert passphrase_complexity_label(80.0) == "Strong"
    assert passphrase_complexity_label(103.4) == "Strong"  # ~8-word passphrase
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest tests/test_main.py::test_passphrase_complexity_label_weak -v`

Expected: `ImportError: cannot import name 'passphrase_complexity_label' from 'main'`

- [ ] **Step 3: Add `passphrase_complexity_label` to `main.py`**

In `main.py`, find the `score_label` function (around line 158):

```python
def score_label(score: int) -> str:
    return ["Weak", "Fair", "Good", "Strong"][max(0, score - 1)]
```

Add the new function immediately after it:

```python
def passphrase_complexity_label(entropy: float) -> str:
    if entropy >= 80:
        return "Strong"
    if entropy >= 60:
        return "Good"
    if entropy >= 40:
        return "Fair"
    return "Weak"
```

- [ ] **Step 4: Run new tests to confirm they pass**

Run: `uv run pytest tests/test_main.py::test_passphrase_complexity_label_weak tests/test_main.py::test_passphrase_complexity_label_fair tests/test_main.py::test_passphrase_complexity_label_good tests/test_main.py::test_passphrase_complexity_label_strong -v`

Expected: all 4 PASS

- [ ] **Step 5: Update `build_response` to accept a `passphrase` flag**

In `main.py`, replace the current `build_response` function:

```python
def build_response(password: str, entropy: float) -> dict:
    score = complexity_score(password)
    return {
        "password": password,
        "entropy": entropy,
        "complexity": score_label(score),
        "time_to_crack": format_time(time_to_crack_seconds(entropy)),
    }
```

with:

```python
def build_response(password: str, entropy: float, passphrase: bool = False) -> dict:
    label = passphrase_complexity_label(entropy) if passphrase else score_label(complexity_score(password))
    return {
        "password": password,
        "entropy": entropy,
        "complexity": label,
        "time_to_crack": format_time(time_to_crack_seconds(entropy)),
    }
```

- [ ] **Step 6: Update the two passphrase call sites**

In `main.py`, find the `/generate` POST handler. Replace:

```python
    if gen_type == "password":
        password, entropy = generate_password_with_options(length, use_digits, use_symbols)
    else:
        word_dict = get_word_dict()
        password = generate_passphrase(word_dict, length, use_digits, use_symbols)
        entropy = passphrase_entropy(length, use_digits, use_symbols)

    return jsonify(build_response(password, entropy))
```

with:

```python
    if gen_type == "password":
        password, entropy = generate_password_with_options(length, use_digits, use_symbols)
        return jsonify(build_response(password, entropy))

    word_dict = get_word_dict()
    password = generate_passphrase(word_dict, length, use_digits, use_symbols)
    entropy = passphrase_entropy(length, use_digits, use_symbols)
    return jsonify(build_response(password, entropy, passphrase=True))
```

Then find the `passphrase_route` function and replace:

```python
    data = build_response(password, entropy)
```

with:

```python
    data = build_response(password, entropy, passphrase=True)
```

- [ ] **Step 7: Run all tests**

Run: `uv run pytest tests/ -v`

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: entropy-based complexity labels for passphrases"
```

---

### Task 2: Add `-` to SYMBOLS

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

**Background:** `SYMBOLS` excluded `-` to prevent it appearing as a passphrase word separator. Since the 2026-05-04 passphrase format fix, the symbol is always the last character, so there is no longer any ambiguity.

**Important:** After this change the assertion `sum(c in SYMBOLS for c in pwd) == 1` in `test_passphrase_digit_and_symbol_count` would incorrectly count passphrase separator dashes (e.g. `Word1-Word2-Word3`) as symbols. That test must be updated to a positional check before changing `SYMBOLS`.

- [ ] **Step 1: Update `test_passphrase_digit_and_symbol_count`**

In `tests/test_main.py`, replace:

```python
def test_passphrase_digit_and_symbol_count(word_dict):
    """Exactly one digit and one symbol inserted."""
    pwd = generate_passphrase(word_dict, 5, True, True)
    assert sum(c.isdigit() for c in pwd) == 1
    assert sum(c in SYMBOLS for c in pwd) == 1
```

with:

```python
def test_passphrase_digit_and_symbol_count(word_dict):
    """Exactly one digit added; symbol is the last character."""
    pwd = generate_passphrase(word_dict, 5, True, True)
    assert sum(c.isdigit() for c in pwd) == 1
    assert pwd[-1] in SYMBOLS
```

- [ ] **Step 2: Confirm the updated test passes before touching SYMBOLS**

Run: `uv run pytest tests/test_main.py::test_passphrase_digit_and_symbol_count -v`

Expected: PASS

- [ ] **Step 3: Add `-` to `SYMBOLS` in `main.py`**

Replace:

```python
SYMBOLS = "!@#$%^&*()_+=[]{}|;:,.<>?"
```

with:

```python
SYMBOLS = "!@#$%^&*()_+=[]{}|;:,.<>?-"
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/ -v`

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add hyphen to SYMBOLS pool"
```

---

### Task 3: Share URL missing `https://` protocol

**Files:**
- Modify: `templates/index.html`

**Background:** The share button builds its URL with `window.location.host` only, producing `genpwd.sh/passphrase+4` — a string that requires a manual `https://` prefix before it's navigable in a browser.

- [ ] **Step 1: Fix the URL construction in the share button handler**

In `templates/index.html`, find the share button event listener (around line 1110). Change:

```js
      var url    = window.location.host + '/' + type + '+' + length;
```

to:

```js
      var url    = 'https://' + window.location.host + '/' + type + '+' + length;
```

- [ ] **Step 2: Commit**

```bash
git add templates/index.html
git commit -m "fix: share button copies full https:// URL"
```

---

### Task 4: Replace Font Awesome CDN with inline SVGs

**Files:**
- Modify: `templates/index.html`

**Background:** Three social icons in the footer are loaded via `https://kit.fontawesome.com/4b7d445623.js`. This introduces an external CDN dependency, a third-party tracking request, and a blocking script load. Google Fonts stays (it's intentional for visual identity). Only Font Awesome is removed.

- [ ] **Step 1: Remove the Font Awesome `<script>` tag**

In `templates/index.html`, find and delete these two lines near the top of `<head>`:

```html
  <!-- Font Awesome for social icons -->
  <script src="https://kit.fontawesome.com/4b7d445623.js" crossorigin="anonymous"></script>
```

- [ ] **Step 2: Replace the three footer icon elements with inline SVGs**

Find the footer `<a>` elements (around line 749):

```html
      <a href="https://instagram.com/audrum" target="_blank" rel="noopener" title="Instagram">
        <i class="fa-brands fa-instagram"></i>
      </a>
      <a href="https://bsky.app/profile/andresbolivar.me" target="_blank" rel="noopener" title="Bluesky">
        <i class="fa-brands fa-bluesky"></i>
      </a>
      <a href="https://github.com/audrum/genpwd-sh" target="_blank" rel="noopener" title="GitHub">
        <i class="fa-brands fa-github"></i>
      </a>
```

Replace with:

```html
      <a href="https://instagram.com/audrum" target="_blank" rel="noopener" title="Instagram">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
      </a>
      <a href="https://bsky.app/profile/andresbolivar.me" target="_blank" rel="noopener" title="Bluesky">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 600 530" fill="currentColor" aria-hidden="true"><path d="M135.72 44.03C202.216 93.951 273.74 195.17 300 249.49c26.262-54.316 97.782-155.54 164.28-205.46C512.26 8.009 590-19.862 590 68.825c0 17.712-10.155 148.79-16.111 170.07-20.703 73.984-96.144 92.854-163.25 81.433 117.3 19.964 147.14 86.092 82.697 152.22-122.39 125.59-175.91-31.511-189.63-71.766-2.514-7.38-3.69-10.832-3.708-7.896-.017-2.936-1.193.516-3.707 7.896-13.714 40.255-67.233 197.36-189.63 71.766-64.444-66.128-34.605-132.26 82.697-152.22-67.108 11.421-142.55-7.45-163.25-81.433C20.15 217.613 10 86.532 10 68.825c0-88.687 77.742-60.816 125.72-24.795z"/></svg>
      </a>
      <a href="https://github.com/audrum/genpwd-sh" target="_blank" rel="noopener" title="GitHub">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/></svg>
      </a>
```

- [ ] **Step 3: Run tests to confirm nothing broke**

Run: `uv run pytest tests/ -v`

Expected: all pass (template changes don't affect backend tests)

- [ ] **Step 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: replace Font Awesome CDN with inline SVGs"
```

---

### Task 5: Gitignore local plan docs

**Files:**
- Modify: `.gitignore`

**Background:** Two internal planning markdown files under `docs/plans/` are untracked and appear in `git status` on every run. They are local artifacts, not part of the app.

- [ ] **Step 1: Add `docs/plans/` to `.gitignore`**

Open `.gitignore` and append:

```
docs/plans/
```

- [ ] **Step 2: Verify the files are now ignored**

Run: `git status`

Expected: `docs/plans/2026-03-08-improvements.md` and `docs/plans/2026-03-08-refactor-redesign-plan.md` no longer appear under "Untracked files".

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore local plan docs"
```

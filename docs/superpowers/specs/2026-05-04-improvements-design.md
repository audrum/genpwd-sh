# genpwd-sh Improvements Design

**Date:** 2026-05-04
**Scope:** Five independent fixes across backend logic, frontend UX, and repo hygiene.
**Files touched:** `main.py`, `templates/index.html`, `.gitignore`

---

## 1. Passphrase complexity label (`main.py`)

### Problem
`complexity_score()` uses character-based heuristics (uppercase, lowercase, digits, symbols, length ≥ 12). Passphrases always have mixed case (capitalized words) and are typically long, so they almost always score "Good" regardless of actual entropy. A 4-word passphrase with ~52 bits of entropy shows "Good" when it should reflect a stronger signal.

### Fix
Add `passphrase_complexity_label(entropy: float) -> str` that maps entropy directly to a label:

| Entropy (bits) | Label  |
|----------------|--------|
| < 40           | Weak   |
| ≥ 40 and < 60  | Fair   |
| ≥ 60 and < 80  | Good   |
| ≥ 80           | Strong |

Examples:
- 4 words, no extras → ~52 bits → **Fair**
- 6 words, no extras → ~78 bits → **Good**
- 8 words, no extras → ~103 bits → **Strong**
- 4 words + digit + symbol → ~60 bits → **Good**

Update `build_response()` to accept an optional `passphrase: bool = False` parameter. When `True`, use `passphrase_complexity_label(entropy)` instead of `complexity_score(password)`.

Update both passphrase call sites (`/generate` POST handler and `/passphrase` route) to pass `passphrase=True`.

### Tests
- Update any existing tests that assert passphrase complexity labels.
- Add unit tests for `passphrase_complexity_label()` covering all four thresholds.

---

## 2. Add `-` to `SYMBOLS` (`main.py`)

### Problem
`SYMBOLS` excludes `-` to prevent it from appearing as a passphrase word separator. Since the passphrase format fix (2026-05-04), the symbol is always appended last with no ambiguity.

### Fix
Add `-` to the `SYMBOLS` constant. No other changes needed.

---

## 3. Share URL missing protocol (`templates/index.html`)

### Problem
The share button builds the URL as:
```js
var url = window.location.host + '/' + type + '+' + length;
```
This produces `genpwd.sh/passphrase+4` — not a navigable URL when pasted into a browser.

### Fix
```js
var url = 'https://' + window.location.host + '/' + type + '+' + length;
```

---

## 4. Replace Font Awesome with inline SVGs (`templates/index.html`)

### Problem
The footer loads social icons via `<script src="https://kit.fontawesome.com/4b7d445623.js">`. This creates an external CDN dependency (app icons break if FA is down), a third-party tracking vector, and an extra network request on every page load. Two `<link rel="preconnect">` tags for Google Fonts also load an external font.

### Fix
- Remove the Font Awesome `<script>` tag only. Google Fonts stays — DM Sans and DM Mono are part of the app's visual identity.
- Replace the three `<i class="fa-brands ...">` elements in the footer with minimal inline SVGs for Instagram, Bluesky, and GitHub. SVGs sized 20×20, styled to match current `footer a` color and hover behavior (`color: var(--text-muted)`, hover `color: var(--cyan)`).

---

## 5. Repo hygiene — gitignore plan docs (`.gitignore`)

### Problem
`docs/plans/2026-03-08-improvements.md` and `docs/plans/2026-03-08-refactor-redesign-plan.md` are untracked local files that appear in `git status`. They are internal planning artifacts, not part of the deployable app.

### Fix
Add `docs/plans/` to `.gitignore`.

---

## Architecture impact

All five changes are additive or subtractive with no structural changes:
- No new routes, no new dependencies, no database changes.
- `build_response()` gains one optional boolean parameter — existing callers (password routes) are unaffected.
- Frontend changes are all within `templates/index.html`; no new static files are introduced.

## Testing strategy

- `passphrase_complexity_label()`: unit tests for all four entropy thresholds.
- Share URL fix: no automated test needed (one-line JS change, verifiable manually).
- SYMBOLS change: existing `test_passphrase_digit_and_symbol_count` covers that a symbol is present; no new test needed.
- Font Awesome removal: visual/manual verification.
- `.gitignore` change: `git status` verification.

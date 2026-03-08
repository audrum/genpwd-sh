# Refactor & Redesign — GenPWD.sh

**Date:** 2026-03-08
**Status:** Approved

## Goal

Refactor `main.py` for correctness and maintainability, improve the passphrase digit/symbol insertion logic, and redesign the frontend with a glassmorphism/gradient aesthetic.

## Backend (`main.py`)

**Structure:** Keep single-file. No blueprint split needed at this scale.

**Fixes:**
- Cache `eff_large_wordlist.txt` at module startup (currently reloaded on every passphrase request)
- Move all `from flask import ...` imports to top of file (currently imported inside route functions)
- Extract `is_cli_request(request)` helper to eliminate duplicated content-negotiation logic across three routes
- Fix `password_response()` charset size: passphrases include `-` separators and words (only lowercase letters), current calculation uses `charset_size = 52` which is wrong for passphrases

**Passphrase digit/symbol sprinkle logic:**
- Current: appends one digit and/or one symbol at the very end (`Word-Word-Word7!`)
- New: randomly insert digit(s) and/or symbol(s) as separators replacing hyphens at random word-join positions
- Example: `Word-7-Word-!-Word-Word` or `Word7Word-Word!Word`
- Keeps the output more natural and harder to pattern-match

## Frontend (`templates/index.html`)

**Style:** Glassmorphism card on an animated vivid gradient background. No external CSS/JS dependencies.

**Layout:**
- Animated gradient background (purple → blue → teal)
- Centered frosted-glass card with blur + semi-transparent background
- Two tabs: Password / Passphrase
- Controls: length slider, toggle checkboxes for digits/symbols
- Large result display with one-click copy button
- Visual strength meter (color bar) for entropy/complexity
- Fully responsive

**Behavior:**
- Auto-generates on tab switch and control change
- Copy to clipboard with visual confirmation
- All API calls via `POST /generate` (existing endpoint)

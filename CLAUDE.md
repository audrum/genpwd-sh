# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GenPWD.sh is a Flask-based password/passphrase generator with both a web UI and a curl-friendly API. The app runs on port 9876, deployed on Fly.io.

## Commands

```sh
# Install dependencies (uses uv)
uv pip install .

# Run locally (debug mode, port 9876)
python main.py

# Build Docker image
docker build -t genpwd-sh .

# Run Docker container
docker run -p 9876:9876 genpwd-sh

# Deploy to Fly.io
fly deploy

# Run all tests
uv run pytest tests/ -v

# Run a single test by name
uv run pytest tests/ -k "test_passphrase_no_extras" -v
```

## Architecture

All application logic lives in a single file: `main.py`.

**Request flow:**
- `GET /` → serves `templates/index.html` (web UI)
- `POST /generate` → JSON API used by the web UI (accepts `length`, `use_digits`, `use_symbols`)
- `GET /password[+options]`, `GET /passphrase[+options]`, `GET /random[+N]` → curl-friendly endpoints that detect user-agent to return plain text (curl) or JSON (browser)

**Option parsing:** The `parse_options()` function parses `+number`, `+symbol`, and `+<int>` tokens from the URL path using regex. Options can appear in any order.

**Response format:** All password generation flows through `password_response()`, which calculates entropy (bits), complexity label (Weak/Fair/Good/Strong), and estimated time to crack at 10B guesses/second.

**Wordlist:** `eff_large_wordlist.txt` is the EFF Diceware large wordlist (tab-separated number-word pairs). Loaded fresh on each passphrase request.

**Content negotiation:** curl requests (detected by `User-Agent` starting with `curl`) and requests with `Accept: text/plain` get plain text responses; all others get JSON.

**Tests:** `tests/test_main.py` — pytest suite covering passphrase generation logic and API routes.

**Key constants and helpers:**
- `SYMBOLS` — module-level constant of allowed symbol characters; excludes `-` so it doesn't conflict with passphrase word separators
- `get_word_dict()` — lazy-cached wordlist loader; reads `eff_large_wordlist.txt` once at first request and reuses the result on subsequent calls
- `generate_password_with_options()` — shared helper used by both the `POST /generate` JSON endpoint and the `GET /password[+options]` curl-friendly route

# GenPWD.sh

A simple to use password generator that offers multiple parameters for generating passwords either from web UI or CLI using simply `curl`.

---

## Features

- **Web UI** for generating passwords and passphrases with options
- **API endpoints** for use with curl or scripts
- **EFF wordlist passphrases** (Diceware style)
- **Random letter passwords** (with optional digits/symbols)
- **Customizable length and options**
- **Entropy, complexity, and time-to-crack** metrics for every result
- **Copy to clipboard** from the web UI

---

## Web UI

- Choose between **Password** (random letters) and **Passphrase** (EFF wordlist)
- Customize length, and optionally add digits/symbols
- See entropy, complexity, and estimated time to crack
- Copy results to clipboard

---

## API Usage

You can generate passwords and passphrases via `curl` or your browser using the following endpoints:

| Endpoint Example | Description |
|------------------|-------------|
| `/password` | 8-letter password (default) |
| `/password+12` | 12-letter password |
| `/password+number+symbol+16` | 16-letter password with digit and symbol |
| `/passphrase` | 4-word passphrase (default) |
| `/passphrase+6` | 6-word passphrase |
| `/passphrase+number+symbol+7` | 7-word passphrase with digit and symbol |
| `/random` | 12-letter random password (default) |
| `/random+20` | 20-letter random password |

You can combine `+number`, `+symbol`, and `+<length>` in any order after `/password` or `/passphrase`.

### Example curl commands

```sh
# 8-letter password
curl http://genpwd.sh/password

# 12-letter password with digit and symbol
curl http://genpwd.sh/password+number+symbol+12

# 4-word passphrase
curl http://genpwd.sh/passphrase

# 6-word passphrase with digit and symbol
curl http://genpwd.sh/passphrase+number+symbol+6

# 20-letter random password
curl http://genpwd.sh/random+20
```

### Example output (plain text)
```
QwErTyUi12!

Entropy: 78.64
Complexity: Strong
Estimated Time to crack: 2 years, 45 days, 3 hours
```

---

## Security Notes
- Entropy and time-to-crack are estimates, assuming 10 billion guesses/second (offline attack).
- For maximum security, use long passphrases or passwords with digits and symbols.
- Never reuse passwords across important accounts.

---

## License
MIT

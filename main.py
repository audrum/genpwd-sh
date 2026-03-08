import random
import math
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)

WORDLIST = Path(__file__).parent / "eff_large_wordlist.txt"
SYMBOLS = "!@#$%^&*()_+=[]{}|;:,.<>?"

# Cache wordlist at startup — not on every request
_WORD_DICT: dict[str, str] = {}


def load_eff_wordlist(file_path: Path) -> dict[str, str]:
    word_dict = {}
    with open(file_path) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                word_dict[parts[0]] = parts[1]
    return word_dict


def get_word_dict() -> dict[str, str]:
    global _WORD_DICT
    if not _WORD_DICT:
        _WORD_DICT = load_eff_wordlist(WORDLIST)
    return _WORD_DICT


def generate_passphrase(word_dict: dict, length: int, use_digits: bool, use_symbols: bool) -> str:
    """Generate passphrase from EFF wordlist. Digits/symbols are sprinkled as
    separators between random word-pairs instead of appended at the end."""
    words = []
    for _ in range(length):
        while True:
            number = str(random.randint(11111, 66666))
            if number in word_dict:
                words.append(word_dict[number].capitalize())
                break

    if length == 1:
        # No separators to sprinkle into; fall back to appending
        result = words[0]
        if use_digits:
            result += str(random.randint(0, 9))
        if use_symbols:
            result += random.choice(SYMBOLS)
        return result

    # Build separator slots: (length - 1) hyphens
    separators = ["-"] * (length - 1)

    # Collect extras to sprinkle
    extras: list[str] = []
    if use_digits:
        extras.append(str(random.randint(0, 9)))
    if use_symbols:
        extras.append(random.choice(SYMBOLS))

    # Replace randomly chosen separators with the extras
    if extras:
        positions = random.sample(range(len(separators)), min(len(extras), len(separators)))
        for i, pos in enumerate(positions):
            separators[pos] = extras[i]

    # Interleave words and separators
    result = words[0]
    for word, sep in zip(words[1:], separators):
        result += sep + word
    return result


def generate_password(length: int = 8) -> str:
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(random.choice(letters) for _ in range(length))


def parse_options(path: str, default_length: int) -> tuple[int, bool, bool]:
    """Parse +number, +symbol, +<int> tokens from a URL path segment."""
    use_digits = False
    use_symbols = False
    length = default_length
    for part in re.findall(r"\+([a-zA-Z0-9]+)", path):
        if part.isdigit():
            length = int(part)
        elif part.lower() == "number":
            use_digits = True
        elif part.lower() == "symbol":
            use_symbols = True
    return length, use_digits, use_symbols


def calculate_entropy(password: str, charset_size: int) -> float:
    return round(len(password) * math.log2(charset_size), 2)


def passphrase_entropy(word_count: int, use_digits: bool, use_symbols: bool) -> float:
    """Word-based entropy: each word chosen from ~7776-word EFF list (log2(7776) ≈ 12.92 bits)."""
    WORDLIST_SIZE = 7776  # 6^5
    bits = word_count * math.log2(WORDLIST_SIZE)
    if use_digits:
        bits += math.log2(10)
    if use_symbols:
        bits += math.log2(len(SYMBOLS))
    return round(bits, 2)


def complexity_score(password: str) -> int:
    score = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(c in SYMBOLS for c in password),
        len(password) >= 12,
    ])
    return min(score, 4)


def score_label(score: int) -> str:
    return ["Weak", "Fair", "Good", "Strong"][max(0, score - 1)]


def time_to_crack_seconds(entropy: float, guesses_per_second: float = 1e10) -> float:
    return (0.5 * 2 ** entropy) / guesses_per_second


def format_time(seconds: float) -> str:
    intervals = [
        ("years", 60 * 60 * 24 * 365),
        ("days", 60 * 60 * 24),
        ("hours", 60 * 60),
        ("minutes", 60),
        ("seconds", 1),
    ]
    result = []
    for name, count in intervals:
        value = int(seconds // count)
        if value:
            result.append(f"{value} {name}")
            seconds -= value * count
    return ", ".join(result) if result else "< 1 second"


def build_response(password: str, entropy: float) -> dict:
    score = complexity_score(password)
    return {
        "password": password,
        "entropy": entropy,
        "complexity": score_label(score),
        "time_to_crack": format_time(time_to_crack_seconds(entropy)),
    }


def is_cli_request() -> bool:
    return (
        "text/plain" in request.headers.get("Accept", "")
        or request.user_agent.string.startswith("curl")
    )


def plain_text_response(data: dict) -> tuple:
    body = (
        f"{data['password']}\n\n"
        f"Entropy: {data['entropy']}\n"
        f"Complexity: {data['complexity']}\n"
        f"Estimated Time to crack: {data['time_to_crack']}\n"
    )
    return body, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    length = data.get("length", 4)
    use_digits = data.get("use_digits", False)
    use_symbols = data.get("use_symbols", False)
    gen_type = data.get("type", "passphrase")

    if gen_type == "password":
        password = generate_password(length)
        if use_digits:
            password += str(random.randint(0, 9))
        if use_symbols:
            password += random.choice(SYMBOLS)
        charset_size = 52 + (10 if use_digits else 0) + (len(SYMBOLS) if use_symbols else 0)
        entropy = calculate_entropy(password, charset_size)
    else:
        word_dict = get_word_dict()
        password = generate_passphrase(word_dict, length, use_digits, use_symbols)
        entropy = passphrase_entropy(length, use_digits, use_symbols)

    return jsonify(build_response(password, entropy))


@app.route("/password", defaults={"extra": ""})
@app.route("/password<path:extra>")
def password_route(extra):
    length, use_digits, use_symbols = parse_options("/password" + extra, default_length=8)
    password = generate_password(length)
    if use_digits:
        password += str(random.randint(0, 9))
    if use_symbols:
        password += random.choice(SYMBOLS)
    charset_size = 52 + (10 if use_digits else 0) + (len(SYMBOLS) if use_symbols else 0)
    entropy = calculate_entropy(password, charset_size)
    data = build_response(password, entropy)
    return plain_text_response(data) if is_cli_request() else jsonify(data)


@app.route("/passphrase", defaults={"extra": ""})
@app.route("/passphrase<path:extra>")
def passphrase_route(extra):
    length, use_digits, use_symbols = parse_options("/passphrase" + extra, default_length=4)
    word_dict = get_word_dict()
    password = generate_passphrase(word_dict, length, use_digits, use_symbols)
    entropy = passphrase_entropy(length, use_digits, use_symbols)
    data = build_response(password, entropy)
    return plain_text_response(data) if is_cli_request() else jsonify(data)


@app.route("/random", defaults={"length": 12})
@app.route("/random+<int:length>")
def random_letters_route(length):
    password = generate_password(length)
    entropy = calculate_entropy(password, 52)
    data = build_response(password, entropy)
    return plain_text_response(data) if is_cli_request() else jsonify(data)


@app.route("/help")
def help_route():
    cli_help = """\
GenPWD.sh - Password & Passphrase Generator API

Usage:
  curl genpwd.sh/password
  curl genpwd.sh/password+number+symbol+12
  curl genpwd.sh/passphrase
  curl genpwd.sh/passphrase+number+symbol+6
  curl genpwd.sh/random+20

Endpoints:
  /password[+number][+symbol][+N]    Random password (N letters, default 8)
  /passphrase[+number][+symbol][+N]  EFF passphrase (N words, default 4)
  /random[+N]                        Random password (N letters, default 12)

Options:
  +number   Add a digit (sprinkled into passphrase, appended to password)
  +symbol   Add a symbol (sprinkled into passphrase, appended to password)
  +N        Set length (letters or words)

Output:
  Returns password/passphrase, entropy, complexity, and estimated time to crack.
  Use --header 'Accept: application/json' for JSON output.
"""
    if is_cli_request():
        return cli_help, 200, {"Content-Type": "text/plain; charset=utf-8"}
    readme_path = Path(__file__).parent / "README.md"
    doc = readme_path.read_text()
    html = f"""<html><head><title>GenPWD.sh Help</title></head>
<body style='font-family:monospace;white-space:pre-wrap;background:#f8faff;padding:2em;'>
<h1>GenPWD.sh Help</h1>
<pre style='font-family:inherit;font-size:1em;background:none;border:none;'>{doc}</pre>
</body></html>"""
    return html


@app.route("/about")
def about_route():
    bluesky = "https://bsky.app/profile/andresbolivar.bsky.social"
    github = "https://github.com/audrum"
    cli_about = f"""\
GenPWD.sh - About

Created by Andres Bolivar
Bluesky: {bluesky}
GitHub:  {github}
"""
    if is_cli_request():
        return cli_about, 200, {"Content-Type": "text/plain; charset=utf-8"}
    html = f"""<html><head><title>About GenPWD.sh</title></head>
<body style='font-family:sans-serif;background:#f8faff;padding:2em;'>
<h1>About GenPWD.sh</h1>
<p><b>Created by Andres Bolivar</b></p>
<ul>
  <li>Bluesky: <a href='{bluesky}' target='_blank'>{bluesky}</a></li>
  <li>GitHub: <a href='{github}' target='_blank'>{github}</a></li>
</ul>
<p style='margin-top:2em;'><a href='/help'>API Help</a></p>
</body></html>"""
    return html


if __name__ == "__main__":
    app.run(debug=True, port=9876, host="0.0.0.0")

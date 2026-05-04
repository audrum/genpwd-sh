import secrets
import math
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

RATE_LIMIT = "60 per minute"

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
    words = []
    for _ in range(length):
        while True:
            number = str(secrets.randbelow(66666 - 11111 + 1) + 11111)
            if number in word_dict:
                words.append(word_dict[number].capitalize())
                break

    result = "-".join(words)
    if use_digits:
        result += "-" + str(secrets.randbelow(10))
    if use_symbols:
        result += secrets.choice(SYMBOLS)
    return result


def generate_password(length: int = 8) -> str:
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(secrets.choice(letters) for _ in range(length))


def parse_options(path: str, default_length: int, max_length: int = 64) -> tuple[int, bool, bool]:
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
    length = max(1, min(length, max_length))
    return length, use_digits, use_symbols


def calculate_entropy(password: str, charset_size: int) -> float:
    return round(len(password) * math.log2(charset_size), 2)


def generate_password_with_options(length: int, use_digits: bool, use_symbols: bool) -> tuple[str, float]:
    """Generate a letter password with optional digit/symbol appended, and compute its entropy."""
    password = generate_password(length)
    if use_digits:
        password += str(secrets.randbelow(10))
    if use_symbols:
        password += secrets.choice(SYMBOLS)
    charset_size = 52 + (10 if use_digits else 0) + (len(SYMBOLS) if use_symbols else 0)
    return password, calculate_entropy(password, charset_size)


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


def passphrase_complexity_label(entropy: float) -> str:
    if entropy >= 80:
        return "Strong"
    if entropy >= 60:
        return "Good"
    if entropy >= 40:
        return "Fair"
    return "Weak"


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


def build_response(password: str, entropy: float, passphrase: bool = False) -> dict:
    label = passphrase_complexity_label(entropy) if passphrase else score_label(complexity_score(password))
    return {
        "password": password,
        "entropy": entropy,
        "complexity": label,
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
@limiter.limit(RATE_LIMIT)
def generate():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    gen_type = data.get("type", "passphrase")
    use_digits = data.get("use_digits", False)
    use_symbols = data.get("use_symbols", False)
    max_len = 20 if gen_type == "passphrase" else 64
    length = min(max(1, data.get("length", 4)), max_len)

    if gen_type == "password":
        password, entropy = generate_password_with_options(length, use_digits, use_symbols)
        return jsonify(build_response(password, entropy))

    word_dict = get_word_dict()
    password = generate_passphrase(word_dict, length, use_digits, use_symbols)
    entropy = passphrase_entropy(length, use_digits, use_symbols)
    return jsonify(build_response(password, entropy, passphrase=True))


@app.route("/password", defaults={"extra": ""})
@app.route("/password<path:extra>")
@limiter.limit(RATE_LIMIT)
def password_route(extra):
    length, use_digits, use_symbols = parse_options("/password" + extra, default_length=8, max_length=64)
    password, entropy = generate_password_with_options(length, use_digits, use_symbols)
    data = build_response(password, entropy)
    return plain_text_response(data) if is_cli_request() else jsonify(data)


@app.route("/passphrase", defaults={"extra": ""})
@app.route("/passphrase<path:extra>")
@limiter.limit(RATE_LIMIT)
def passphrase_route(extra):
    length, use_digits, use_symbols = parse_options("/passphrase" + extra, default_length=4, max_length=20)
    word_dict = get_word_dict()
    password = generate_passphrase(word_dict, length, use_digits, use_symbols)
    entropy = passphrase_entropy(length, use_digits, use_symbols)
    data = build_response(password, entropy, passphrase=True)
    return plain_text_response(data) if is_cli_request() else jsonify(data)


@app.route("/random", defaults={"extra": ""})
@app.route("/random<path:extra>")
@limiter.limit(RATE_LIMIT)
def random_letters_route(extra):
    length, use_digits, use_symbols = parse_options("/random" + extra, default_length=12, max_length=64)
    password, entropy = generate_password_with_options(length, use_digits, use_symbols)
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
    website = "https://andresbolivar.me"
    instagram = "https://instagram.com/audrum"
    bluesky = "https://bsky.app/profile/andresbolivar.me"
    github = "https://github.com/audrum/genpwd-sh"
    cli_about = f"""\
GenPWD.sh - About

Created by Andres Bolivar
Website:   {website}
Instagram: {instagram}
Bluesky:   {bluesky}
GitHub:    {github}
"""
    if is_cli_request():
        return cli_about, 200, {"Content-Type": "text/plain; charset=utf-8"}
    html = f"""<html><head><title>About GenPWD.sh</title></head>
<body style='font-family:sans-serif;background:#f8faff;padding:2em;'>
<h1>About GenPWD.sh</h1>
<p><b>Created by Andres Bolivar</b></p>
<ul>
  <li>Website: <a href='{website}' target='_blank'>{website}</a></li>
  <li>Instagram: <a href='{instagram}' target='_blank'>{instagram}</a></li>
  <li>Bluesky: <a href='{bluesky}' target='_blank'>{bluesky}</a></li>
  <li>GitHub: <a href='{github}' target='_blank'>{github}</a></li>
</ul>
<p style='margin-top:2em;'><a href='/help'>API Help</a></p>
</body></html>"""
    return html


@app.route("/health")
def health_route():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=9876, host="0.0.0.0")

import random
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import re
import math

app = Flask(__name__)

WORDLIST = Path(__file__).parent / "eff_large_wordlist.txt"

def load_eff_wordlist(file_path):
    """Load EFF wordlist and return a dict: number (str) -> word (str)."""
    word_dict = {}
    with open(file_path, "r") as file:
        for line in file:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                number, word = parts
                word_dict[number] = word
    return word_dict

def generate_passphrase(word_dict, length, use_digits, use_symbols):
    """Generate a passphrase using the EFF wordlist, with options for digits and symbols. Each word is capitalized."""
    words = []
    for _ in range(length):
        while True:
            number = str(random.randint(11111, 66666))
            if number in word_dict:
                words.append(word_dict[number].capitalize())
                break
    password = '-'.join(words)
    if use_digits:
        password += str(random.randint(0, 9))
    if use_symbols:
        password += random.choice("!@#$%^&*()_+-=[]{}|;:,.<>?")
    return password


def generate_password(length=8):
    """Generate a password of random mixed-case letters."""
    letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return ''.join(random.choice(letters) for _ in range(length))

def parse_options(path, default_length):
    # Extract options from the path using regex
    # e.g. /password+number+symbol+10 or /passphrase+symbol+6
    use_digits = False
    use_symbols = False
    length = default_length
    # Find all option parts after the route
    parts = re.findall(r'\+([a-zA-Z0-9]+)', path)
    for part in parts:
        if part.isdigit():
            length = int(part)
        elif part.lower() == 'number':
            use_digits = True
        elif part.lower() == 'symbol':
            use_symbols = True
    return length, use_digits, use_symbols

def calculate_entropy(password, charset_size):
    # Entropy in bits: length * log2(charset_size)
    return round(len(password) * math.log2(charset_size), 2)

def complexity_score(password):
    # Simple scoring: 1-weak, 2-fair, 3-good, 4-strong
    score = 0
    if any(c.islower() for c in password):
        score += 1
    if any(c.isupper() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        score += 1
    if len(password) >= 12:
        score += 1
    return min(score, 4)

def score_label(score):
    return ["Weak", "Fair", "Good", "Strong"][max(0, score-1)]

def time_to_crack_seconds(entropy, guesses_per_second=1e10):
    # Average guesses needed: 0.5 * 2^entropy
    avg_guesses = 0.5 * 2 ** entropy
    seconds = avg_guesses / guesses_per_second
    return seconds

def format_time(seconds):
    # Human-readable time formatting
    intervals = [
        ('years', 60*60*24*365),
        ('days', 60*60*24),
        ('hours', 60*60),
        ('minutes', 60),
        ('seconds', 1)
    ]
    result = []
    for name, count in intervals:
        value = int(seconds // count)
        if value:
            result.append(f"{value} {name}")
            seconds -= value * count
    if not result:
        return "< 1 second"
    return ', '.join(result)

# Update password_response to include time to crack

def password_response(password):
    charset_size = 52  # a-zA-Z
    if any(c.isdigit() for c in password):
        charset_size += 10
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        charset_size += len("!@#$%^&*()_+-=[]{}|;:,.<>?")
    entropy = calculate_entropy(password, charset_size)
    score = complexity_score(password)
    label = score_label(score)
    crack_seconds = time_to_crack_seconds(entropy)
    crack_time = format_time(crack_seconds)
    return {
        "password": password,
        "entropy": entropy,
        "complexity": label,
        "time_to_crack": crack_time
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    length = data.get('length', 4)
    use_digits = data.get('use_digits', True)
    use_symbols = data.get('use_symbols', True)
    word_dict = load_eff_wordlist(WORDLIST)
    password = generate_passphrase(word_dict, length, use_digits, use_symbols)
    resp = password_response(password)
    return jsonify(resp)

# Password route with optional length (default 8)
@app.route('/password', defaults={'extra': ''})
@app.route('/password<path:extra>')
def password_route(extra):
    length, use_digits, use_symbols = parse_options('/password'+extra, default_length=8)
    password = generate_password(length)
    # Optionally append digit/symbol
    if use_digits:
        password += str(random.randint(0, 9))
    if use_symbols:
        password += random.choice("!@#$%^&*()_+-=[]{}|;:,.<>?")
    resp = password_response(password)
    # If curl (Accept: text/plain), return plain text, else JSON
    from flask import request
    if 'text/plain' in request.headers.get('Accept', '') or request.user_agent.string.startswith('curl'):
        return f"{resp['password']}\n\nEntropy: {resp['entropy']}\nComplexity: {resp['complexity']}\nEstimated Time to crack: {resp['time_to_crack']}\n", 200, {'Content-Type': 'text/plain; charset=utf-8'}
    return jsonify(resp)

# Passphrase route with optional length (default 4)
@app.route('/passphrase', defaults={'extra': ''})
@app.route('/passphrase<path:extra>')
def passphrase_route(extra):
    length, use_digits, use_symbols = parse_options('/passphrase'+extra, default_length=4)
    word_dict = load_eff_wordlist(WORDLIST)
    password = generate_passphrase(word_dict, length, use_digits, use_symbols)
    resp = password_response(password)
    from flask import request
    if 'text/plain' in request.headers.get('Accept', '') or request.user_agent.string.startswith('curl'):
        return f"{resp['password']}\n\nEntropy: {resp['entropy']}\nComplexity: {resp['complexity']}\nEstimated Time to crack: {resp['time_to_crack']}\n", 200, {'Content-Type': 'text/plain; charset=utf-8'}
    return jsonify(resp)

@app.route('/random', defaults={'length': 12})
@app.route('/random+<int:length>')
def random_letters_route(length):
    letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    password = ''.join(random.choice(letters) for _ in range(length))
    resp = password_response(password)
    from flask import request
    if 'text/plain' in request.headers.get('Accept', '') or request.user_agent.string.startswith('curl'):
        return f"{resp['password']}\n\nEntropy: {resp['entropy']}\nComplexity: {resp['complexity']}\nEstimated Time to crack: {resp['time_to_crack']}\n", 200, {'Content-Type': 'text/plain; charset=utf-8'}
    return jsonify(resp)

@app.route('/help')
def help_route():
    # CLI help (short version)
    cli_help = '''\
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
  +number   Add a digit
  +symbol   Add a symbol
  +N        Set length (letters or words)

Output:
  Returns password/passphrase, entropy, complexity, and estimated time to crack.
  Use --header 'Accept: application/json' for JSON output.
'''
    # Read the README.md file for browser help
    readme_path = Path(__file__).parent / 'README.md'
    with open(readme_path, 'r') as f:
        doc = f.read()
    # Detect if CLI (curl) or browser
    if 'text/plain' in request.headers.get('Accept', '') or request.user_agent.string.startswith('curl'):
        return cli_help, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    # Otherwise, render as simple HTML (preserve markdown formatting)
    html = f"""
    <html><head><title>GenPWD.sh Help</title></head><body style='font-family:monospace;white-space:pre-wrap;background:#f8faff;padding:2em;'>
    <h1>GenPWD.sh Help</h1>
    <pre style='font-family:inherit;font-size:1em;background:none;border:none;'>{doc}</pre>
    </body></html>
    """
    return html

@app.route('/about')
def about_route():
    # Social info
    bluesky = 'https://bsky.app/profile/andresbolivar.bsky.social'
    github = 'https://github.com/audrum'
    cli_about = f'''\
GenPWD.sh - About

Created by Andres Bolivar
Bluesky: {bluesky}
GitHub:  {github}
'''
    if 'text/plain' in request.headers.get('Accept', '') or request.user_agent.string.startswith('curl'):
        return cli_about, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    html = f"""
    <html><head><title>About GenPWD.sh</title></head><body style='font-family:sans-serif;background:#f8faff;padding:2em;'>
    <h1>About GenPWD.sh</h1>
    <p><b>Created by Andres Bolivar</b></p>
    <ul>
      <li>Bluesky: <a href='{bluesky}' target='_blank'>{bluesky}</a></li>
      <li>GitHub: <a href='{github}' target='_blank'>{github}</a></li>
    </ul>
    <p style='margin-top:2em;'><a href='/help'>API Help</a></p>
    </body></html>
    """
    return html

if __name__ == '__main__':
    app.run(debug=True, port=9876, host='0.0.0.0')
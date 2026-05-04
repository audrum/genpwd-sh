import pytest

from main import app, generate_passphrase, load_eff_wordlist, WORDLIST, SYMBOLS, limiter, passphrase_complexity_label


@pytest.fixture
def app_instance():
    app.config['TESTING'] = True
    yield app
    app.config['TESTING'] = False


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


@pytest.fixture
def word_dict():
    return load_eff_wordlist(WORDLIST)


@pytest.fixture(autouse=True)
def disable_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


# --- passphrase sprinkle tests ---

def test_passphrase_no_extras(word_dict):
    """No digits or symbols: all separators should be '-'"""
    pwd = generate_passphrase(word_dict, 4, False, False)
    words = pwd.split('-')
    assert len(words) == 4
    assert all(w[0].isupper() for w in words)


def test_passphrase_digit_at_end(word_dict):
    """Digit always appears at the end of the passphrase (last char)."""
    for _ in range(10):
        pwd = generate_passphrase(word_dict, 4, True, False)
        assert pwd[-1].isdigit(), f"Expected digit at end, got: {pwd}"


def test_passphrase_symbol_at_very_end(word_dict):
    """Symbol always appears at the very end of the passphrase."""
    for _ in range(10):
        pwd = generate_passphrase(word_dict, 4, False, True)
        assert pwd[-1] in SYMBOLS, f"Expected symbol at very end, got: {pwd}"


def test_passphrase_digit_before_symbol(word_dict):
    """When both requested, digit appears immediately before the symbol at the end."""
    for _ in range(10):
        pwd = generate_passphrase(word_dict, 4, True, True)
        assert pwd[-1] in SYMBOLS, f"Expected symbol at very end, got: {pwd}"
        assert pwd[-2].isdigit(), f"Expected digit before symbol, got: {pwd}"


def test_passphrase_single_word_with_extras(word_dict):
    """Single-word passphrase: extras appended since there are no separators."""
    pwd = generate_passphrase(word_dict, 1, True, True)
    assert any(c.isdigit() for c in pwd)
    assert any(c in SYMBOLS for c in pwd)


def test_passphrase_digit_and_symbol_count(word_dict):
    """Exactly one digit added; symbol is the last character."""
    pwd = generate_passphrase(word_dict, 5, True, True)
    assert sum(c.isdigit() for c in pwd) == 1
    assert pwd[-1] in SYMBOLS


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


# --- API route tests ---

def test_password_route_json(client):
    """JSON response includes all required fields."""
    r = client.get('/password', headers={'Accept': 'application/json'})
    assert r.status_code == 200
    data = r.get_json()
    assert 'password' in data
    assert 'entropy' in data
    assert 'complexity' in data
    assert 'time_to_crack' in data


def test_passphrase_route_json(client):
    """JSON response for passphrase includes password field."""
    r = client.get('/passphrase', headers={'Accept': 'application/json'})
    assert r.status_code == 200
    data = r.get_json()
    assert 'password' in data


def test_password_route_curl(client):
    """curl User-Agent returns plain text with entropy line."""
    r = client.get('/password', headers={'User-Agent': 'curl/7.88.0'})
    assert r.status_code == 200
    assert b'Entropy:' in r.data
    assert r.content_type.startswith('text/plain')


def test_entropy_passphrase_greater_than_password(client):
    """A 6-word passphrase should have higher entropy than an 8-char password."""
    r1 = client.get('/passphrase+6', headers={'Accept': 'application/json'})
    r2 = client.get('/password+8', headers={'Accept': 'application/json'})
    assert r1.get_json()['entropy'] > r2.get_json()['entropy']


def test_random_route_plain(client):
    r = client.get('/random', headers={'User-Agent': 'curl/7.88.0'})
    assert r.status_code == 200
    assert b'Entropy:' in r.data

def test_random_route_with_length(client):
    r = client.get('/random+20', headers={'Accept': 'application/json'})
    data = r.get_json()
    assert len(data['password']) == 20

def test_random_route_with_number(client):
    r = client.get('/random+number', headers={'Accept': 'application/json'})
    data = r.get_json()
    assert any(c.isdigit() for c in data['password'])

def test_random_route_with_symbol(client):
    r = client.get('/random+symbol', headers={'Accept': 'application/json'})
    data = r.get_json()
    assert any(c in SYMBOLS for c in data['password'])

def test_generate_post_password_type(client):
    r = client.post('/generate',
        json={"type": "password", "length": 10, "use_digits": True},
        headers={'Accept': 'application/json'})
    assert r.status_code == 200
    data = r.get_json()
    assert 'password' in data
    assert any(c.isdigit() for c in data['password'])

def test_generate_post_missing_body(client):
    r = client.post('/generate', data='not-json', content_type='text/plain')
    assert r.status_code == 400

def test_passphrase_length_clamped(client):
    r = client.get('/passphrase+99', headers={'Accept': 'application/json'})
    data = r.get_json()
    # Count words by splitting on separators (hyphens or digits or symbols between words)
    import re
    words = re.split(r'[-\d!@#$%^&*()_+=\[\]{}|;:,.<>?]', data['password'])
    words = [w for w in words if w]  # filter empty strings
    assert len(words) <= 20

def test_password_length_clamped(client):
    r = client.get('/password+99', headers={'Accept': 'application/json'})
    data = r.get_json()
    # password length should be capped (letters only portion <= 64)
    import re
    letters_only = re.sub(r'[\d!@#$%^&*()_+=\[\]{}|;:,.<>?]', '', data['password'])
    assert len(letters_only) <= 64


def test_health_route(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}

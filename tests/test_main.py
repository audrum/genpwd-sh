import pytest

from main import app, generate_passphrase, load_eff_wordlist, WORDLIST, SYMBOLS, limiter


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


def test_passphrase_with_digit_sprinkled(word_dict):
    """Digit appears somewhere inside the passphrase, not just at the end."""
    results = [generate_passphrase(word_dict, 6, True, False) for _ in range(20)]
    # At least once the digit should NOT be the very last character
    assert any(not r[-1].isdigit() for r in results), "Digit always at end — not sprinkled"


def test_passphrase_with_symbol_sprinkled(word_dict):
    """Symbol appears somewhere inside the passphrase, not just at the end."""
    results = [generate_passphrase(word_dict, 6, False, True) for _ in range(20)]
    assert any(r[-1] not in SYMBOLS for r in results), "Symbol always at end — not sprinkled"


def test_passphrase_single_word_with_extras(word_dict):
    """Single-word passphrase: extras appended since there are no separators."""
    pwd = generate_passphrase(word_dict, 1, True, True)
    assert any(c.isdigit() for c in pwd)
    assert any(c in SYMBOLS for c in pwd)


def test_passphrase_digit_and_symbol_count(word_dict):
    """Exactly one digit and one symbol inserted."""
    pwd = generate_passphrase(word_dict, 5, True, True)
    assert sum(c.isdigit() for c in pwd) == 1
    assert sum(c in SYMBOLS for c in pwd) == 1


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

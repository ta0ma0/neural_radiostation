import re
from tools.nick_generator import generate_nick, PREFIXES, SUFFIXES


def test_generate_nick_returns_string():
    nick = generate_nick()
    assert isinstance(nick, str)
    assert len(nick) > 0


def test_generate_nick_format():
    nick = generate_nick()
    assert "_" in nick
    parts = nick.split("_", 1)
    assert len(parts) == 2
    assert parts[0] in PREFIXES
    assert parts[1] in SUFFIXES


def test_generate_nick_latin_only():
    for _ in range(50):
        nick = generate_nick()
        assert re.match(r"^[A-Za-z][A-Za-z0-9_]*[A-Za-z0-9]$", nick), f"Unexpected chars: {nick}"


def test_generate_nick_uniqueness():
    generated = {generate_nick() for _ in range(100)}
    assert len(generated) > 1

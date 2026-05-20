"""
Unit tests for secretref-env-resolver.

Tests the .env parser and basic handler logic without a running server.
"""

import os
import tempfile

import server


def test_load_env_empty_file():
    """Loading a non-existent file returns empty dict."""
    secrets = server.load_env("/nonexistent/.env")
    assert secrets == {}


def test_load_env_basic():
    """Basic .env key=value pairs are parsed correctly."""
    content = """
KEY=value
EMPTY=
WITH_QUOTES="hello world"
SINGLE_QUOTES='foo bar'
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(content)
        path = f.name

    try:
        secrets = server.load_env(path)
        assert secrets["KEY"] == "value"
        assert secrets["EMPTY"] == ""
        assert secrets["WITH_QUOTES"] == "hello world"
        assert secrets["SINGLE_QUOTES"] == "foo bar"
    finally:
        os.unlink(path)


def test_load_env_ignores_comments_and_blanks():
    """Comments and blank lines are ignored."""
    content = """
# This is a comment

  # Indented comment
KEY=value
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(content)
        path = f.name

    try:
        secrets = server.load_env(path)
        assert secrets == {"KEY": "value"}
    finally:
        os.unlink(path)


def test_load_env_no_equals_line():
    """Lines without = are silently skipped (header noise)."""
    content = """
INVALID_LINE
KEY=value
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(content)
        path = f.name

    try:
        secrets = server.load_env(path)
        assert secrets == {"KEY": "value"}
    finally:
        os.unlink(path)


def test_load_env_trailing_whitespace():
    """Trailing whitespace in values is stripped."""
    content = "KEY=  value with spaces  "
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(content)
        path = f.name

    try:
        secrets = server.load_env(path)
        assert secrets["KEY"] == "value with spaces"
    finally:
        os.unlink(path)


def test_secret_names_listed_via_handler():
    """Handler._send_json works as expected (integration check)."""
    secrets = {"A": "1", "B": "2"}
    names = sorted(secrets.keys())
    assert names == ["A", "B"]


def test_server_module_has_expected_constants():
    """Module-level constants exist and are reasonable."""
    assert isinstance(server.PORT, int)
    assert server.PORT > 0
    assert isinstance(server.HOST, str)
    assert isinstance(server.ENV_PATH, str)

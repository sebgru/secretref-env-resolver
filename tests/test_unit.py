"""
Unit tests for secretref-env-resolver.

Tests the .env parser and basic handler logic without a running server.
"""

import http.client
import http.server
import json
import os
import tempfile
import threading

import pytest

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


# ---------------------------------------------------------------------------
# HTTP handler integration tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def live_server():
    """Spin up a real HTTP server on a random port; tear it down after the test."""
    _saved = server.SecretRefHandler.secrets
    httpd = http.server.HTTPServer(("127.0.0.1", 0), server.SecretRefHandler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield port
    httpd.shutdown()
    server.SecretRefHandler.secrets = _saved


def _http_get(port: int, path: str):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, resp.getheader("Content-Type") or "", body


def _json_get(port: int, path: str):
    status, ct, body = _http_get(port, path)
    return status, ct, json.loads(body)


def test_handler_root(live_server):
    """GET / returns service info with endpoint list."""
    status, ct, body = _json_get(live_server, "/")
    assert status == 200
    assert "application/json" in ct
    assert body["ok"] is True
    assert "endpoints" in body


def test_handler_health(live_server):
    """GET /health returns ok and a secret count."""
    status, ct, body = _json_get(live_server, "/health")
    assert status == 200
    assert body["ok"] is True
    assert "secret_count" in body


def test_handler_list_empty(live_server):
    """GET /list with no secrets loaded returns an empty list."""
    server.SecretRefHandler.secrets = {}
    status, ct, body = _json_get(live_server, "/list")
    assert status == 200
    assert body["secrets"] == []


def test_handler_list_sorted(live_server):
    """GET /list returns secret names in sorted order, not values."""
    server.SecretRefHandler.secrets = {"ZEBRA": "z", "APPLE": "a"}
    status, ct, body = _json_get(live_server, "/list")
    assert body["secrets"] == ["APPLE", "ZEBRA"]


def test_handler_secret_found(live_server):
    """GET /secret/<name> returns the value as plain text."""
    server.SecretRefHandler.secrets = {"MY_KEY": "supersecret"}
    status, ct, body = _http_get(live_server, "/secret/MY_KEY")
    assert status == 200
    assert "text/plain" in ct
    assert body.strip() == b"supersecret"


def test_handler_secret_not_found(live_server):
    """GET /secret/<name> returns 404 when the name is not present."""
    server.SecretRefHandler.secrets = {}
    status, ct, body = _json_get(live_server, "/secret/MISSING")
    assert status == 404
    assert body["ok"] is False


def test_handler_secret_invalid_name(live_server):
    """GET /secret/<name> with a slash in the name returns 400."""
    status, ct, body = _json_get(live_server, "/secret/foo/bar")
    assert status == 400
    assert body["ok"] is False


def test_handler_secret_empty_name(live_server):
    """GET /secret/ (trailing slash, no name) returns 400."""
    status, ct, body = _json_get(live_server, "/secret/")
    assert status == 400
    assert body["ok"] is False


def test_handler_unknown_endpoint(live_server):
    """Unknown paths return 404."""
    status, ct, body = _json_get(live_server, "/unknown")
    assert status == 404
    assert body["ok"] is False


def test_server_module_has_expected_constants():
    """Module-level constants exist and are reasonable."""
    assert isinstance(server.PORT, int)
    assert server.PORT > 0
    assert isinstance(server.HOST, str)
    assert isinstance(server.ENV_PATH, str)

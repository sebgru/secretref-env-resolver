#!/usr/bin/env python3
"""secretref-env-resolver — lightweight HTTP API for OpenClaw SecretRefs.

Reads secrets from a mounted .env file and exposes them individually via HTTP.
Designed for use with OpenClaw's exec SecretRef type.

Endpoints:
  GET /              — Service info
  GET /health        — Health check
  GET /list          — List available secret names (not values)
  GET /secret/<name> — Return a specific secret value as plain text
"""

import http.server
import json
import os
import sys
import urllib.parse

ENV_PATH = os.environ.get("SECRETREF_ENV_PATH", "/run/secrets/.env")
HOST = os.environ.get("SECRETREF_HOST", "0.0.0.0")  # nosec
PORT = int(os.environ.get("SECRETREF_PORT", "8766"))


def load_env(path: str) -> dict[str, str]:
    """Parse a .env file into a dict. Simple parser, no shell expansion."""
    secrets: dict[str, str] = {}
    if not os.path.isfile(path):
        return secrets
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # Strip surrounding quotes if present
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            if key:
                secrets[key] = val
    return secrets


class SecretRefHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the SecretRef resolver."""

    # Loaded once at startup, cached in-memory
    secrets: dict[str, str] = {}

    def log_message(self, format, *args):  # noqa: A002
        """Suppress default logging to stderr; use sys.stderr.write for silence."""
        pass

    def _send_json(self, data: dict, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode() + b"\n")

    def _send_text(self, text: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(text.encode() + b"\n")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/":
            self._send_json(
                {
                    "ok": True,
                    "service": "secretref-env-resolver",
                    "env_file": ENV_PATH,
                    "secret_count": len(self.secrets),
                    "endpoints": {
                        "GET /": "this help",
                        "GET /health": "health check",
                        "GET /list": "list available secret names",
                        "GET /secret/<name>": "return a specific secret value",
                    },
                }
            )
        elif path == "/health":
            self._send_json(
                {
                    "ok": True,
                    "service": "secretref-env-resolver",
                    "env_file_found": os.path.isfile(ENV_PATH),
                    "secret_count": len(self.secrets),
                }
            )
        elif path == "/list":
            self._send_json(
                {
                    "ok": True,
                    "secrets": sorted(self.secrets.keys()),
                }
            )
        elif path.startswith("/secret/"):
            name = path[len("/secret/") :]
            if not name or "/" in name:
                self._send_json({"ok": False, "error": "invalid secret name"}, 400)
                return
            if name in self.secrets:
                self._send_text(self.secrets[name])
            else:
                self._send_json({"ok": False, "error": "secret not found"}, 404)
        else:
            self._send_json({"ok": False, "error": "not found"}, 404)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


def main() -> None:
    """Start the HTTP server."""
    path = ENV_PATH
    if not os.path.isfile(path):
        print(f"Warning: env file not found at {path}", file=sys.stderr)
    SecretRefHandler.secrets = load_env(path)
    print(
        f"Loaded {len(SecretRefHandler.secrets)} secrets from {path}",
        file=sys.stderr,
    )

    server = http.server.HTTPServer((HOST, PORT), SecretRefHandler)
    print(f"Serving on http://{HOST}:{PORT}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        server.server_close()


if __name__ == "__main__":
    main()

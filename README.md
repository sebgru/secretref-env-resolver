# secretref-env-resolver

![CI](https://github.com/sebgru/secretref-env-resolver/actions/workflows/ci.yml/badge.svg)
![GitHub](https://img.shields.io/github/license/sebgru/secretref-env-resolver.svg)

**Allowlisted read-only OpenClaw SecretRef resolver bridge** — securely exposes named secrets from a mounted `.env` file via HTTP for consumption by OpenClaw's `exec` SecretRef type.

Designed for the same pattern as [nvidia-smi-service](https://github.com/sebgru/nvidia-smi-service): a minimal Docker service with no dependencies, running as non-root.

## How it works

1. A `.env` file is mounted into the container at `/run/secrets/.env`
2. The service parses it and exposes each secret by name via HTTP
3. OpenClaw's SecretRef `exec` runs `curl http://secretref-env-resolver:8766/secret/NAME` to fetch a specific secret

No secrets appear in environment variables, command lines, or logs.

## Quick Start

### 1. Create your .env file

```bash
cp .env.example /secure/path/.secrets.env
chmod 600 /secure/path/.secrets.env
# Edit with your actual secrets
```

### 2. docker-compose

```yaml
services:
  secretref-env-resolver:
    build: .
    container_name: secretref-env-resolver
    restart: unless-stopped
    ports:
      - "8766:8766"
    volumes:
      - /secure/path/.secrets.env:/run/secrets/.env:ro
```

### 3. OpenClaw SecretRef config

In your `openclaw.json`, reference secrets like:

```json
{
  "MY_SECRET": {
    "type": "exec",
    "command": "curl -s -f http://secretref-env-resolver:8766/secret/MY_SECRET"
  }
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info and endpoint list |
| `/health` | GET | Health check |
| `/list` | GET | List available secret names (not values) |
| `/secret/{name}` | GET | Return a specific secret value as plain text |

### Example

```bash
# List available secret names
curl http://localhost:8766/list

# Get a specific secret
curl http://localhost:8766/secret/DB_PASSWORD
```

## Security

- **Read-only**: no POST, PUT, PATCH, or DELETE endpoints
- **Non-root user**: process runs as `appuser`, not root
- **No secret exposure in logs**: only secret *counts* reported at startup
- **Read-only mount**: the `.env` file is mounted with `:ro` to prevent modification
- **No secrets in env vars**: secrets stay in the file, not in container environment

## CI/CD

- **CI** (`ci.yml`): ruff formatting + linting, pytest unit tests, Trivy container security scan
- **docker build** (`docker-image.yml`): verifies clean Docker build
- **docker publish** (`docker-publish.yml`): on version tags, publishes to `ghcr.io/sebgru/secretref-env-resolver`

## License

MIT

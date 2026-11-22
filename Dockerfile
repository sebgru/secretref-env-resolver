FROM python:3.14-slim

# Update all system packages to latest security-patched versions.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY server.py /app/server.py
RUN chmod +x /app/server.py

# ── Strip pip from the runtime image ────────────────────────────────────────
# The service is stdlib-only and pip is never used at runtime. pip ships
# vendored copies of msgpack/urllib3/setuptools that raise HIGH CVEs in image
# scanners, and they can only be fixed by a pip release — which still vendors a
# vulnerable setuptools. Dropping pip removes that attack surface entirely and
# keeps the Trivy gate green.
RUN rm -rf /usr/local/lib/python3.*/site-packages/pip \
           /usr/local/lib/python3.*/site-packages/pip-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.*

# Run as non-root user for security.
RUN adduser --disabled-password --gecos '' appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import os, urllib.request; port = os.environ.get('SECRETREF_PORT', '8766'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health')" || exit 1

ENV SECRETREF_ENV_PATH=/run/secrets/.env
ENV SECRETREF_HOST=0.0.0.0
ENV SECRETREF_PORT=8766

CMD ["python3", "/app/server.py"]

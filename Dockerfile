FROM python:3.14-slim

# Update all system packages to latest security-patched versions.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY server.py /app/server.py
RUN chmod +x /app/server.py

# Run as non-root user for security.
RUN adduser --disabled-password --gecos '' appuser
USER appuser

EXPOSE 8766

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import os, urllib.request; port = os.environ.get('SECRETREF_PORT', '8766'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health')" || exit 1

ENV SECRETREF_ENV_PATH=/run/secrets/.env
ENV SECRETREF_HOST=0.0.0.0
ENV SECRETREF_PORT=8766

CMD ["python3", "/app/server.py"]

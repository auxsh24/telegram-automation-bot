FROM python:3.12-slim AS builder

WORKDIR /app

# Build tools are only needed to compile pydantic-core on architectures that
# have no prebuilt wheel. They never reach the final image.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Retry the install: a slow PyPI mirror otherwise fails the whole build with a
# bare "Read timed out".
COPY requirements.txt .
RUN set -e; \
    for attempt in 1 2 3 4 5; do \
        pip install --no-cache-dir --timeout 120 --retries 10 \
            --prefix=/install -r requirements.txt \
        && break \
        || { echo "pip install failed (attempt ${attempt}/5) - retrying in 10s"; sleep 10; }; \
    done; \
    test -d /install/lib/python3.12/site-packages/fastapi

# Final stage
FROM python:3.12-slim

WORKDIR /app

# curl: container healthcheck. gosu: drop root after the entrypoint fixes
# ownership of the mounted data directory.
RUN apt-get update -qq -o Acquire::Retries=5 \
    && apt-get install -y --no-install-recommends curl gosu \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Run unprivileged: a process holding a Telegram session should not be root.
RUN groupadd --system relay \
    && useradd --system --gid relay --create-home relay \
    && mkdir -p /app/data \
    && chown -R relay:relay /app

COPY --chown=relay:relay . .

# Fix line endings (Windows checkouts) and make the entrypoint executable.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    RELAY_DATA_DIR=/app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

# One worker only: the in-process relay state and the SQLite write path both
# assume a single process. No --reload and no --proxy-headers on purpose;
# the app reads forwarded headers itself for trusted peers only.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "20"]

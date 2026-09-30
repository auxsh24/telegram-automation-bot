FROM python:3.12-slim AS builder

WORKDIR /app

# Build tools are only needed to compile pydantic-core, which has no wheel for
# every architecture. They never reach the final image.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Install dependencies in builder stage
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final stage
FROM python:3.12-slim

WORKDIR /app

# curl is used by the container healthcheck; gosu drops root privileges after
# the entrypoint fixes ownership of the bind-mounted data directory
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Run unprivileged: a process holding a Telegram session has no business being
# root inside its own container
RUN groupadd --system relay \
    && useradd --system --gid relay --create-home relay \
    && mkdir -p /app/data \
    && chown -R relay:relay /app

# Copy application code
COPY --chown=relay:relay . .

# Fix line endings and make entrypoint executable
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

# Runs as root first so it can fix the data directory ownership, then re-execs
# itself as the unprivileged relay user.
ENTRYPOINT ["/app/docker-entrypoint.sh"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    RELAY_DATA_DIR=/app/data

EXPOSE 8000

# Same endpoint the uptime monitor uses, so a container that cannot serve
# requests is restarted instead of sitting there looking alive
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

# No --reload: the autoreloader is a dev tool, and in production it spawns a
# supervisor that can leave an old worker holding the Telegram session after a
# restart. One worker only - the in-process relay state and the SQLite write
# path both assume a single process.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "20"]

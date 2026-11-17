#!/bin/sh
# Container entrypoint.
#
# The container runs as the non-root `relay` user, but /app/data is a bind mount
# owned by whoever created it on the host. Without this step SQLite cannot open
# the database and the container dies on startup with
# "unable to open database file".
#
# The fix is applied as root at startup and then privileges are dropped, so the
# app itself never runs as root.

set -e

DATA_DIR="${RELAY_DATA_DIR:-/app/data}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"

    # Only chown what is needed; -R over a large backup dir is wasteful.
    chown relay:relay "$DATA_DIR" 2>/dev/null || true

    # Re-exec as the unprivileged user so nothing below runs as root.
    exec gosu relay "$0" "$@"
fi

cd /app

exec "$@"

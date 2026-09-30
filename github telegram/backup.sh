#!/usr/bin/env bash
# Daily consistent backup of the relay database.
#
# The relay database holds the processed-message ledger and every setting. If
# the volume is lost, the relay forgets what it already forwarded and will
# re-send today's messages. Run this from cron on the host.
#
#   crontab -e
#   17 3 * * * /opt/telegram-relay-dashboard/backup.sh >> /var/log/relay-backup.log 2>&1

set -euo pipefail

DATA_DIR="${RELAY_DATA_DIR:-/opt/telegram-relay-dashboard/data}"
BACKUP_DIR="${RELAY_BACKUP_DIR:-$DATA_DIR/backups}"
KEEP_DAYS="${RELAY_BACKUP_KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/relay-$STAMP.db"

# The online backup API is used rather than `cp`, because copying the file
# while a write is in flight can capture a half-written WAL.
python3 - "$DATA_DIR/relay.db" "$TARGET" <<'PY'
import sqlite3
import sys

source_path, target_path = sys.argv[1], sys.argv[2]

source = sqlite3.connect(source_path)
target = sqlite3.connect(target_path)
try:
    with target:
        source.backup(target)
finally:
    source.close()
    target.close()

print(f"backup written: {target_path}")
PY

# Keep only the recent window so the backup directory cannot grow forever.
find "$BACKUP_DIR" -name 'relay-*.db' -type f -mtime "+$KEEP_DAYS" -print -delete

echo "backup complete: $TARGET"

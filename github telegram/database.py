import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# The data directory is overridable so the container can point it at the bind
# mount without the code path and the volume path drifting apart.
DATA_DIR = Path(
    os.getenv("RELAY_DATA_DIR")
    or (BASE_DIR / "data")
)

DB_FILE = DATA_DIR / "relay.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)


# SQLite is shared by the HTTP workers and the Telegram listener in the same
# process, so a busy timeout is what keeps a concurrent write from raising
# "database is locked" instead of waiting a few milliseconds.
BUSY_TIMEOUT_MS = 10000


def get_connection():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False,
        timeout=BUSY_TIMEOUT_MS / 1000
    )
    conn.execute("PRAGMA journal_mode=WAL")
    # NORMAL is the recommended durability level in WAL mode: a crash can lose
    # the last transactions but never corrupts the database, and it is far
    # cheaper than fsync-per-commit on a small cloud volume.
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn


def backup_database(destination):
    """Write a consistent copy of the database using SQLite's online backup.

    Copying the file directly can capture a half-written WAL, so the backup
    API is used instead.
    """
    target = sqlite3.connect(destination)
    try:
        source = get_connection()
        try:
            with target:
                source.backup(target)
        finally:
            source.close()
    finally:
        target.close()
    return destination


def init_database():
    db = get_connection()

    # App settings
    db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Processed Telegram messages
    db.execute("""
        CREATE TABLE IF NOT EXISTS processed_messages (
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            processed_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'sent',
            PRIMARY KEY (channel_id, message_id)
        )
    """)

    # Activity logs
    db.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at INTEGER NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)

    # Retention deletes scan by created_at, and the statistics/cleanup
    # queries filter processed_messages by processed_at. Both indexes matter
    # once the relay has been running for a while.
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at
        ON activity_logs (created_at)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_processed_messages_processed_at
        ON processed_messages (processed_at)
        """
    )

    db.commit()
    db.close()


# -------------------------
# Settings
# -------------------------

def set_setting(key, value):
    db = get_connection()

    db.execute(
        """
        INSERT OR REPLACE INTO settings (key, value)
        VALUES (?, ?)
        """,
        (key, str(value))
    )

    db.commit()
    db.close()


def get_setting(key, default=None):
    db = get_connection()

    row = db.execute(
        """
        SELECT value
        FROM settings
        WHERE key = ?
        """,
        (key,)
    ).fetchone()

    db.close()

    if row is None:
        return default

    return row[0]


def get_all_settings():
    db = get_connection()

    rows = db.execute(
        """
        SELECT key, value
        FROM settings
        """
    ).fetchall()

    db.close()

    return dict(rows)


# -------------------------
# Processed messages
# -------------------------

# Row states used by the processed_messages table.
#   pending -> the message is being forwarded right now (claimed)
#   sent    -> the message was forwarded successfully
#   failed  -> the last attempt failed, so it may be retried later
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"


def is_processed(channel_id, message_id):
    """True if the message was sent already or is being sent right now."""
    db = get_connection()

    row = db.execute(
        """
        SELECT 1
        FROM processed_messages
        WHERE channel_id = ?
        AND message_id = ?
        AND status IN (?, ?)
        """,
        (channel_id, message_id, STATUS_SENT, STATUS_PENDING)
    ).fetchone()

    db.close()

    return row is not None


def claim_message(channel_id, message_id):
    """Reserve a message for sending so it can never be forwarded twice.

    Returns True when the caller owns the message and may forward it, or
    False when it was already sent (or is currently in flight). Failed
    messages are claimable again so they can be retried later.
    """
    db = get_connection()

    try:
        # Serialize the status check and claim so live events and history scans
        # cannot both claim the same message.
        db.execute("BEGIN IMMEDIATE")

        row = db.execute(
            """
            SELECT status
            FROM processed_messages
            WHERE channel_id = ?
            AND message_id = ?
            """,
            (channel_id, message_id)
        ).fetchone()

        now = int(time.time())

        if row is None:
            db.execute(
                """
                INSERT INTO processed_messages
                (channel_id, message_id, processed_at, status)
                VALUES (?, ?, ?, ?)
                """,
                (channel_id, message_id, now, STATUS_PENDING)
            )
        elif row[0] == STATUS_FAILED:
            db.execute(
                """
                UPDATE processed_messages
                SET processed_at = ?, status = ?
                WHERE channel_id = ?
                AND message_id = ?
                AND status = ?
                """,
                (now, STATUS_PENDING, channel_id, message_id, STATUS_FAILED)
            )
            if db.total_changes == 0:
                db.rollback()
                return False
        else:
            db.rollback()
            return False

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def release_stale_claims(max_age_seconds=1800):
    """Turn abandoned claims into retryable failures.

    If the process crashes (or is restarted) between claiming a message and
    finishing the send, that row would stay "pending" forever and the message
    would look like a duplicate. Anything older than max_age_seconds is
    therefore released so the relay can retry it.

    Returns the number of released rows.
    """
    cutoff = int(time.time()) - int(max_age_seconds)

    db = get_connection()

    cursor = db.execute(
        """
        UPDATE processed_messages
        SET status = ?
        WHERE status = ?
        AND processed_at < ?
        """,
        (STATUS_FAILED, STATUS_PENDING, cutoff)
    )

    released = cursor.rowcount

    db.commit()
    db.close()

    return released


def mark_processed(channel_id, message_id, status=STATUS_SENT):
    db = get_connection()

    db.execute(
        """
        INSERT OR REPLACE INTO processed_messages
        (channel_id, message_id, processed_at, status)
        VALUES (?, ?, ?, ?)
        """,
        (
            channel_id,
            message_id,
            int(time.time()),
            status
        )
    )

    db.commit()
    db.close()


# -------------------------
# Logs
# -------------------------

def add_log(level, message):
    db = get_connection()

    db.execute(
        """
        INSERT INTO activity_logs
        (created_at, level, message)
        VALUES (?, ?, ?)
        """,
        (
            int(time.time()),
            level,
            message
        )
    )

    db.commit()
    db.close()


def get_recent_logs(limit=100):
    db = get_connection()

    rows = db.execute(
        """
        SELECT id, created_at, level, message
        FROM activity_logs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

    db.close()

    return rows


def get_logs_since(since_timestamp, limit=200):
    """Get logs created after the given timestamp (newest first)."""
    db = get_connection()
    rows = db.execute(
        """
        SELECT id, created_at, level, message
        FROM activity_logs
        WHERE created_at > ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (since_timestamp, limit)
    ).fetchall()
    db.close()
    return rows


def get_logs_after_id(log_id, limit=200):
    """Get logs newer than the given row id (newest first).

    Polling by autoincrement id instead of a timestamp makes sure no log is
    skipped when several events happen within the same second.
    """
    db = get_connection()
    rows = db.execute(
        """
        SELECT id, created_at, level, message
        FROM activity_logs
        WHERE id > ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (log_id, limit)
    ).fetchall()
    db.close()
    return rows


def cleanup_old_logs(retention_days=1):
    """Delete logs older than retention_days. Returns count of deleted rows.

    A retention of 0 (or less) means "keep every log", so nothing is deleted.
    """
    if int(retention_days) <= 0:
        return 0

    cutoff = int((datetime.now() - timedelta(days=retention_days)).timestamp())
    db = get_connection()
    cursor = db.execute(
        "DELETE FROM activity_logs WHERE created_at < ?",
        (cutoff,)
    )
    deleted = cursor.rowcount
    db.commit()
    db.close()
    return deleted


# -------------------------
# Statistics
# -------------------------

def get_today_stats(start_timestamp):
    db = get_connection()

    total_processed = db.execute(
        """
        SELECT COUNT(*)
        FROM processed_messages
        WHERE processed_at >= ?
        """,
        (start_timestamp,)
    ).fetchone()[0]

    sent = db.execute(
        """
        SELECT COUNT(*)
        FROM processed_messages
        WHERE processed_at >= ?
        AND status = 'sent'
        """,
        (start_timestamp,)
    ).fetchone()[0]

    failed = db.execute(
        """
        SELECT COUNT(*)
        FROM processed_messages
        WHERE processed_at >= ?
        AND status = 'failed'
        """,
        (start_timestamp,)
    ).fetchone()[0]

    db.close()

    return {
        "processed": total_processed,
        "sent": sent,
        "failed": failed
    }


init_database()
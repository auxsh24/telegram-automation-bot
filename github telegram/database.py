import os
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

# SQLite only: a single file inside the data directory.
import sqlite3

BUSY_TIMEOUT_MS = 10000

def get_connection():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False,
        timeout=BUSY_TIMEOUT_MS / 1000
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn

def backup_database(destination):
    """Write a consistent copy of the database using SQLite's online backup."""
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

    db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS processed_messages (
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            processed_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'sent',
            PRIMARY KEY (channel_id, message_id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at INTEGER NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)

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

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"

def is_processed(channel_id, message_id):
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
    db = get_connection()
    try:
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

def delete_old_processed(cutoff):
    db = get_connection()
    cursor = db.execute(
        """
        DELETE FROM processed_messages
        WHERE processed_at < ?
        """,
        (int(cutoff),)
    )
    deleted = cursor.rowcount
    db.commit()
    db.close()
    return deleted

def release_stale_claims(max_age_seconds=1800):
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
        (channel_id, message_id, int(time.time()), status)
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
        (int(time.time()), level, message)
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

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

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# Database Backend Selection
# ==========================================
# DATABASE_URL empty → SQLite (local dev / single container)
# DATABASE_URL set   → PostgreSQL (cloud / multi-instance)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

IS_POSTGRES = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")

if IS_POSTGRES:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,  # serverless-friendly: no connection pool
        connect_args={"connect_timeout": 10},
    )

    def _run(sql, params=None):
        """Execute a query and return rows as list of dicts."""
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            conn.commit()
            if result.returns_rows:
                return [dict(row._mapping) for row in result]
            return []

    def _run_one(sql, params=None):
        """Execute a query and return the first row as dict, or None."""
        rows = _run(sql, params)
        return rows[0] if rows else None

    def _execute(sql, params=None):
        """Execute a statement (INSERT/UPDATE/DELETE) and return rowcount."""
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            conn.commit()
            return result.rowcount

    def get_connection():
        """Compatibility shim — returns a context manager for SQLite-style code."""
        return engine.connect()

    def backup_database(destination):
        """PostgreSQL: use pg_dump. SQLite: use online backup API."""
        import subprocess
        try:
            result = subprocess.run(
                ["pg_dump", DATABASE_URL, "-f", str(destination)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                raise RuntimeError(f"pg_dump failed: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError("pg_dump not found. Install postgresql-client.")
        return destination

    def init_database():
        # App settings
        _execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Processed Telegram messages
        _execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                processed_at BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'sent',
                PRIMARY KEY (channel_id, message_id)
            )
        """)

        # Activity logs
        _execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id BIGSERIAL PRIMARY KEY,
                created_at BIGINT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)

        # Indexes
        _execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at
            ON activity_logs (created_at)
        """)
        _execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_messages_processed_at
            ON processed_messages (processed_at)
        """)

    # -------------------------
    # Settings
    # -------------------------

    def set_setting(key, value):
        _execute("""
            INSERT INTO settings (key, value)
            VALUES (:key, :value)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, {"key": key, "value": str(value)})

    def get_setting(key, default=None):
        row = _run_one("SELECT value FROM settings WHERE key = :key", {"key": key})
        return row["value"] if row else default

    def get_all_settings():
        rows = _run("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in rows}

    # -------------------------
    # Processed messages
    # -------------------------

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"

    def is_processed(channel_id, message_id):
        row = _run_one("""
            SELECT 1 FROM processed_messages
            WHERE channel_id = :cid AND message_id = :mid
            AND status IN (:sent, :pending)
        """, {"cid": channel_id, "mid": message_id, "sent": STATUS_SENT, "pending": STATUS_PENDING})
        return row is not None

    def claim_message(channel_id, message_id):
        now = int(time.time())
        try:
            # Try to claim: insert as pending, or update failed → pending
            result = _execute("""
                INSERT INTO processed_messages (channel_id, message_id, processed_at, status)
                VALUES (:cid, :mid, :now, :pending)
                ON CONFLICT (channel_id, message_id) DO UPDATE
                SET processed_at = EXCLUDED.processed_at,
                    status = EXCLUDED.status
                WHERE processed_messages.status = :failed
            """, {"cid": channel_id, "mid": message_id, "now": now,
                  "pending": STATUS_PENDING, "failed": STATUS_FAILED})
            return result > 0
        except Exception:
            raise

    def release_stale_claims(max_age_seconds=1800):
        cutoff = int(time.time()) - int(max_age_seconds)
        return _execute("""
            UPDATE processed_messages
            SET status = :failed
            WHERE status = :pending AND processed_at < :cutoff
        """, {"failed": STATUS_FAILED, "pending": STATUS_PENDING, "cutoff": cutoff})

    def mark_processed(channel_id, message_id, status=STATUS_SENT):
        _execute("""
            INSERT INTO processed_messages (channel_id, message_id, processed_at, status)
            VALUES (:cid, :mid, :now, :status)
            ON CONFLICT (channel_id, message_id) DO UPDATE
            SET processed_at = EXCLUDED.processed_at,
                status = EXCLUDED.status
        """, {"cid": channel_id, "mid": message_id, "now": int(time.time()), "status": status})

    # -------------------------
    # Logs
    # -------------------------

    def add_log(level, message):
        _execute("""
            INSERT INTO activity_logs (created_at, level, message)
            VALUES (:now, :level, :message)
        """, {"now": int(time.time()), "level": level, "message": message})

    def get_recent_logs(limit=100):
        rows = _run("""
            SELECT id, created_at, level, message
            FROM activity_logs
            ORDER BY id DESC
            LIMIT :limit
        """, {"limit": limit})
        return [(r["id"], r["created_at"], r["level"], r["message"]) for r in rows]

    def get_logs_since(since_timestamp, limit=200):
        rows = _run("""
            SELECT id, created_at, level, message
            FROM activity_logs
            WHERE created_at > :since
            ORDER BY id DESC
            LIMIT :limit
        """, {"since": since_timestamp, "limit": limit})
        return [(r["id"], r["created_at"], r["level"], r["message"]) for r in rows]

    def get_logs_after_id(log_id, limit=200):
        rows = _run("""
            SELECT id, created_at, level, message
            FROM activity_logs
            WHERE id > :log_id
            ORDER BY id DESC
            LIMIT :limit
        """, {"log_id": log_id, "limit": limit})
        return [(r["id"], r["created_at"], r["level"], r["message"]) for r in rows]

    def cleanup_old_logs(retention_days=1):
        if int(retention_days) <= 0:
            return 0
        cutoff = int((datetime.now() - timedelta(days=retention_days)).timestamp())
        return _execute(
            "DELETE FROM activity_logs WHERE created_at < :cutoff",
            {"cutoff": cutoff}
        )

    # -------------------------
    # Statistics
    # -------------------------

    def get_today_stats(start_timestamp):
        total = _run_one("""
            SELECT COUNT(*) as cnt FROM processed_messages
            WHERE processed_at >= :start
        """, {"start": start_timestamp})
        sent = _run_one("""
            SELECT COUNT(*) as cnt FROM processed_messages
            WHERE processed_at >= :start AND status = 'sent'
        """, {"start": start_timestamp})
        failed = _run_one("""
            SELECT COUNT(*) as cnt FROM processed_messages
            WHERE processed_at >= :start AND status = 'failed'
        """, {"start": start_timestamp})
        return {
            "processed": total["cnt"] if total else 0,
            "sent": sent["cnt"] if sent else 0,
            "failed": failed["cnt"] if failed else 0
        }

else:
    # ==========================================
    # SQLite Backend (default)
    # ==========================================
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

import asyncio
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient, events, utils
from telethon.errors import (
    FloodWaitError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
)

import database


BASE_DIR = Path(__file__).resolve().parent

# Must resolve to the same place database.py uses, otherwise the session file
# and the database would end up in different directories.
DATA_DIR = database.DATA_DIR
SESSION_FILE = DATA_DIR / "telegram_session"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# Telegram asks a client to slow down when it sends too fast. Short waits are
# honoured automatically, longer ones abort the send so the relay is never
# blocked for minutes. MAX_FLOOD_WAITS caps waits per single message.
MAX_FLOOD_WAIT_SECONDS = 300
MAX_FLOOD_WAITS = 2

# How often expired duplicate rows / abandoned claims are cleaned up.
CLEANUP_INTERVAL_SECONDS = 300

# How often the background loops tick.
MAINTENANCE_INTERVAL_SECONDS = 900
WATCHDOG_INTERVAL_SECONDS = 60


class TelegramService:

    def __init__(self):
        self.client = None

        # Authentication state
        self.phone = None
        self.phone_code_hash = None

        # Relay state
        self.monitoring = False
        self.monitoring_started_at = None
        self.event_handler = None
        self.monitor_entities = []

        # Throttles the duplicate cleanup query (it used to run per message)
        self.last_cleanup_at = 0.0

        # Prevents two Analyze Today operations at once
        self.analysis_lock = asyncio.Lock()

        # Observability: the dashboard needs to tell "relay is running" apart
        # from "Telegram connection dropped an hour ago".
        self.last_error = None
        self.last_sent_at = None
        self.messages_sent = 0
        self.messages_failed = 0
        self.started_at = None

        # The auto-resume flag is persisted, so a container restart brings the
        # relay back up without anyone clicking "Start Monitor" again.
        self.background_tasks = []

    # =========================================================
    # CONFIGURATION
    # =========================================================

    async def configure(self, api_id, api_hash):

        api_hash = str(api_hash or "").strip()
        api_id = int(api_id)

        if api_id <= 0:
            raise ValueError(
                "API ID must be a positive number."
            )

        if len(api_hash) < 10:
            raise ValueError(
                "API hash looks invalid."
            )

        previous_api_id = database.get_setting("telegram_api_id")
        previous_api_hash = database.get_setting("telegram_api_hash")

        if (
            self.client is not None
            and (
                previous_api_id != str(api_id)
                or previous_api_hash != api_hash
            )
        ):
            await self.stop_monitoring()

            if self.client.is_connected():
                await self.client.disconnect()

            self.client = None
            self.phone = None
            self.phone_code_hash = None

        database.set_setting(
            "telegram_api_id",
            str(api_id)
        )

        database.set_setting(
            "telegram_api_hash",
            api_hash
        )

    def create_client(self):

        api_id = database.get_setting(
            "telegram_api_id"
        )

        api_hash = database.get_setting(
            "telegram_api_hash"
        )

        if not api_id or not api_hash:
            raise ValueError(
                "Telegram API credentials are not configured."
            )

        # Cloud deployment: session string from env survives restarts.
        # Local dev: session file in data/ directory.
        session_string = os.getenv("TELEGRAM_SESSION_STRING", "").strip()

        if session_string:
            from telethon.sessions import StringSession
            self.client = TelegramClient(
                StringSession(session_string),
                int(api_id),
                api_hash
            )
        else:
            self.client = TelegramClient(
                str(SESSION_FILE),
                int(api_id),
                api_hash
            )

        return self.client

    async def connect(self):

        if self.client is None:
            self.create_client()

        if not self.client.is_connected():
            await self.client.connect()

        return await self.client.is_user_authorized()

    async def is_authorized(self):

        if self.client is None:
            if (
                not database.get_setting("telegram_api_id")
                or not database.get_setting("telegram_api_hash")
            ):
                return False

            self.create_client()

        if not self.client.is_connected():
            await self.client.connect()

        return await self.client.is_user_authorized()

    # =========================================================
    # TELEGRAM AUTHENTICATION
    # =========================================================

    @staticmethod
    def normalize_phone(phone):
        """Remove spaces/dashes and force a leading '+' so Telegram accepts it."""
        cleaned = re.sub(r"[\s\-().]", "", str(phone or ""))

        if cleaned and not cleaned.startswith("+"):
            cleaned = "+" + cleaned

        return cleaned

    async def send_code(self, phone):

        if self.client is None:
            self.create_client()

        if not self.client.is_connected():
            await self.client.connect()

        phone = self.normalize_phone(phone)

        if len(phone) < 8:
            raise ValueError(
                "Enter a valid phone number in international format, "
                "for example +919876543210."
            )

        self.phone = phone
        self.phone_code_hash = None

        result = await self.client.send_code_request(
            phone
        )

        self.phone_code_hash = result.phone_code_hash

        # Returned so the caller can store the normalized number.
        return phone

    async def verify_code(self, code):

        if self.client is None:
            raise RuntimeError(
                "Telegram client is not initialized."
            )

        if not self.phone:
            raise RuntimeError(
                "Phone number is missing."
            )

        if not self.phone_code_hash:
            raise RuntimeError(
                "Verification code was not requested."
            )

        # Codes are numeric; users often paste them with spaces or dashes.
        code = re.sub(r"[^0-9]", "", str(code or ""))

        if not code:
            raise RuntimeError(
                "Please enter the verification code from Telegram."
            )

        try:

            await self.client.sign_in(
                phone=self.phone,
                code=code,
                phone_code_hash=self.phone_code_hash
            )

            self.phone_code_hash = None

            return {
                "success": True,
                "requires_2fa": False
            }

        except SessionPasswordNeededError:

            return {
                "success": False,
                "requires_2fa": True
            }

        except PhoneCodeInvalidError:

            return {
                "success": False,
                "requires_2fa": False,
                "error": "Invalid verification code."
            }

        except PhoneCodeExpiredError:

            self.phone_code_hash = None

            return {
                "success": False,
                "requires_2fa": False,
                "error": "Verification code expired."
            }

    async def verify_2fa(self, password):

        if self.client is None:
            raise RuntimeError(
                "Telegram client is not initialized."
            )

        await self.client.sign_in(
            password=password
        )

        return True

    async def get_me(self):

        if self.client is None:
            raise RuntimeError(
                "Telegram client is not initialized."
            )

        return await self.client.get_me()

    async def disconnect(self, clear_auto_resume=True):

        # Forwarded so a shutdown disconnect does not wipe the flag, while an
        # operator pressing "Disconnect Account" still stops auto-resuming.
        await self.stop_monitoring(
            clear_auto_resume=clear_auto_resume
        )

        if self.client is not None:
            await self.client.disconnect()

    # =========================================================
    # SETTINGS
    # =========================================================

    def get_converter_bot(self):

        return database.get_setting(
            "converter_bot",
            "@ExtraPeBot"
        )

    def get_source_channels(self):

        raw = database.get_setting(
            "source_channels",
            "[]"
        )

        try:

            channels = json.loads(raw)

            if not isinstance(channels, list):
                return []

            return [
                str(channel).strip()
                for channel in channels
                if str(channel).strip()
            ]

        except json.JSONDecodeError:

            return []

    @staticmethod
    def _as_int(value, default):
        """Settings are stored as text, so never let a bad value crash a send."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_retry_settings(self):

        attempts = self._as_int(
            database.get_setting(
                "retry_attempts",
                "3"
            ),
            3
        )

        delay = self._as_int(
            database.get_setting(
                "retry_delay_seconds",
                "2"
            ),
            2
        )

        return max(1, attempts), max(0, delay)

    def get_duplicate_ttl(self):

        return self._as_int(
            database.get_setting(
                "duplicate_ttl_days",
                "1"
            ),
            1
        )

    # =========================================================
    # LOGGING
    # =========================================================

    def log(self, level, message):

        print(
            f"[{level.upper()}] {message}",
            flush=True
        )

        # The last error is surfaced in the UI so a silent relay failure is
        # visible without digging through the activity log.
        if level == "error":
            self.last_error = {
                "message": str(message),
                "at": int(time.time())
            }

        elif level == "success":
            self.last_error = None

        database.add_log(
            level,
            message
        )

    # =========================================================
    # BACKGROUND MAINTENANCE
    # =========================================================

    async def run_maintenance_loop(self):
        """Apply log retention and release stale claims on a timer.

        The relay used to rely on someone pressing "Clear Old Logs", which
        means a long-running unattended instance grows the log table forever.
        """
        while True:
            try:
                await asyncio.sleep(MAINTENANCE_INTERVAL_SECONDS)

                retention_days = self._as_int(
                    database.get_setting(
                        "log_retention_days",
                        "1"
                    ),
                    1
                )

                deleted = database.cleanup_old_logs(
                    retention_days
                )

                if deleted:
                    self.log(
                        "info",
                        (
                            f"Automatic log retention removed "
                            f"{deleted} entr(y/ies) older than "
                            f"{retention_days} day(s)."
                        )
                    )

                self.cleanup_old_processed(force=True)

            except asyncio.CancelledError:
                raise

            except Exception as error:

                # A failing maintenance tick must never take the process down.
                self.log(
                    "error",
                    f"Maintenance tick failed: {error}"
                )

    async def run_watchdog_loop(self):
        """Reconnect to Telegram and resume the relay if the link drops.

        A mobile-quality connection or a cloud VM restart can silently drop the
        MTProto connection; without this the dashboard would keep claiming the
        relay is running while nothing is forwarded.
        """
        while True:
            try:
                await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)

                if not self.monitoring:
                    continue

                if (
                    self.client is None
                    or not self.client.is_connected()
                ):
                    self.log(
                        "warning",
                        "Telegram connection lost. Reconnecting..."
                    )

                    if self.client is None:
                        self.create_client()

                    await self.client.connect()

                    if not await self.client.is_user_authorized():
                        self.log(
                            "error",
                            (
                                "Telegram session is no longer authorized. "
                                "Reconnect the account from the dashboard."
                            )
                        )
                        self.monitoring = False
                        database.set_setting(
                            "auto_resume",
                            "0"
                        )
                        continue

                    # Re-attach the handler to the freshly connected client,
                    # otherwise messages would be silently ignored.
                    entities = (
                        await self.resolve_source_channels()
                    )

                    self.monitor_entities = entities

                    if self.event_handler:
                        self.client.add_event_handler(
                            self.event_handler,
                            events.NewMessage(
                                chats=entities
                            )
                        )

                    self.monitoring = True
                    self.monitoring_started_at = int(time.time())

                    self.log(
                        "success",
                        "Telegram reconnected and monitoring resumed."
                    )

            except asyncio.CancelledError:
                raise

            except Exception as error:
                self.log(
                    "error",
                    f"Watchdog tick failed: {error}"
                )

    def start_background_tasks(self):
        for target in (
            self.run_maintenance_loop,
            self.run_watchdog_loop
        ):
            self.background_tasks.append(
                asyncio.create_task(target())
            )

    async def stop_background_tasks(self):
        for task in self.background_tasks:
            task.cancel()

        self.background_tasks = []

    def set_auto_resume(self, enabled):
        database.set_setting(
            "auto_resume",
            "1" if enabled else "0"
        )

    def get_auto_resume(self):
        return database.get_setting(
            "auto_resume",
            "0"
        ) in {"1", "true", "yes"}

    async def resume_if_needed(self):
        """Restore monitoring after a restart when it was running before.

        Called from the app startup hook. Without this, every deploy or crash
        would silently stop the relay until someone opened the dashboard.
        """
        if not self.get_auto_resume():
            return False

        if not database.get_setting("telegram_api_id"):
            return False

        try:
            if not await self.is_authorized():
                return False

            await self.start_monitoring()

            self.log(
                "success",
                "Monitoring auto-resumed after restart."
            )

            return True

        except Exception as error:
            self.log(
                "error",
                f"Could not auto-resume monitoring: {error}"
            )
            return False

    # =========================================================
    # DATABASE CLEANUP
    # =========================================================

    def cleanup_old_processed(self, force=False):
        """Drop expired duplicate rows and release abandoned claims.

        This used to run a DELETE for every single processed message. The
        duplicate TTL is measured in days, so running it a few times per hour
        is more than enough.
        """
        now = time.time()

        if not force and (now - self.last_cleanup_at) < CLEANUP_INTERVAL_SECONDS:
            return

        self.last_cleanup_at = now

        # Keep at least one day of history, otherwise every message would
        # look new again on the next scan.
        ttl_days = max(1, self.get_duplicate_ttl())

        cutoff = int(
            now
            - (
                ttl_days
                * 24
                * 60
                * 60
            )
        )

        db = database.get_connection()

        db.execute(
            """
            DELETE FROM processed_messages
            WHERE processed_at < ?
            """,
            (cutoff,)
        )

        db.commit()
        db.close()

        # If the process died mid-send, that claim is stale and the message
        # should be retryable instead of looking like a duplicate forever.
        released = database.release_stale_claims()

        if released:
            self.log(
                "info",
                f"Released {released} unfinished message(s) for retry."
            )

    # =========================================================
    # TELEGRAM ENTITY RESOLUTION
    # =========================================================

    async def resolve_source_channels(self):

        if not await self.is_authorized():

            raise RuntimeError(
                "Telegram account is not authenticated."
            )

        channels = self.get_source_channels()

        if not channels:

            raise ValueError(
                "No source channels configured."
            )

        entities = []

        for channel in channels:

            try:

                entity = await self.client.get_entity(
                    channel
                )

                entities.append(entity)

                self.log(
                    "info",
                    f"Source resolved: {channel}"
                )

            except Exception as error:

                # One broken channel must not stop the whole relay, so keep
                # going and report the problem in the activity log.
                self.log(
                    "error",
                    (
                        f"Could not resolve "
                        f"{channel}: {error}"
                    )
                )

        if not entities:

            raise ValueError(
                "None of the configured source channels could be resolved. "
                "Check the usernames and that this account is a member."
            )

        if len(entities) < len(channels):

            self.log(
                "info",
                (
                    f"Using {len(entities)} of {len(channels)} "
                    f"configured source channel(s)."
                )
            )

        return entities

    # =========================================================
    # SEND MESSAGE TO CONVERTER
    # =========================================================

    async def send_to_converter(self, message):

        if self.client is None:

            raise RuntimeError(
                "Telegram client is not initialized. "
                "Connect your account first."
            )

        converter_bot = self.get_converter_bot()

        attempts, initial_delay = (
            self.get_retry_settings()
        )

        last_error = None
        attempt = 1
        flood_waits = 0

        while attempt <= attempts:

            try:

                await self.client.send_message(
                    converter_bot,
                    message
                )

                return True

            except FloodWaitError as error:

                # Telegram tells us exactly how long to wait, so honour it
                # instead of hammering the API and risking a longer ban.
                wait_seconds = int(
                    getattr(error, "seconds", 0) or 0
                )

                if (
                    wait_seconds > MAX_FLOOD_WAIT_SECONDS
                    or flood_waits >= MAX_FLOOD_WAITS
                ):

                    last_error = error

                    self.log(
                        "error",
                        (
                            f"Flood wait of {wait_seconds}s is too "
                            f"long, skipping this message."
                        )
                    )

                    break

                flood_waits += 1

                self.log(
                    "warning",
                    (
                        f"Telegram rate limit: waiting "
                        f"{wait_seconds + 1}s before retrying."
                    )
                )

                await asyncio.sleep(
                    wait_seconds + 1
                )

                # A flood wait does not consume a retry attempt.
                continue

            except Exception as error:

                last_error = error

                self.log(
                    "error",
                    (
                        f"Send attempt "
                        f"{attempt}/{attempts} failed: "
                        f"{error}"
                    )
                )

                if attempt < attempts:

                    delay = (
                        initial_delay
                        * (
                            2 ** (attempt - 1)
                        )
                    )

                    await asyncio.sleep(
                        delay
                    )

                attempt += 1

        self.log(
            "error",
            f"Message delivery failed: {last_error}"
        )

        return False

    # =========================================================
    # PROCESS ONE MESSAGE
    # =========================================================

    async def process_message(
        self,
        message,
        channel_id=None
    ):

        if channel_id is None:
            channel_id = message.chat_id

        message_id = message.id

        self.cleanup_old_processed()

        # Claim the message before sending it. Both the live handler and a
        # history scan can reach the same message at the same time, and only
        # one of them may forward it.
        if not database.claim_message(
            channel_id,
            message_id
        ):

            self.log(
                "info",
                (
                    f"Skipped duplicate | "
                    f"channel={channel_id} | "
                    f"message={message_id}"
                )
            )

            return "duplicate"

        self.log(
            "info",
            (
                f"Processing | "
                f"channel={channel_id} | "
                f"message={message_id}"
            )
        )

        success = await self.send_to_converter(
            message
        )

        if success:

            database.mark_processed(
                channel_id,
                message_id,
                database.STATUS_SENT
            )

            self.messages_sent += 1
            self.last_sent_at = int(time.time())

            self.log(
                "success",
                (
                    f"Sent | "
                    f"channel={channel_id} | "
                    f"message={message_id} | "
                    f"converter="
                    f"{self.get_converter_bot()}"
                )
            )

            return "sent"

        # The attempt failed. The row is kept as "failed" so the statistics
        # show it, but a later scan is allowed to claim and retry it.
        database.mark_processed(
            channel_id,
            message_id,
            database.STATUS_FAILED
        )

        self.messages_failed += 1

        self.log(
            "error",
            (
                f"Send failed | "
                f"channel={channel_id} | "
                f"message={message_id} | "
                f"will retry later"
            )
        )

        return "failed"

    # =========================================================
    # ANALYZE TODAY
    # =========================================================

    async def analyze_today(self):

        async with self.analysis_lock:

            if not await self.is_authorized():

                raise RuntimeError(
                    "Telegram account is not authenticated."
                )

            # Clear any stale claims left by a crash or restart before we start
            # scanning, so abandoned in-flight messages are retryable immediately.
            self.cleanup_old_processed(force=True)

            entities = (
                await self.resolve_source_channels()
            )

            self.log(
                "info",
                "Starting today's message analysis..."
            )

            # Use computer's local timezone.
            local_now = (
                datetime.now().astimezone()
            )

            start_local = local_now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            end_local = (
                start_local
                + timedelta(days=1)
            )

            start_utc = (
                start_local.astimezone(
                    timezone.utc
                )
            )

            end_utc = (
                end_local.astimezone(
                    timezone.utc
                )
            )

            total = 0
            sent = 0
            duplicate = 0
            failed = 0

            # Scan every configured source independently.
            for entity in entities:

                channel_name = (
                    getattr(
                        entity,
                        "username",
                        None
                    )
                    or getattr(
                        entity,
                        "title",
                        None
                    )
                    or str(entity.id)
                )

                channel_id = utils.get_peer_id(
                    entity
                )

                self.log(
                    "info",
                    (
                        f"Scanning today: "
                        f"{channel_name}"
                    )
                )

                channel_total = 0
                channel_sent = 0
                channel_duplicate = 0
                channel_failed = 0

                # Collect today's messages first, because Telegram returns
                # them newest -> oldest.
                todays_messages = []

                async for message in (
                    self.client.iter_messages(
                        entity,
                        offset_date=end_utc
                    )
                ):

                    if not message.date:
                        continue

                    message_date = message.date

                    if message_date.tzinfo is None:

                        message_date = (
                            message_date.replace(
                                tzinfo=timezone.utc
                            )
                        )

                    # Telegram returns newest -> oldest.
                    # Once we reach before today's start,
                    # this channel is completely scanned.
                    if message_date < start_utc:

                        break

                    if message_date >= end_utc:

                        continue

                    todays_messages.append(message)

                # Forward oldest -> newest so the converter bot receives the
                # posts in the same order they were published.
                todays_messages.reverse()

                for message in todays_messages:

                    channel_total += 1
                    total += 1

                    result = (
                        await self.process_message(
                            message,
                            channel_id
                        )
                    )

                    if result == "sent":

                        sent += 1
                        channel_sent += 1

                    elif result == "duplicate":

                        duplicate += 1
                        channel_duplicate += 1

                    elif result == "failed":

                        failed += 1
                        channel_failed += 1

                self.log(
                    "info",
                    (
                        f"Finished {channel_name} | "
                        f"total={channel_total} | "
                        f"sent={channel_sent} | "
                        f"duplicates="
                        f"{channel_duplicate} | "
                        f"failed={channel_failed}"
                    )
                )

            self.log(
                "info",
                (
                    "Today's analysis finished | "
                    f"total={total} | "
                    f"sent={sent} | "
                    f"duplicates={duplicate} | "
                    f"failed={failed}"
                )
            )

            # Automatically start live monitoring after today's scan, so new
            # messages keep flowing without another click.
            await self.start_monitoring(
                entities=entities
            )

            return {
                "total": total,
                "sent": sent,
                "duplicate": duplicate,
                "failed": failed,
                "monitoring": True
            }

    # =========================================================
    # LIVE MONITORING
    # =========================================================

    async def start_monitoring(
        self,
        entities=None
    ):

        if self.monitoring:

            return {
                "success": True,
                "already_running": True
            }

        if not await self.is_authorized():

            raise RuntimeError(
                "Telegram account is not authenticated."
            )

        if entities is None:

            entities = (
                await self.resolve_source_channels()
            )

        if not entities:

            raise ValueError(
                "No source channels configured."
            )

        self.monitor_entities = entities

        async def new_message_handler(event):

            try:

                await self.process_message(
                    event.message,
                    event.chat_id
                )

            except Exception as error:

                self.log(
                    "error",
                    (
                        "Live message handler error: "
                        f"{error}"
                    )
                )

        self.event_handler = (
            new_message_handler
        )

        self.client.add_event_handler(
            self.event_handler,
            events.NewMessage(
                chats=self.monitor_entities
            )
        )

        self.monitoring = True
        self.monitoring_started_at = int(time.time())
        self.set_auto_resume(True)

        self.log(
            "success",
            (
                f"Live monitoring is running for "
                f"{len(self.monitor_entities)} channel(s)."
            )
        )

        return {
            "success": True,
            "monitoring": True,
            "channels": len(self.monitor_entities)
        }

    # =========================================================
    # STOP MONITORING
    # =========================================================

    async def stop_monitoring(self, clear_auto_resume=True):

        """Stop live monitoring.

        clear_auto_resume distinguishes an operator pressing "Stop Monitor" from
        the process shutting down. Without it, every restart would run the
        shutdown path, wipe the persisted flag, and auto-resume could never
        fire again.
        """
        was_monitoring = self.monitoring

        if (
            self.client is not None
            and self.event_handler is not None
        ):

            self.client.remove_event_handler(
                self.event_handler
            )

        self.event_handler = None
        self.monitor_entities = []
        self.monitoring = False
        self.monitoring_started_at = None

        # Persist the stop so a restart does not silently undo it, but only
        # when an operator asked for it.
        if clear_auto_resume:
            self.set_auto_resume(False)

        # Only log when the relay was actually running, otherwise every
        # disconnect would add a pointless "stopped" entry.
        if was_monitoring:

            self.log(
                "info",
                "Live monitoring stopped."
            )

        return {
            "success": True,
            "monitoring": False
        }

    # =========================================================
    # STATUS
    # =========================================================

    def get_monitoring_status(self):

        connected = bool(
            self.client is not None
            and self.client.is_connected()
        )

        return {
            "monitoring": self.monitoring,
            "channels": len(self.monitor_entities),
            "started_at": self.monitoring_started_at,
            "connected": connected,
            "auto_resume": self.get_auto_resume(),
            "uptime_seconds": (
                int(time.time()) - self.started_at
                if self.started_at
                else 0
            ),
            "sent_this_run": self.messages_sent,
            "failed_this_run": self.messages_failed,
            "last_sent_at": self.last_sent_at,
            "last_error": self.last_error
        }


telegram_service = TelegramService()

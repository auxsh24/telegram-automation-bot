from pathlib import Path
import base64
import binascii
import hmac
import json
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import database
from telegram_service import telegram_service


BASE_DIR = Path(__file__).resolve().parent


# -------------------------
# Logging
# -------------------------
# Structured, unbuffered logging is what makes `docker logs` usable in
# production; the relay writes every event to the activity table as well, but a
# container restart would otherwise leave no trace of why it died.
import logging

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s %(levelname)-8s %(name)s "
        "%(message)s"
    )
)

logger = logging.getLogger("relay")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Own the long-lived resources for the whole process.

    Uvicorn reloads and restarts the container freely; anything that must
    survive or be restored belongs here rather than at import time.
    """
    telegram_service.started_at = int(time.time())
    telegram_service.start_background_tasks()

    # Restoring monitoring can touch the network, so it runs as a background
    # task: a slow Telegram handshake must not delay the health endpoint.
    resume_task = None

    try:
        import asyncio

        resume_task = asyncio.create_task(
            telegram_service.resume_if_needed()
        )

    except Exception as error:
        logger.warning("Could not schedule auto-resume: %s", error)

    logger.info("Telegram Relay Dashboard started")

    try:
        yield

    finally:
        if resume_task is not None:
            resume_task.cancel()

        try:
            await telegram_service.stop_background_tasks()

            # clear_auto_resume=False: shutting down is not the same as an
            # operator pressing "Stop Monitor". Clearing the flag here would
            # make the relay forget it should restart, so the next boot would
            # never resume.
            await telegram_service.stop_monitoring(
                clear_auto_resume=False
            )
            await telegram_service.disconnect(
                clear_auto_resume=False
            )

        except Exception as error:
            logger.warning("Shutdown cleanup issue: %s", error)

        logger.info("Telegram Relay Dashboard stopped")


def setting_int(key, default):
    """Settings are stored as text, so fall back to the default on bad data."""
    try:
        return int(database.get_setting(key, str(default)))
    except (TypeError, ValueError):
        return default


def env_flag(key, default=False):
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {
        "1",
        "true",
        "yes",
        "on"
    }


app = FastAPI(
    title="Telegram Relay Dashboard",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)


class RelayAuthMiddleware(BaseHTTPMiddleware):
    """Require operator credentials before exposing the dashboard or API.

    Basic auth is a stop-gap, not a real identity system, so this middleware
    also throttles repeated failures. Without that, an exposed instance is a
    free brute-force target.
    """

    # In-memory, per-process. A single worker is the documented deployment, and
    # it is enough to make online guessing impractical.
    MAX_ATTEMPTS = 8
    WINDOW_SECONDS = 300
    LOCKOUT_SECONDS = 900

    def __init__(self, app, max_attempts=None, window_seconds=None, lockout_seconds=None):
        super().__init__(app)
        self.max_attempts = int(max_attempts or os.getenv("RELAY_MAX_ATTEMPTS") or self.MAX_ATTEMPTS)
        self.window_seconds = int(window_seconds or os.getenv("RELAY_RATE_WINDOW") or self.WINDOW_SECONDS)
        self.lockout_seconds = int(lockout_seconds or os.getenv("RELAY_LOCKOUT_SECONDS") or self.LOCKOUT_SECONDS)
        self._failures = defaultdict(list)
        self._locked_until = {}

    def _client_key(self, request):
        """Identify the caller.

        The proxy address is preferred so every request is counted separately
        behind a tunnel, and only a direct connection falls back to a shared
        bucket.
        """
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _retry_after(self, key):
        locked_until = self._locked_until.get(key)
        if not locked_until:
            return 0
        remaining = int(locked_until - time.time())
        if remaining <= 0:
            self._locked_until.pop(key, None)
            self._failures.pop(key, None)
            return 0
        return remaining

    def _register_failure(self, key):
        now = time.time()
        attempts = [
            stamp
            for stamp in self._failures.get(key, [])
            if now - stamp < self.window_seconds
        ]
        attempts.append(now)
        self._failures[key] = attempts

        if len(attempts) >= self.max_attempts:
            self._locked_until[key] = now + self.lockout_seconds
            # Bound the map so a botnet cannot grow it without limit.
            if len(self._failures) > 5000:
                self._failures.clear()
            return True
        return False

    def _clear_failures(self, key):
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # The health probe must answer before any auth decision, otherwise an
        # orchestrator cannot tell a locked-out app from a dead one.
        if path == "/api/health":
            return await call_next(request)

        configured_username = os.getenv("RELAY_USERNAME")
        configured_password = os.getenv("RELAY_PASSWORD")
        auth_disabled = env_flag("RELAY_AUTH_DISABLED") or not configured_username and not configured_password

        if auth_disabled:
            return await call_next(request)

        if not configured_username or not configured_password:
            return JSONResponse(
                {
                    "detail": (
                        "Both RELAY_USERNAME and RELAY_PASSWORD must be "
                        "configured together."
                    )
                },
                status_code=503,
            )

        key = self._client_key(request)
        retry_after = self._retry_after(key)

        if retry_after > 0:
            logger.warning(
                "Auth locked out for %s, retry in %ss",
                key,
                retry_after
            )
            response = self._unauthorized(
                "Too many failed attempts. Try again later."
            )
            response.headers["Retry-After"] = str(retry_after)
            return response

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Basic "):
            return self._unauthorized()

        try:
            encoded_credentials = authorization[6:].strip()
            decoded_credentials = base64.b64decode(
                encoded_credentials,
                validate=True,
            ).decode("utf-8")
            username, password = decoded_credentials.split(":", 1)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return self._unauthorized()

        valid_username = hmac.compare_digest(username, configured_username)
        valid_password = hmac.compare_digest(password, configured_password)

        if not (valid_username and valid_password):
            locked = self._register_failure(key)
            logger.warning(
                "Failed auth attempt from %s (%s)",
                key,
                "locked out" if locked else "throttled"
            )
            return self._unauthorized()

        self._clear_failures(key)

        return await call_next(request)

    @staticmethod
    def _unauthorized(detail="Authentication required."):
        response = JSONResponse(
            {"detail": detail},
            status_code=401,
        )
        response.headers["WWW-Authenticate"] = (
            'Basic realm="Telegram Relay Dashboard", charset="UTF-8"'
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline hardening headers.

    The dashboard is normally served over a TLS tunnel in front of the app, so
    these headers are what stop a browser from doing anything useful with a
    stolen session or an injected page.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "img-src 'self' data:; "
                "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
                "font-src 'self' https://fonts.gstatic.com; "
                "script-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        )

        return response


# Added last so it wraps the auth middleware: security headers are applied to
# the 401 responses too.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RelayAuthMiddleware)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)


@app.get("/")
async def root():
    # The shell must never be cached, otherwise a deploy keeps serving an old
    # bundle next to new assets.
    return FileResponse(
        BASE_DIR / "templates" / "index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )


class SetupRequest(BaseModel):
    api_id: int = Field(gt=0)
    api_hash: str = Field(min_length=10, max_length=128)


class PhoneRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=32)


class CodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class TwoFARequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class RelaySettings(BaseModel):
    converter_bot: str = Field(
        min_length=1,
        max_length=64
    )
    source_channels: list[str] = Field(
        max_length=50
    )
    duplicate_ttl_days: int = Field(
        default=1,
        ge=1,
        le=365
    )
    retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10
    )
    retry_delay_seconds: int = Field(
        default=2,
        ge=0,
        le=300
    )
    log_retention_days: int = Field(
        default=1,
        ge=0,
        le=365
    )
    auto_resume: bool = False


@app.get("/api/health")
async def health():
    """Liveness/readiness probe for the container and any uptime monitor.

    Deliberately unauthenticated and free of Telegram calls: it must answer
    fast and must not report a false negative just because the relay is
    paused.
    """
    return {
        "status": "ok",
        "version": "1.0.0",
        "uptime_seconds": (
            int(time.time()) - telegram_service.started_at
            if telegram_service.started_at
            else 0
        ),
        "monitoring": telegram_service.monitoring
    }


@app.get("/api/status")
async def status():
    authorized = await telegram_service.is_authorized()

    return {
        "telegram_authorized": authorized
    }


@app.post("/api/setup")
async def setup(request: SetupRequest):
    try:
        await telegram_service.configure(
            api_id=request.api_id,
            api_hash=request.api_hash
        )

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "success": True
    }


@app.post("/api/telegram/send-code")
async def send_code(request: PhoneRequest):
    try:
        phone = await telegram_service.send_code(request.phone)

        database.set_setting(
            "telegram_phone",
            phone
        )

        return {
            "success": True
        }

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.post("/api/telegram/verify-code")
async def verify_code(request: CodeRequest):
    try:
        result = await telegram_service.verify_code(request.code)

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    # An invalid or expired code is a failed request, not a successful one.
    if not result.get("success") and not result.get("requires_2fa"):

        raise HTTPException(
            status_code=400,
            detail=result.get("error") or "Verification failed."
        )

    return {
        "success": True,
        "requires_2fa": bool(result.get("requires_2fa"))
    }


@app.post("/api/telegram/verify-2fa")
async def verify_2fa(request: TwoFARequest):
    try:
        await telegram_service.verify_2fa(request.password)

        return {
            "success": True
        }

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.get("/api/telegram/account")
async def account():
    try:
        me = await telegram_service.get_me()

        return {
            "authorized": True,
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name
        }

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# -------------------------
# Activity & Stats
# -------------------------

@app.get("/api/activity")
async def get_activity(since: float | None = None, after_id: int | None = None):
    """Newest log entries first.

    after_id is the preferred cursor for live polling, because two events can
    share the same timestamp and a timestamp filter would silently skip one.
    """
    try:
        if after_id is not None:
            logs = database.get_logs_after_id(after_id)
        elif since is not None:
            logs = database.get_logs_since(since)
        else:
            logs = database.get_recent_logs(100)
        return {
            "logs": [
                {
                    "id": log[0],
                    "created_at": log[1],
                    "level": log[2],
                    "message": log[3]
                }
                for log in logs
            ]
        }
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.get("/api/stats")
async def get_stats():
    try:
        now = datetime.now().astimezone()
        start_of_day = int(
            now.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(timezone.utc)
            .timestamp()
        )
        stats = database.get_today_stats(start_of_day)
        return stats
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# -------------------------
# Manual test send
# -------------------------

@app.post("/api/relay/send-test")
async def send_test():
    try:
        if not await telegram_service.is_authorized():
            raise RuntimeError(
                "Telegram account is not authenticated."
            )

        test_message = (
            f"Test message | "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        success = await telegram_service.send_to_converter(
            test_message
        )

        if success:
            return {
                "success": True,
                "message": "Test message sent to converter bot."
            }
        else:
            return {
                "success": False,
                "message": "Failed to send test message."
            }

    except Exception as error:
        database.add_log(
            "error",
            f"Test send failed: {error}"
        )
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.post("/api/telegram/disconnect")
async def disconnect():
    try:
        await telegram_service.disconnect()
        return {
            "success": True,
            "message": "Disconnected."
        }
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# -------------------------
# Relay control
# -------------------------

@app.get("/api/relay/status")
async def relay_status():
    return telegram_service.get_monitoring_status()


@app.post("/api/relay/analyze")
async def relay_analyze():
    try:
        result = await telegram_service.analyze_today()

        return {
            "success": True,
            **result
        }

    except Exception as error:
        database.add_log(
            "error",
            f"Analyze failed: {error}"
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.post("/api/relay/start")
async def relay_start():
    try:
        result = await telegram_service.start_monitoring()

        return result

    except Exception as error:
        database.add_log(
            "error",
            f"Start monitoring failed: {error}"
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@app.post("/api/relay/stop")
async def relay_stop():
    try:
        result = await telegram_service.stop_monitoring()

        return result

    except Exception as error:
        database.add_log(
            "error",
            f"Stop monitoring failed: {error}"
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# -------------------------
# Relay settings
# -------------------------

@app.get("/api/settings")
async def get_settings():

    source_channels_raw = database.get_setting(
        "source_channels",
        "[]"
    )

    try:
        source_channels = json.loads(source_channels_raw)
    except json.JSONDecodeError:
        source_channels = []

    if not isinstance(source_channels, list):
        source_channels = []

    return {
        "converter_bot": database.get_setting(
            "converter_bot",
            "@ExtraPeBot"
        ),
        "source_channels": source_channels,
        "duplicate_ttl_days": setting_int(
            "duplicate_ttl_days",
            1
        ),
        "retry_attempts": setting_int(
            "retry_attempts",
            3
        ),
        "retry_delay_seconds": setting_int(
            "retry_delay_seconds",
            2
        ),
        "log_retention_days": setting_int(
            "log_retention_days",
            1
        ),
        "auto_resume": telegram_service.get_auto_resume()
    }


@app.post("/api/settings")
async def save_settings(request: RelaySettings):

    converter_bot = request.converter_bot.strip()

    if not converter_bot:
        raise HTTPException(
            status_code=400,
            detail="Converter bot username is required."
        )

    channels = []

    for channel in request.source_channels:
        channel = channel.strip()

        if channel and channel not in channels:
            channels.append(channel)

    database.set_setting(
        "converter_bot",
        converter_bot
    )

    database.set_setting(
        "source_channels",
        json.dumps(channels)
    )

    database.set_setting(
        "duplicate_ttl_days",
        request.duplicate_ttl_days
    )

    database.set_setting(
        "retry_attempts",
        request.retry_attempts
    )

    database.set_setting(
        "retry_delay_seconds",
        request.retry_delay_seconds
    )

    database.set_setting(
        "log_retention_days",
        request.log_retention_days
    )

    database.set_setting(
        "auto_resume",
        "1" if request.auto_resume else "0"
    )

    # A running monitor keeps the channels it resolved at start time.
    restart_required = telegram_service.monitoring

    if restart_required:
        database.add_log(
            "info",
            (
                "Settings saved. Restart monitoring so the new "
                "channels take effect."
            )
        )

    return {
        "success": True,
        "message": "Settings saved.",
        "restart_required": restart_required
    }


@app.post("/api/logs/cleanup")
async def cleanup_logs():
    """Delete logs older than log_retention_days setting. Returns count deleted."""
    retention_days = setting_int(
        "log_retention_days",
        1
    )

    if retention_days <= 0:
        return {
            "success": True,
            "deleted_count": 0,
            "retention_days": 0,
            "skipped": True,
            "message": (
                "Log retention is set to keep every log, "
                "so nothing was deleted."
            )
        }

    deleted = database.cleanup_old_logs(retention_days)

    database.add_log(
        "info",
        (
            f"Cleaned up {deleted} old log(s) "
            f"(retention: {retention_days} day(s))"
        )
    )

    return {
        "success": True,
        "deleted_count": deleted,
        "retention_days": retention_days
    }

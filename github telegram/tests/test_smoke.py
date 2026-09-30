"""End-to-end checks for the deployed app surface.

Every test runs against a scratch database, so the real relay.db and the saved
Telegram session are never touched.

    .venv/Scripts/python.exe -m tests.test_smoke
"""
import base64
import os
import sys
import tempfile

# The app resolves its data directory at import time, so the environment has to
# be set before anything from the project is imported.
_TMP = tempfile.mkdtemp(prefix="relay-smoke-")
os.environ.setdefault("RELAY_DATA_DIR", _TMP)
os.environ["RELAY_USERNAME"] = "operator"
os.environ["RELAY_PASSWORD"] = "a-strong-test-password"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
import database  # noqa: E402

database.DATA_DIR = os.path.join(_TMP, "data")
database.DB_FILE = os.path.join(database.DATA_DIR, "relay.db")
os.makedirs(database.DATA_DIR, exist_ok=True)
database.init_database()

from fastapi.testclient import TestClient  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(b"operator:a-strong-test-password").decode()}

failures = []


def check(label, condition, detail=""):
    if not condition:
        failures.append(label)
    print(f"[{'PASS' if condition else 'FAIL'}] {label} {detail}")


with TestClient(app_module.app) as client:
    # Health must answer without credentials, or an orchestrator cannot tell a
    # locked-out app from a dead one.
    response = client.get("/api/health")
    check("health is unauthenticated", response.status_code == 200, response.text)
    check("health reports a version", "version" in response.json())

    # Auth.
    check("settings reject anonymous", client.get("/api/settings").status_code == 401)
    wrong = {"Authorization": "Basic " + base64.b64encode(b"operator:wrong").decode()}
    check("settings reject a wrong password", client.get("/api/settings", headers=wrong).status_code == 401)
    check("settings accept valid credentials", client.get("/api/settings", headers=AUTH).status_code == 200)

    # Settings round trip.
    payload = {
        "converter_bot": "@TestBot",
        "source_channels": ["@one", "@two", "@one", "  "],
        "duplicate_ttl_days": 2,
        "retry_attempts": 4,
        "retry_delay_seconds": 3,
        "log_retention_days": 7,
        "auto_resume": True,
    }
    check("settings save", client.post("/api/settings", json=payload, headers=AUTH).status_code == 200)

    saved = client.get("/api/settings", headers=AUTH).json()
    check("auto_resume persisted", saved["auto_resume"] is True)
    check("channels de-duplicated and trimmed", saved["source_channels"] == ["@one", "@two"], str(saved["source_channels"]))

    # A value outside the documented range must be refused, not clamped.
    check("out-of-range setting rejected", client.post("/api/settings", json={**payload, "retry_attempts": 99}, headers=AUTH).status_code == 422)

    # Relay surface.
    response = client.get("/api/relay/status", headers=AUTH)
    check("relay status exposes health fields", response.status_code == 200 and "uptime_seconds" in response.json())

    check("activity cursor works", client.get("/api/activity?after_id=0", headers=AUTH).status_code == 200)
    check("bad cursor is a 422", client.get("/api/activity?since=abc", headers=AUTH).status_code == 422)
    check("stats", client.get("/api/stats", headers=AUTH).status_code == 200)
    check("log cleanup", client.post("/api/logs/cleanup", headers=AUTH).status_code == 200)

    # Shell delivery and hardening headers.
    check("index requires auth", client.get("/").status_code == 401)
    response = client.get("/", headers=AUTH)
    check("index served", response.status_code == 200)
    check("index is not cached", "no-cache" in response.headers.get("cache-control", ""))
    check("X-Frame-Options", response.headers.get("x-frame-options") == "DENY")
    check("CSP present", "default-src" in response.headers.get("content-security-policy", ""))
    check("nosniff present", response.headers.get("x-content-type-options") == "nosniff")
    check("static assets served", client.get("/static/app.js", headers=AUTH).status_code == 200)

print()
if failures:
    print(f"{len(failures)} check(s) FAILED: {failures}")
    sys.exit(1)

print("All checks passed.")

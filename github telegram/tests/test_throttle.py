"""Verifies the auth throttle locks a client out, recovers, and resets.

An exposed dashboard is a brute-force target without this, so the behaviour is
pinned by a test rather than by a comment.

    .venv/Scripts/python.exe -m tests.test_throttle
"""
import base64
import os
import sys
import tempfile
import time

_TMP = tempfile.mkdtemp(prefix="relay-throttle-")
os.environ["RELAY_USERNAME"] = "operator"
os.environ["RELAY_PASSWORD"] = "a-strong-test-password"
os.environ["RELAY_MAX_ATTEMPTS"] = "3"
os.environ["RELAY_LOCKOUT_SECONDS"] = "2"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
import database  # noqa: E402

database.DATA_DIR = os.path.join(_TMP, "data")
database.DB_FILE = os.path.join(database.DATA_DIR, "relay.db")
os.makedirs(database.DATA_DIR, exist_ok=True)
database.init_database()

from fastapi.testclient import TestClient  # noqa: E402

WRONG = {"Authorization": "Basic " + base64.b64encode(b"operator:wrong").decode()}
RIGHT = {"Authorization": "Basic " + base64.b64encode(b"operator:a-strong-test-password").decode()}

results = {}

with TestClient(app_module.app) as client:
    for _ in range(3):
        client.get("/api/settings", headers=WRONG)

    response = client.get("/api/settings", headers=RIGHT)
    results["locked"] = response.status_code == 401 and response.headers.get("Retry-After") is not None

    time.sleep(2.5)
    results["recovered"] = client.get("/api/settings", headers=RIGHT).status_code == 200

    # A successful sign-in must clear the counter, otherwise a legitimate user
    # who mistyped once stays one mistake away from a lockout.
    for _ in range(2):
        client.get("/api/settings", headers=WRONG)
    client.get("/api/settings", headers=RIGHT)
    response = client.get("/api/settings", headers=WRONG)
    results["reset"] = response.status_code == 401 and not response.headers.get("Retry-After")

for name, passed in results.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")

if all(results.values()):
    print("\nThrottle behaviour correct.")
    sys.exit(0)

print("\nThrottle behaviour FAILED", results)
sys.exit(1)

"""Auto-resume must survive a restart.

The relay used to persist an "auto_resume" flag, but the shutdown path called
stop_monitoring(), which cleared it again. The net effect was that the flag
could never survive a restart and the whole feature was inert.

This test drives the real lifespan startup/shutdown cycle and asserts the flag
is still set afterwards.

    .venv/Scripts/python.exe -m tests.test_auto_resume
"""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="relay-resume-")
os.environ["RELAY_DATA_DIR"] = _TMP

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
import database  # noqa: E402
import telegram_service as ts_module  # noqa: E402

database.DATA_DIR = ts_module.database.DATA_DIR = os.path.join(_TMP, "data")
database.DB_FILE = os.path.join(database.DATA_DIR, "relay.db")
ts_module.SESSION_FILE = os.path.join(database.DATA_DIR, "telegram_session")
os.makedirs(database.DATA_DIR, exist_ok=True)
database.init_database()

service = ts_module.telegram_service

# No Telegram credentials here, so resume_if_needed is a no-op. What is being
# tested is that the shutdown path leaves the flag alone.
database.set_setting("auto_resume", "1")
print("flag before restart:", service.get_auto_resume())

import asyncio  # noqa: E402


async def run_cycle():
    async with app_module.lifespan(app_module.app):
        pass


asyncio.run(run_cycle())

after = service.get_auto_resume()
raw = database.get_setting("auto_resume")

print("flag after shutdown:", after, "| raw DB value:", repr(raw))

passed = after is True and raw == "1"
print(f"[{'PASS' if passed else 'FAIL'}] auto_resume survives a restart")

# The operator path must still be able to turn it off.
asyncio.run(service.stop_monitoring())
cleared = service.get_auto_resume() is False
print(f"[{'PASS' if cleared else 'FAIL'}] explicit stop still clears the flag")

if passed and cleared:
    print("\nAuto-resume behaviour correct.")
    sys.exit(0)

print("\nAuto-resume behaviour FAILED")
sys.exit(1)

"""Verifies retention runs on a timer and the auto-resume flag persists.

The relay is expected to run unattended, so neither behaviour may depend on
someone opening the dashboard.

    .venv/Scripts/python.exe -m tests.test_maintenance
"""
import asyncio
import os
import sys
import tempfile
import time

_TMP = tempfile.mkdtemp(prefix="relay-maint-")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
import telegram_service as ts_module  # noqa: E402

database.DATA_DIR = os.path.join(_TMP, "data")
database.DB_FILE = os.path.join(database.DATA_DIR, "relay.db")
os.makedirs(database.DATA_DIR, exist_ok=True)
database.init_database()

service = ts_module.telegram_service

# Tick fast so the loop runs inside the test instead of after 15 minutes.
ts_module.MAINTENANCE_INTERVAL_SECONDS = 0.2

old = int(time.time()) - (5 * 24 * 60 * 60)
for _ in range(5):
    database.add_log("info", "old entry")

connection = database.get_connection()
connection.execute("UPDATE activity_logs SET created_at = ?", (old,))
connection.commit()
connection.close()

database.set_setting("log_retention_days", "1")
before = len(database.get_recent_logs(limit=1000))


async def main():
    task = asyncio.create_task(service.run_maintenance_loop())
    await asyncio.sleep(1.0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


asyncio.run(main())

after = len(database.get_recent_logs(limit=1000))
retention_ok = after < before
print(f"[{'PASS' if retention_ok else 'FAIL'}] retention removed old rows automatically ({before} -> {after})")

service.set_auto_resume(True)
persist_on = service.get_auto_resume() is True
service.set_auto_resume(False)
persist_off = service.get_auto_resume() is False
print(f"[{'PASS' if persist_on else 'FAIL'}] auto_resume persists as True")
print(f"[{'PASS' if persist_off else 'FAIL'}] auto_resume persists as False")

if retention_ok and persist_on and persist_off:
    print("\nMaintenance behaviour correct.")
    sys.exit(0)

print("\nMaintenance behaviour FAILED")
sys.exit(1)

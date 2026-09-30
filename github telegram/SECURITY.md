# Security Policy

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a security problem.

Email the maintainer instead, or use GitHub's private reporting
("Security" tab → "Report a vulnerability") on this repository.

Include: what you found, how to reproduce it, and what an attacker gains.
You can expect an acknowledgement within a few days.

## What counts as a vulnerability

- Authentication bypass — reaching the dashboard or any `/api/*` endpoint without valid credentials
- The auth lockout being avoidable, or `RELAY_AUTH_DISABLED` being honoured in a way it shouldn't be
- Any path that leaks `data/telegram_session`, `.env`, or database contents to an unauthorised caller
- Stored/reflected XSS in the dashboard (log messages, channel names, Telegram profile names)
- Anything that lets an attacker read or write another user's Telegram session

## Non-vulnerabilities

- Running out of memory or disk on a very small VM
- Telegram rate-limit / `FloodWaitError` behaviour
- Your own account being rate-limited or banned by Telegram for forwarding too much
- Weak *your* password, or deploying without HTTPS behind your own choice

## Handling secrets safely

Two files in this project are live credentials. **Never commit either one.**

| File | What it is |
|---|---|
| `.env` | Dashboard username and password |
| `data/telegram_session` | A logged-in Telegram session — anyone holding it can act as you |

`data/telegram_session` is the important one: it is a full Telegram login, not a
hash. If you ever committed it, treat the account as compromised — log out of
Telegram everywhere ("Terminate other sessions") rather than just deleting the
file.

If a session file is exposed, deleting the commit is not enough. The object
stays in the repository history and on every fork and clone.

# Telegram Relay Dashboard

A self-hosted dashboard that forwards messages from Telegram channels to a
converter bot. FastAPI + SQLite + Telethon on the backend, a dependency-free
frontend, and Docker for deployment.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-required-2496ED.svg)](https://docs.docker.com/get-docker/)

> **Two files in this project are live credentials. Never commit either one:**
> `.env` (your dashboard password) and `data/telegram_session` (a logged-in
> Telegram session — whoever holds it can act as you). See [Security](#security).

---

## Table of contents

- [What it does](#what-it-does)
- [Features](#features)
- [Quick start (Docker)](#quick-start-docker)
- [Windows / PowerShell](#windows--powershell)
- [Creating `.env`](#creating-env)
- [Connecting Telegram](#connecting-telegram)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [Project layout](#project-layout)
- [Deployment](#deployment)
- [Backups](#backups)
- [Tests](#tests)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

---

## What it does

You point it at one or more source channels and one destination bot. It watches
the sources, and every new message is forwarded to the destination.

```
  @source_channel_1  ──┐
  @source_channel_2  ──┼──►  Telegram Relay  ──►  @your_converter_bot
  @source_channel_3  ──┘      (this project)
```

Two ways it moves messages:

| | **Analyze Today** | **Live monitoring** |
|---|---|---|
| What it reads | Messages already published today | Messages published from now on |
| Order | Oldest → newest, so the destination sees them in publication order | As they arrive |
| Duplicates | Skipped | Skipped |
| Duration | Seconds to minutes, depending on volume | Runs in the background until stopped |

Analyzing also starts live monitoring afterwards, so new messages keep flowing
without a second click.

---

## Features

**Relay**

- Live monitoring of any number of source channels
- Backfill of a full day, per channel, in publication order
- Duplicate throttle backed by an atomic SQLite claim — a message can never be
  forwarded twice, even if a live event and a history scan reach it at the same moment
- Failed messages are retryable; abandoned claims from a crash are released
  automatically so nothing gets stuck as a permanent "duplicate"
- Exponential backoff between retries, and `FloodWaitError` honoured without
  consuming a retry attempt
- **Auto-resume** — relay state is persisted, so a container or VM restart brings
  the relay back on its own
- **Watchdog** — a dropped MTProto connection is detected and re-established
  within 60 seconds instead of silently stopping delivery
- If the session is no longer authorized, the relay stops and says so rather
  than claiming to run

**Dashboard**

- Live activity feed, polled on an incrementing log id so no entry is ever
  skipped when several happen in the same second
- Today's processed / sent / failed counters, animated on update
- Relay health card: connection state, uptime, sent/failed this run, last
  delivery, last error
- Dark and light themes, following the system preference by default
- Offline banner, request timeouts, and a custom confirm dialog for anything
  destructive
- Log retention from 1 day to "keep all", applied automatically in the
  background — you do not have to press a cleanup button

**Operations**

- HTTP Basic auth with per-client throttling and lockout
- Security headers (CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`)
- Unauthenticated `/api/health` probe for uptime monitors and Docker healthchecks
- Runs as an unprivileged user inside the container
- WAL-safe database backups, with a cron installer
- Four test suites that need no test runner

---

## Quick start (Docker)

### 1. Get the project

```bash
git clone https://github.com/auxsh24/telegram-automation-bot.git
cd telegram-automation-bot
```

The application lives in the `github telegram/` subfolder. Every command below
is run from there:

```bash
cd "github telegram"
```

### 2. Create `.env`

**Do this before the first `docker compose up`.** `docker-compose.yml` declares
`env_file: .env`, so a missing file makes the whole command fail immediately with
`env file .env not found`.

```bash
nano .env          # or: notepad .env on Windows
```

Copy the template from [Creating `.env`](#creating-env) — it lists every variable
with its purpose. The two required ones are:

```dotenv
RELAY_USERNAME="your-username"
RELAY_PASSWORD="use-a-long-random-password"
```

Generate a good password:

```bash
openssl rand -base64 24 | tr -d '\n/+=' | head -c 28
```

The app refuses to serve (`503`) unless both `RELAY_USERNAME` and
`RELAY_PASSWORD` are set, and refuses to start at all unless the file exists.

### 3. Build and start

```bash
docker compose up --build -d
```

The first build takes a few minutes because it downloads base images. On ARM
(Oracle Cloud) `pydantic` compiles from source, so allow 3–5 minutes. After it,
`docker compose ps` should show `Up ... (healthy)`.

### 4. Confirm it actually came up

```bash
docker compose ps                                  # STATUS = Up (healthy)
docker compose logs --tail=20                      # "started"
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/health   # 200
```

`200` is what you want. `401` means your `.env` credentials are wrong; `000`
means the container is not up yet — read `docker compose logs` first, because
the most common cause on a fresh clone is a malformed `.env`.

### 5. Open it

Go to `http://localhost:8000` and sign in with your `.env` credentials.

### 6. Configure the relay

In the dashboard:

1. Set **Converter Bot** — where messages should be delivered (defaults to
   `@ExtraPeBot`)
2. Add your **Source Channels** — `@channel_username`, one per line
3. Press **Analyze Today** for a backfill, or **Start Monitor** to go live
4. Make sure **Auto-resume after restart** is on

The Activity panel shows everything the relay is doing, in real time.

---

## Windows / PowerShell

The commands above are POSIX. On PowerShell, four things differ:

```powershell
cd D:\telegram-automation-bot
cd "github telegram"

# curl's -o /dev/null is a POSIX path — use NUL
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8000/api/health

# run the four test suites
foreach ($t in @('smoke','auto_resume','throttle','maintenance')) {
  .\.venv\Scripts\python.exe -m "tests.test_$t"
  if ($LASTEXITCODE -ne 0) { "FAILED: $t" }
}

# generate a random password
$b = New-Object byte[] 18
[System.Security.Cryptography.RandomNumberGenerator]::Fill($b)
[Convert]::ToBase64String($b).TrimEnd('=').Replace('+','').Replace('/','')
```

PowerShell has no `cp`, so create `.env` in a text editor (Notepad, VS Code)
rather than copying a template file.

---

## Creating `.env`

`.env` lives in the project folder (`github telegram/.env`), one variable per
line, `KEY="value"` with double quotes. Full template:

```dotenv
# --- Dashboard login (required) -------------------------------------------
# Without both of these the app answers 503 instead of falling open.
RELAY_USERNAME="your-username"
RELAY_PASSWORD="use-a-long-random-password"

# --- Telegram API credentials ---------------------------------------------
# Get these from my.telegram.org -> API development tools.
API_ID="             "
API_HASH="                          "

# --- Optional ---------------------------------------------------------------
# Set to 1 to disable auth entirely. Trusted local machines only.
# RELAY_AUTH_DISABLED="0"

# Failed logins before lockout, the length of the rate-limit window in seconds,
# and how long a lockout lasts.
# RELAY_MAX_ATTEMPTS="8"
# RELAY_RATE_WINDOW="300"
# RELAY_LOCKOUT_SECONDS="900"

# Where the database and session file live. Inside the container this is the
# bind mount; on a host run it defaults to ./data.
# RELAY_DATA_DIR="/app/data"
```

`API_ID` and `API_HASH` are the values you create at
[my.telegram.org](https://my.telegram.org) → *API development tools*. The
dashboard also accepts them interactively, so putting them here is optional —
but keeping them in `.env` means you never have to retype them on a rebuild.
The quotes are what matter; the spacing inside them is only a visible
placeholder. A value of only spaces is an invalid credential and will be
rejected.

Only `RELAY_USERNAME` and `RELAY_PASSWORD` are read from the environment. The
Telegram values are stored in the database once you save them from the UI.

---

## Connecting Telegram

This happens once per machine, because a Telegram session is bound to the
machine that created it.

1. **Get API credentials** — sign in at
   [my.telegram.org](https://my.telegram.org) → *API development tools* → create
   an app → copy the **API ID** and **API Hash**
2. Enter both in the dashboard and save
3. Enter your **phone number** in international format (`+91XXXXXXXXXX`)
4. Telegram sends an OTP — enter it in the dashboard
5. If you have two-step verification, enter that password too

This creates `data/telegram_session`. After that, restarts do not ask for an OTP
again — as long as the `data/` volume survives.

> **Only forward from channels you have permission to read**, and only from an
> account you are willing to risk. Telegram's Terms of Service are your
> responsibility. This project is for personal and educational use.

---

## Configuration

### Dashboard settings

These are stored in the database, not in `.env`, and are editable from the UI.

| Setting | Default | What it does |
|---|---|---|
| Converter Bot | `@ExtraPeBot` | Destination for forwarded messages |
| Source Channels | *(empty)* | Channels to watch |
| Duplicate Retention | 1 day | How long a message counts as already-forwarded |
| Retry Attempts | 3 | Attempts per message before it is marked failed |
| Retry Delay | 2 seconds | Base delay; doubles each attempt |
| Log Retention | 1 day | Activity log history; `0` keeps everything |
| Auto-resume | off | Restart monitoring automatically after a restart |

> Changing channels while monitoring is running needs a restart — the running
> monitor keeps the channels it resolved when it started. The dashboard tells you
> when this applies.

### Environment variables

Set in `.env`, read at container start.

| Variable | Default | Purpose |
|---|---|---|
| `RELAY_USERNAME` | — | **Required.** Dashboard username |
| `RELAY_PASSWORD` | — | **Required.** Dashboard password |
| `RELAY_AUTH_DISABLED` | `0` | Set to `1` to disable auth. Trusted machines only |
| `RELAY_MAX_ATTEMPTS` | `8` | Failed logins before lockout |
| `RELAY_RATE_WINDOW` | `300` | Length of the rate-limit window, seconds |
| `RELAY_LOCKOUT_SECONDS` | `900` | Lockout duration |
| `RELAY_DATA_DIR` | `/app/data` | Where the database and session file live |

---

## How it works

A short tour, if you want to read the code.

**`app.py`** — the FastAPI application. Holds every `/api/*` endpoint, the auth
middleware, the security headers, and a `lifespan` hook that owns everything
long-lived.

**`telegram_service.py`** — all Telegram behaviour: connecting, authentication,
the live monitoring loop, message processing, and two background loops (a
maintenance loop for log retention every 15 minutes, and a watchdog that checks
the connection every 60 seconds).

**`database.py`** — a thin SQLite helper. Three tables: `settings`,
`processed_messages` (the duplicate-tracking table, with `pending` / `sent` /
`failed` states), and `activity_logs`.

**Three decisions worth knowing about**, because they are what make the relay
survive real deployments:

- **Claims are atomic.** `claim_message()` wraps its read-then-write in
  `BEGIN IMMEDIATE`. The live handler and the history scan both call it, and only
  one of them can win. Without this, a message arriving while a scan is running
  gets forwarded twice.
- **Shutdown does not clear the auto-resume flag.** `stop_monitoring()` takes a
  `clear_auto_resume` argument. A container stop passes `False`; an operator
  pressing "Stop Monitor" passes `True`. Conflating the two means auto-resume can
  never fire again after the first restart.
- **Log polling uses the row id, not a timestamp.** `/api/activity?after_id=` is
  the cursor. A timestamp filter would silently drop entries when several events
  land in the same second.

**Frontend** — `static/app.js` is plain JavaScript with no build step and no
framework. You can edit it and hit reload. Every value that reaches `innerHTML`
from Telegram or the database goes through `escapeHtml()`.

---

## Project layout

The repository root holds one folder; the application lives inside it.

```
telegram-automation-bot/
└── github telegram/
    ├── app.py                  FastAPI app — routes, auth, security headers
    ├── telegram_service.py     Telethon client — monitoring, forwarding, retries
    ├── database.py             SQLite helper — settings, messages, logs
    ├── templates/index.html    Dashboard markup
    ├── static/
    │   ├── app.js              Frontend logic (no build step)
    │   └── style.css           Design system, light and dark
    ├── tests/                  Four self-contained suites
    ├── data/                   Runtime state — relay.db + telegram_session
    │                           (never commit)
    ├── Dockerfile              Multi-stage build, non-root user
    ├── docker-compose.yml      Production compose, loopback-only port
    ├── docker-entrypoint.sh    Fixes data/ ownership, then drops to non-root
    ├── provision.sh            One-shot VM setup: Docker, .env, build, cron
    ├── backup.sh               WAL-safe database backup with automatic pruning
    ├── .env                    Your credentials — create it, never commit it
    ├── DEPLOYMENT.md           Free 24/7 hosting guide
    ├── SECURITY.md             How to report a vulnerability
    └── CONTRIBUTING.md         Development setup and style guide
```

> **Not yet in this repository:** `.env.example`, `.gitignore`, `.dockerignore`,
> and a GitHub Actions workflow. Until `.gitignore` exists, `git add .` from the
> project folder will happily stage `.env` and `data/` — see
> [Security](#security).

---

## Deployment

`docker-compose.yml` binds the port to **loopback only**:

```yaml
ports:
  - "127.0.0.1:8000:8000"
```

That is deliberate. Exposing port 8000 on a public IP would serve the dashboard
over plain HTTP, and Basic auth credentials would cross the wire in clear text.
Put a TLS terminator in front of it.

**For a free 24/7 setup**, see [DEPLOYMENT.md](DEPLOYMENT.md) — it covers
Oracle Cloud Always Free, Cloudflare Tunnel, and DuckDNS.

**One-shot provisioning** on a fresh Debian/Ubuntu VM:

```bash
sudo bash provision.sh /opt/telegram-relay-dashboard
```

Or over the network, straight from this repository:

```bash
curl -fsSL https://raw.githubusercontent.com/auxsh24/telegram-automation-bot/main/github%20telegram/provision.sh | sudo bash
```

It installs Docker, generates a random `.env` password, builds and starts the
container, waits for it to report healthy, and installs a daily backup cron job.
It is idempotent — safe to re-run, and it will not wipe your data.

### Useful commands

```bash
docker compose ps                 # status
docker compose logs -f            # follow logs
docker compose restart            # restart (session survives)
docker compose down               # stop (data is kept)
docker compose down -v            # stop and delete volumes (you will need a new OTP)
```

---

## Backups

`backup.sh` takes a consistent copy of `relay.db` using SQLite's online backup
API — copying the file directly can capture a half-written WAL. Old snapshots are
pruned automatically after 14 days.

```bash
RELAY_DATA_DIR=./data ./backup.sh        # Linux / macOS / Git Bash
```

| Variable | Default | Purpose |
|---|---|---|
| `RELAY_DATA_DIR` | `/opt/telegram-relay-dashboard/data` | Where `relay.db` lives |
| `RELAY_BACKUP_DIR` | `$RELAY_DATA_DIR/backups` | Where snapshots are written |
| `RELAY_BACKUP_KEEP_DAYS` | `14` | How long to keep them |

Run it **on the host**, not inside the container. It uses the online backup API,
so a running container is unaffected. It needs `python3` on the host.

**The session file is not covered.** If you want `data/telegram_session` backed
up too — so you do not need a new OTP on a rebuild — copy it separately:

```bash
cp data/telegram_session data/backups/telegram_session.bak
```

> That file is a live Telegram login. Keep its backup somewhere just as safe as
> the original — never in cloud storage or a public repository.

---

## Tests

Four self-contained suites. No `pytest` needed — each one exits non-zero on
failure.

```bash
python -m tests.test_smoke         # auth, security headers, static assets, routes
python -m tests.test_auto_resume   # the relay flag survives a restart
python -m tests.test_throttle      # the auth lockout locks, recovers, and resets
python -m tests.test_maintenance   # log retention and auto_resume toggles
```

Or all four:

```bash
for t in smoke auto_resume throttle maintenance; do
  python -m tests.test_$t || echo "FAILED: $t"
done
```

`test_smoke` uses FastAPI's `TestClient`, which is not in `requirements.txt`:

```bash
pip install -r requirements.txt
pip install fastapi[standard]
```

Every test points `RELAY_DATA_DIR` at a fresh temp directory, so your real
database and Telegram session are never touched. They run on the **host**, not
in Docker.

> **Python 3.11 or 3.12 only.** The pinned `pydantic==2.10.5` has no prebuilt
> wheel for Python 3.13+, so installing it on a newer interpreter will try (and
> fail) to compile from source. If your default `python` is 3.13 or 3.14, build
> the virtual environment explicitly:
>
> ```bash
> uv venv --python 3.12 .venv        # or: py -3.12 -m venv .venv
> ```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `env file .env not found` | `.env` was never created | Create it — [Creating `.env`](#creating-env) |
| `localhost:8000` refuses the connection | Container is not running | `docker compose ps`, then `docker compose logs --tail=30` |
| Login returns `401` | `.env` credentials do not match | Fix `.env`, then `docker compose up -d` |
| Page returns `503` | `RELAY_USERNAME` / `RELAY_PASSWORD` not both set | Set both in `.env` |
| Locked out after a few attempts | Rate limit tripped | Wait `RELAY_LOCKOUT_SECONDS`, then retry |
| `sqlite3.OperationalError: unable to open database file` | Host `data/` is not writable by the container user | `sudo chown -R relay:relay data` on Linux; on Windows check the folder is writable |
| "container name already in use" | An old container is still up, or port 8000 is busy | `docker compose down`, or check `docker compose ps` |
| Asks for the OTP again after a restart | The `data/` volume was deleted or is not mounted | Check the volume in `docker-compose.yml` |
| Port 8000 already in use | Something else is on that port | Change `127.0.0.1:8000:8000` to `127.0.0.1:8080:8000` |
| Dashboard says monitoring, nothing forwards | Telegram connection dropped | The watchdog retries within 60s; check *Relay Health* and *last error* |
| Messages are skipping | Treated as duplicates | Raise *Duplicate Retention* above 1 day |
| Container restarts during the first build on ARM | pydantic compiling from source | Normal — the first build on Oracle ARM takes 3–5 minutes |
| `pip install` fails on pydantic | Running Python 3.13+ | Use Python 3.11 or 3.12 for the venv |

---

## Security

- **`.env` and `data/telegram_session` are the two files that can hurt you.**
  The first is a password. The second is a full Telegram login: anyone who gets
  hold of it can act as you.
- **This repository does not ship a `.gitignore` yet.** Until one is added, do
  not run `git add .` from the project folder — exclude the secrets locally
  first:
  ```bash
  printf '.env\ndata/\n*.session\n__pycache__/\n' >> .git/info/exclude
  ```
- **Always set `RELAY_USERNAME` and `RELAY_PASSWORD` in production.** The app
  refuses to serve without them rather than falling open.
- **Put HTTPS in front of it.** The app sends Basic auth credentials in a header
  on every request. Over plain HTTP on a public network, anyone on the path can
  read them. Use Cloudflare Tunnel or a reverse proxy.
- **Do not set `RELAY_AUTH_DISABLED=1`** anywhere other than a trusted local
  machine.
- Report vulnerabilities privately — see [SECURITY.md](SECURITY.md). Please do
  not open a public issue.

If a session file is ever exposed, deleting the commit is not enough: the object
stays in history, in every fork, and in every clone. **Log out of Telegram
everywhere** ("Terminate other sessions") and treat the account as compromised.

---

## Contributing

Bug reports, deployment failures, and pull requests are all welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). It covers the dev setup, the style the code
follows, and the four test suites you should run before opening a PR.

---

## License

MIT — use, modify, and distribute freely. See [LICENSE](LICENSE).

**Telegram** is not affiliated with this project. Telegram is a trademark of its
respective owner.

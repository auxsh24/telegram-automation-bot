# Telegram Relay Dashboard

A self-hosted, real-time Telegram message relay dashboard. Monitor source channels, forward messages to a converter bot, and manage everything through a clean web UI — all with zero monthly cost.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Telethon](https://img.shields.io/badge/Telethon-1.45-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

- **Real-time Monitoring** — Live message forwarding from source channels to converter bot
- **Web Dashboard** — Clean, responsive UI for managing relay settings and monitoring activity
- **Duplicate Detection** — TTL-based deduplication prevents double-forwarding
- **Auto-Resume** — Monitoring automatically restarts after container reboot
- **Watchdog** — Automatic Telegram connection recovery
- **Log Retention** — Configurable automatic cleanup of old activity logs
- **Rate Limiting** — Brute-force protection on dashboard authentication
- **Security Headers** — CSP, X-Frame-Options, nosniff, and more
- **Cloud Ready** — PostgreSQL support, session string auth, Docker deployment

---

## 🚀 Quick Start (Local Docker)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)

### 1. Clone & Configure

```bash
git clone https://github.com/auxsh24/telegram-automation-bot.git
cd telegram-automation-bot

cp .env.example .env
```

Edit `.env`:

```ini
RELAY_USERNAME=operator
RELAY_PASSWORD=your-secure-password-here

TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_32_char_api_hash_here
```

### 2. Build & Run

```bash
docker compose up -d --build
```

### 3. Access Dashboard

Open [http://localhost:8000](http://localhost:8000) and log in with your credentials.

### 4. Connect Telegram

1. Go to **Settings** → enter API ID & Hash → **Save**
2. Enter phone number → **Send Code**
3. Enter OTP → **Verify**
4. If 2FA enabled, enter password
5. Set converter bot & source channels → **Save Settings**
6. Click **Start Monitor** ✅

---

## ☁️ Cloud Deployment (24/7 — Free)

Deploy to Oracle Cloud Always Free, Railway, or any VPS for 24/7 uptime.

### Quick Cloud Setup

```bash
# 1. On your cloud VM
git clone https://github.com/auxsh24/telegram-automation-bot.git
cd telegram-automation-bot

# 2. Configure environment
cp .env.example .env
nano .env
```

```ini
RELAY_USERNAME=operator
RELAY_PASSWORD=$(openssl rand -base64 24)

# PostgreSQL (Supabase free tier recommended)
DATABASE_URL=postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres

# Telegram
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_SESSION_STRING=your_session_string_here

# Relay settings
RELAY_CONVERTER_BOT=@ExtraPeBot
RELAY_SOURCE_CHANNELS=["@channel1","@channel2"]
```

```bash
# 3. Deploy
docker compose up -d --build
```

### Generate Session String (one-time)

```bash
python -c "
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

with TelegramClient(StringSession(), 12345678, 'your_api_hash') as client:
    print(client.session.save())
"
```

### HTTPS with Cloudflare Tunnel (Free)

```bash
# Install cloudflared
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Authenticate & create tunnel
cloudflared tunnel login
cloudflared tunnel create telegram-relay
cloudflared tunnel route dns telegram-relay relay.yourdomain.com

# Configure config.yml
# hostname: relay.yourdomain.com
# service: http://localhost:8000

cloudflared tunnel run telegram-relay
```

---

## 🔧 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RELAY_USERNAME` | ✅ | — | Dashboard login username |
| `RELAY_PASSWORD` | ✅ | — | Dashboard login password |
| `TELEGRAM_API_ID` | ✅ | — | From my.telegram.org |
| `TELEGRAM_API_HASH` | ✅ | — | From my.telegram.org |
| `DATABASE_URL` | — | SQLite | PostgreSQL connection string |
| `TELEGRAM_SESSION_STRING` | — | Session file | Cloud: use string; Local: use file |
| `RELAY_CONVERTER_BOT` | — | `@ExtraPeBot` | Target bot username |
| `RELAY_SOURCE_CHANNELS` | — | `[]` | JSON array of channel usernames |
| `RELAY_DUPLICATE_TTL_DAYS` | — | `1` | Days to remember processed messages |
| `RELAY_RETRY_ATTEMPTS` | — | `3` | Max send retry attempts |
| `RELAY_RETRY_DELAY_SECONDS` | — | `2` | Base delay between retries (exponential) |
| `RELAY_LOG_RETENTION_DAYS` | — | `1` | Days to keep activity logs (0 = keep all) |
| `RELAY_MAX_ATTEMPTS` | — | `8` | Max auth failures before lockout |
| `RELAY_RATE_WINDOW` | — | `300` | Rate limit window (seconds) |
| `RELAY_LOCKOUT_SECONDS` | — | `900` | Lockout duration (seconds) |
| `RELAY_AUTH_DISABLED` | — | `false` | Disable auth (dev only, never in production) |
| `RELAY_DATA_DIR` | — | `./data` | Data directory path |

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check (no auth) |
| `GET` | `/api/status` | Telegram authorization status |
| `POST` | `/api/setup` | Configure API credentials |
| `POST` | `/api/telegram/send-code` | Send OTP to phone |
| `POST` | `/api/telegram/verify-code` | Verify OTP |
| `POST` | `/api/telegram/verify-2fa` | Verify 2FA password |
| `GET` | `/api/telegram/account` | Get account info |
| `POST` | `/api/telegram/disconnect` | Disconnect account |
| `GET` | `/api/activity` | Get activity logs |
| `GET` | `/api/stats` | Get today's statistics |
| `POST` | `/api/relay/send-test` | Send test message |
| `GET` | `/api/relay/status` | Get monitoring status |
| `POST` | `/api/relay/analyze` | Scan today's messages |
| `POST` | `/api/relay/start` | Start monitoring |
| `POST` | `/api/relay/stop` | Stop monitoring |
| `GET` | `/api/settings` | Get relay settings |
| `POST` | `/api/settings` | Save relay settings |
| `POST` | `/api/logs/cleanup` | Clean old logs |

---

## 🔒 Security

- **Basic Auth** with brute-force throttling (8 attempts / 5 min → 15 min lockout)
- **Security Headers**: CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy
- **Non-root container** with `no-new-privileges`
- **Loopback-only port** binding (use Cloudflare Tunnel or reverse proxy for HTTPS)
- **Secrets excluded** from git (`.env`, `.db`, `.session`)
- **Constant-time comparison** for credentials (timing attack prevention)

---

## 💾 Backups

### SQLite (Local)

```bash
# Automatic daily backup via cron
crontab -e
# Add: 17 3 * * * /path/to/backup.sh >> /var/log/relay-backup.log 2>&1
```

Backups stored in `data/backups/` with 14-day rotation.

### PostgreSQL (Cloud)

```bash
# Manual backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore
psql $DATABASE_URL < backup_20241001.sql
```

---

## 📊 Monitoring

- **UptimeRobot** — Monitor `https://yourdomain.com/api/health` (free, 5-min interval)
- **Container Healthcheck** — Docker auto-restarts unhealthy containers
- **Watchdog Loop** — Auto-reconnects Telegram every 60s if connection drops
- **Maintenance Loop** — Auto-cleans logs and stale claims every 15 min

---

## 🐳 Docker Compose

```yaml
services:
  telegram-relay:
    build: .
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

---

## 🏗️ Project Structure

```
telegram-automation-bot/
├── app.py                 # FastAPI application
├── database.py            # SQLite/PostgreSQL dual backend
├── telegram_service.py    # Telethon client & relay logic
├── docker-compose.yml     # Production compose
├── Dockerfile             # Multi-stage build
├── docker-entrypoint.sh   # Container entrypoint
├── provision.sh           # One-shot VM provisioning
├── backup.sh              # Database backup script
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
├── static/                # Frontend assets (JS, CSS)
├── templates/             # HTML templates
├── tests/                 # Test suite
└── data/                  # Runtime data (git-ignored)
```

---

## 🧪 Testing

```bash
# Run all tests
python -m tests.test_smoke
python -m tests.test_throttle
python -m tests.test_maintenance
python -m tests.test_auto_resume
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|---|---|
| `database is locked` | Increase `BUSY_TIMEOUT_MS` in `database.py` |
| `503` on every page | Check `RELAY_USERNAME` and `RELAY_PASSWORD` in `.env` |
| `401` loop | Clear browser cache or restart container |
| Monitoring not auto-resuming | Enable "Auto-resume after restart" in settings |
| `TELEGRAM_SESSION_STRING` invalid | Regenerate session string |
| Container unhealthy | Run `docker compose logs --tail=50` |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

## ⚠️ Disclaimer

This tool is for educational and personal use. Ensure compliance with Telegram's Terms of Service. The authors are not responsible for any misuse or account restrictions.

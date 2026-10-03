# Production Deployment — Telegram Relay Dashboard

Free hosting par 24/7 chalne wala relay. Cost **₹0**.

---

## 1. Kyu Oracle Cloud (aur Kuch Nahi)

Is project ke liye free web hosting (Render, Koyeb, Fly) **kaam nahi karta** —
kyunki ye long-lived Telegram session rakhta hai:

| Platform | Problem |
|---|---|
| Render / Koyeb free | Instance sleep/restart hoti hai → `.session` file rotate → dobara OTP |
| Fly.io / Railway | Free credit khatam, card mandatory |
| **Oracle Cloud Always Free** | ✅ 4 ARM core / 24 GB RAM / 200 GB disk, *forever free*, public IP, 24/7 |

VM pe Docker + Compose chalta hai, aur Cloudflare Tunnel front par HTTPS deta hai
— bina koi port expose kiye.

---

## 2. VM Banana (Oracle Cloud)

1. **cloud.oracle.com** → free account (card lagta hai, charge nahi hota)
2. **Compute → Instances → Create**
   - Shape: **VM.Standard.A1.Flex**, 2 OCPU / 12 GB RAM
   - Image: **Canonical Ubuntu 24.04 (aarch64)**
   - Networking: default VCN, **assign a public IP**
3. SSH key generate karo (ya `ssh-keygen -t ed25519`) aur public key paste karo
4. Instance create → IP note karo

> Free tier me shape availability limited hoti hai. Agar A1 nahi mil raha to
> `VM.Standard.E2.Flex` (1 GB) try karo — relay ke liye bhi kaafi hai.

---

## 3. Server Setup

```bash
ssh ubuntu@<YOUR_VM_IP>

sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker $USER && newgrp docker

sudo mkdir -p /opt/telegram-relay-dashboard
sudo chown -R $USER /opt/telegram-relay-dashboard

cd /opt/telegram-relay-dashboard
# repo yahan clone ya copy karo
git clone <YOUR_REPO_URL> . || cp -r /path/to/local/project/* .
```

**Arm64 build (Oracle) pe pydantic compile hota hai** — build thoda slow hai,
pehli baar ~3-5 min lagenge.

---

## 4. Secrets — `.env`

```bash
cp .env.example .env
nano .env
```

```ini
RELAY_USERNAME=your-operator-name
RELAY_PASSWORD=$(openssl rand -base64 24)
```

Password kahin safe jagah note karo — isi se dashboard login hota hai.

```bash
chmod 600 .env
```

---

## 5. Launch

```bash
cd /opt/telegram-relay-dashboard
docker compose up -d --build

docker compose ps          # healthy dikhna chahiye
docker compose logs -f     # startup logs
```

> Data-directory permissions automatically fix ho jaati hain — image ka
> entrypoint startup par `data/` ko `relay` user ko de deta hai aur phir
> unprivileged user par re-exec ho jaata hai. Extra `chown` karne ki zaroorat
> nahi.

Verify:

```bash
curl -s http://127.0.0.1:8000/api/health
# {"status":"ok","version":"1.0.0","uptime_seconds":3,"monitoring":false}
```

> **Port 8000 abhi bhi public nahi hai** (`127.0.0.1:8000:8000` binding).
> Agla step ise public karta hai — HTTPS ke saath.

---

## 6. HTTPS — Cloudflare Tunnel (Free)

**Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create**

```bash
# Cloudflare se milega exact command, e.g.:
cloudflared service install <TOKEN>
```

Tunnel ka **Public Hostname** add karo:

| Field | Value |
|---|---|
| Subdomain | `relay` |
| Domain | aapka domain |
| Type | HTTP |
| URL | `localhost:8000` |

Result: `https://relay.yourdomain.com` → app, TLS Cloudflare handle karta hai.

**Free domain chahiye?** DuckDNS (`duckdns.org`) se free subdomain milta hai —
usko Cloudflare me CNAME kar do.

Ab koi bhi firewall port open karne ki zaroorat nahi. Default Oracle security
list me sirf SSH (22) khula hai, wahi rakho.

---

## 7. First Login

1. Browser me `https://relay.yourdomain.com` kholo
2. `.env` wala username/password daal
3. Telegram API credentials → phone → OTP → **Verify & Connect**
4. Settings me converter bot + source channels bharo → **Save Settings**
5. **Start Monitor** dabao
6. Settings me **Auto-resume after restart ON** karo ✅ ← sabse important

---

## 8. Auto-Restore (Restart Ke Baad)

`auto_resume` flag DB me persist hota hai. App start hote hi monitoring khud
restart ho jaata hai — deploy, crash, `docker compose restart`, VM reboot — sab
ke baad. Manual click ki zaroorat nahi.

Saath hi do background loops chalte hain:
- **Watchdog** (60s) — Telegram connection girne par reconnect + handler dobara attach
- **Maintenance** (15 min) — log retention + stale claims cleanup

---

## 9. Backups (Zaroori)

`data/relay.db` me processed-message ledger hai. Khoye to relay bhool jaata hai
kya forward ho chuka hai — aur aaj ke messages dobara bhej dega.

```bash
crontab -e
# yeh line add karo:
17 3 * * * /opt/telegram-relay-dashboard/backup.sh >> /var/log/relay-backup.log 2>&1
```

14 din ka rotation already script me hai. Backups `data/backups/` me jaate hain.

---

## 10. Monitoring (Free)

- **UptimeRobot** → `https://relay.yourdomain.com/api/health`, 5 min interval
  (ye endpoint auth-free hai, isliye directly probe ho sakta hai)
- Container crash → `restart: unless-stopped` + `HEALTHCHECK` khud restart karega

---

## 11. Updates

```bash
cd /opt/telegram-relay-dashboard
git pull
docker compose up -d --build
```

Monitoring apne aap wapas aayega (auto-resume on hai).

---

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Health check `unhealthy` | `docker compose logs --tail=50` |
| `sqlite3.OperationalError: unable to open database file` | Host par `data/` ki ownership theek nahi. `sudo chown -R 999:999 /opt/telegram-relay-dashboard/data` |
| `503` on every page | `.env` me dono `RELAY_*` set nahi |
| `401` loop, password sahi hai | 8 galat tries = 15 min lockout. `docker compose restart` se mitao |
| Monitoring khud restart nahi hua | Settings me auto-resume ON hai? Telegram session valid hai? |
| "Reconnect" message | Telegram ne session invalidate kiya — dobara OTP daalna padega |
| Build fail (Oracle ARM) | Normal hai, pydantic compile hota hai. 5 min wait karo |
| `data/` files root-owned | `sudo chown -R $USER /opt/telegram-relay-dashboard/data` |

---

## Security Posture

- ✅ Loopback-only port + HTTPS tunnel (credentials kabhi cleartext me nahi jaate)
- ✅ Brute-force throttling (8 attempts / 5 min → 15 min lockout)
- ✅ Non-root container, `no-new-privileges`
- ✅ CSP, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`
- ✅ `.env`, `.db`, `.session` git-ignored
- ✅ SQLite WAL + busy timeout (concurrent writes crash nahi karte)
- ✅ Docker log rotation (10 MB × 3) — disk full nahi hoga

## Tests

Changes ke baad:

```bash
.venv/Scripts/python.exe -m tests.test_smoke
.venv/Scripts/python.exe -m tests.test_throttle
.venv/Scripts/python.exe -m tests.test_maintenance
.venv/Scripts/python.exe -m tests.test_auto_resume
```

Sabhi scratch DB use karte hain — real relay data safe rehta hai.

---

## 12. Cloud Deployment (24x7 — Free)

Is section mein bataya hai ki relay ko bina kisi monthly fee ke 24/7 cloud pe kaise chalaya jaata hai.

### 12.1 Kyu Cloud Deployment Zaroori Hai

Local Docker setup perfect hai, lekin laptop band hone pe relay bhi band ho jaata hai. Cloud deployment se:

- Laptop band hone pe bhi relay 24x7 chalta hai
- Container restart/crash pe auto-resume monitoring wapas aata hai
- Data persistent rehta hai (PostgreSQL ya managed storage)
- Public URL se dashboard access hota hai

### 12.2 Database: SQLite → PostgreSQL

Cloud pe SQLite kaam nahi karta kyunki container filesystem ephemeral hoti hai. Do options:

**Option A: Supabase (Free, Recommended)**

1. supabase.com pe free account banao
2. New Project → region select karo (Singapore ya India closest)
3. Project Settings → Database → Connection string lo
4. `.env` mein set karo:
   ```
   DATABASE_URL=postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres
   ```

**Option B: Bundled PostgreSQL (docker-compose)**

`docker-compose.yml` mein commented postgres service uncomment karo aur `.env` mein:
```
DATABASE_URL=postgresql://relay:relay@postgres:5432/relay
```

### 12.3 Telegram Session String Generate Karo

Cloud pe session file survive nahi karta, isliye session string use karo:

```bash
# Local machine pe run karo (ek baar)
python -c "
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 12345678
api_hash = 'your_api_hash_here'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())
"
```

Output ek long string hoga (jaisa `1abc2def3ghi...`). Isse `.env` mein daalo:
```
TELEGRAM_SESSION_STRING=1abc2def3ghi...
```

### 12.4 Hosting Platforms

| Platform | Free Tier | Notes |
|---|---|---|
| **Oracle Cloud Always Free** | 4 ARM core, 24 GB RAM, 200 GB disk | Best for Docker, 24/7, public IP |
| **Railway.app** | $5 credit/month | Easy Docker deploy, card required |
| **Render.com** | 750 hours/month | Free tier sleeps after inactivity |
| **Vercel** | 100 GB bandwidth | Serverless, FastAPI support limited |

**Recommended: Oracle Cloud Always Free** — forever free, no card charge, 24/7 uptime.

### 12.5 Oracle Cloud Setup

1. cloud.oracle.com pe free account banao (card lagta hai, charge nahi hota)
2. Compute → Instances → Create
   - Shape: VM.Standard.A1.Flex (2 OCPU / 12 GB RAM)
   - Image: Canonical Ubuntu 24.04 (aarch64)
   - Networking: default VCN, assign public IP
3. SSH key generate karo aur public key paste karo
4. Instance create → IP note karo

### 12.6 Server Setup

```bash
ssh ubuntu@<YOUR_VM_IP>

sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker $USER && newgrp docker

sudo mkdir -p /opt/telegram-relay-dashboard
sudo chown -R $USER /opt/telegram-relay-dashboard

cd /opt/telegram-relay-dashboard
git clone <YOUR_REPO_URL> .
```

### 12.7 Environment Variables

```bash
cp .env.example .env
nano .env
```

```ini
RELAY_USERNAME=operator
RELAY_PASSWORD=$(openssl rand -base64 24)

# PostgreSQL (Supabase ya bundled)
DATABASE_URL=postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres

# Telegram
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_SESSION_STRING=1abc2def3ghi...

# Relay settings
RELAY_CONVERTER_BOT=@ExtraPeBot
RELAY_SOURCE_CHANNELS=["@channel1","@channel2"]
RELAY_DUPLICATE_TTL_DAYS=1
RELAY_RETRY_ATTEMPTS=3
RELAY_RETRY_DELAY_SECONDS=2
RELAY_LOG_RETENTION_DAYS=1
```

```bash
chmod 600 .env
```

### 12.8 Launch

```bash
cd /opt/telegram-relay-dashboard
docker compose up -d --build
docker compose ps
docker compose logs -f
```

### 12.9 HTTPS — Cloudflare Tunnel (Free)

Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create

```bash
cloudflared service install <TOKEN>
```

Tunnel ka Public Hostname add karo:

| Field | Value |
|---|---|
| Subdomain | relay |
| Domain | aapka domain |
| Type | HTTP |
| URL | localhost:8000 |

Result: `https://relay.yourdomain.com` → app, TLS Cloudflare handle karta hai.

### 12.10 First Login

1. Browser me `https://relay.yourdomain.com` kholo
2. `.env` wala username/password daal
3. Telegram API credentials → phone → OTP → Verify & Connect
4. Settings me converter bot + source channels bharo → Save Settings
5. Start Monitor dabao
6. Settings me Auto-resume after restart ON karo

### 12.11 Backups

```bash
crontab -e
# yeh line add karo:
17 3 * * * /opt/telegram-relay-dashboard/backup.sh >> /var/log/relay-backup.log 2>&1
```

PostgreSQL me backup.sh automatically pg_dump use karta hai.

### 12.12 Monitoring

- UptimeRobot → `https://relay.yourdomain.com/api/health`, 5 min interval
- Container crash → `restart: unless-stopped` + HEALTHCHECK khud restart karega

### 12.13 Updates

```bash
cd /opt/telegram-relay-dashboard
git pull
docker compose up -d --build
```

Monitoring apne aap wapas aayega (auto-resume on hai).

### 12.14 Cloud Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `sqlalchemy.exc.OperationalError` | DATABASE_URL galat hai ya DB reachable nahi |
| `TELEGRAM_SESSION_STRING` invalid | Session expire ho gaya — dobara generate karo |
| Container restart loop | `docker compose logs --tail=50` dekho |
| Health check unhealthy | Port 8000 loopback pe bind hai — Cloudflare Tunnel check karo |
| Auth lockout | 8 galat tries = 15 min lockout. `docker compose restart` se mitao |
| Monitoring auto-resume nahi | Settings me auto-resume ON hai? Session valid hai? |

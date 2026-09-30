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

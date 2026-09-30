#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-shot provisioning for the Telegram Relay Dashboard.
#
# Run this on a fresh Ubuntu VM (Oracle Cloud Always Free works well):
#
#   curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/provision.sh | bash
#
# or, if you are uploading the project yourself:
#
#   sudo bash provision.sh /opt/telegram-relay-dashboard
#
# It is idempotent: running it again is safe and will not wipe data.
# ---------------------------------------------------------------------------

set -euo pipefail

APP_DIR="${1:-/opt/telegram-relay-dashboard}"
REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"

log()  { printf '\033[0;36m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[warn ]\033[0m %s\n' "$*"; }
fail() { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Sanity checks
# ---------------------------------------------------------------------------

[ "$(id -u)" = "0" ] || fail "Run with sudo: sudo bash provision.sh"

command -v apt-get >/dev/null || fail "This script targets Debian/Ubuntu only."

log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    ca-certificates curl git \
    docker.io docker-compose-v2 \
    cron openssl >/dev/null

# Ubuntu 24.04 ships the Compose v2 plugin; older releases need the shim.
if ! docker compose version >/dev/null 2>&1; then
    warn "docker compose (v2) not found, falling back to docker-compose"
fi

systemctl enable --now docker >/dev/null 2>&1 || true
systemctl enable --now cron >/dev/null 2>&1 || true

docker --version
(docker compose version || docker-compose --version) 2>/dev/null || warn "compose version check failed"

# ---------------------------------------------------------------------------
# 2. Fetch the project
# ---------------------------------------------------------------------------

if [ -n "$REPO_URL" ]; then
    log "Cloning $REPO_URL into $APP_DIR"
    if [ -d "$APP_DIR/.git" ]; then
        git -C "$APP_DIR" pull --ff-only
    else
        mkdir -p "$APP_DIR"
        git clone "$REPO_URL" "$APP_DIR"
    fi
elif [ -f "$APP_DIR/docker-compose.yml" ]; then
    log "Using existing project at $APP_DIR"
else
    fail "No project found. Upload the files to $APP_DIR or set REPO_URL."
fi

cd "$APP_DIR"

# ---------------------------------------------------------------------------
# 3. Secrets
# ---------------------------------------------------------------------------

if [ ! -f .env ]; then
    log "Generating .env with a random password"
    RELAY_PASSWORD="$(openssl rand -base64 24 | tr -d '\n/+=' | head -c 28)"

    cat > .env <<EOF
RELAY_USERNAME=operator
RELAY_PASSWORD=$RELAY_PASSWORD
EOF

    chmod 600 .env

    printf '\n\033[0;32m%s\033[0m\n' "=============================================="
    printf '\033[0;32m%s\033[0m\n' " Dashboard credentials — SAVE THESE NOW"
    printf '\033[0;32m%s\033[0m\n' "=============================================="
    printf '  username : operator\n'
    printf '  password : %s\n' "$RELAY_PASSWORD"
    printf '\033[0;32m%s\033[0m\n' "=============================================="
    printf ' They are also stored in %s/.env (mode 600).\n\n' "$APP_DIR"
else
    log ".env already exists — leaving it untouched"
fi

# ---------------------------------------------------------------------------
# 4. Data directory
# ---------------------------------------------------------------------------
# The image entrypoint fixes ownership itself, but creating the directory up
# front avoids Docker creating it as root on some hosts.

log "Preparing data directory"
mkdir -p data

# ---------------------------------------------------------------------------
# 5. Build and start
# ---------------------------------------------------------------------------

log "Building the image (first build on ARM takes a few minutes)"
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
else
    COMPOSE="docker-compose"
fi

$COMPOSE up -d --build

log "Waiting for the container to report healthy"
for i in $(seq 1 40); do
    STATE="$(docker inspect -f '{{.State.Health.Status}}' telegram-relay-dashboard 2>/dev/null || echo starting)"
    [ "$STATE" = "healthy" ] && break
    if [ "$STATE" = "unhealthy" ]; then
        warn "Container reported unhealthy; recent logs:"
        $COMPOSE logs --tail=40 || true
        break
    fi
    sleep 3
done

# ---------------------------------------------------------------------------
# 6. Backups
# ---------------------------------------------------------------------------

log "Installing the daily backup cron job"
CRON_LINE="17 3 * * * $APP_DIR/backup.sh >> /var/log/relay-backup.log 2>&1"

if crontab -l 2>/dev/null | grep -q "relay-backup.log"; then
    log "Backup cron already present"
else
    ( crontab -l 2>/dev/null; echo "$CRON_LINE" ) | crontab -
    log "Backup cron installed (daily at 03:17)"
fi

# ---------------------------------------------------------------------------
# 7. Report
# ---------------------------------------------------------------------------

echo
log "Status:"
docker ps --filter name=telegram-relay-dashboard \
    --format '  {{.Status}}  {{.Ports}}' || true

echo
log "Local health check:"
curl -s --max-time 5 http://127.0.0.1:8000/api/health || warn "no response yet"
echo
echo

cat <<EOF

Next steps
----------

1. Expose it over HTTPS. The app is bound to 127.0.0.1 on purpose, so you now
   need a TLS terminator. Cloudflare Tunnel is free and needs no open ports:

     Cloudflare Zero Trust -> Networks -> Tunnels -> Create
     Public hostname: relay.yourdomain.com -> HTTP -> localhost:8000

   No domain yet? DuckDNS gives a free subdomain; point it at the tunnel.

2. Open the dashboard, sign in with the credentials printed above, then:
     - connect your Telegram account (API ID / hash / phone / code)
     - set the converter bot and source channels
     - IMPORTANT: turn ON "Auto-resume after restart"

3. Wire up a free uptime monitor on:
     https://relay.yourdomain.com/api/health

Useful commands
---------------

  cd $APP_DIR
  docker compose logs -f      # follow logs
  docker compose restart      # restart (auto-resume brings the relay back)
  docker compose pull && docker compose up -d --build   # update

EOF

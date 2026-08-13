#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  WinVN Store - Deployment Script
#  Domain: winvn.store
#  Server: ns13507.usc1.stableserver.net (185.181.254.173)
#
#  Usage:
#    1. Upload this repo to the server
#    2. Run as root: bash deploy/deploy-winvn.sh
#
#  Path mapping:
#    /         -> tgadmin frontend (React SPA + landing page)
#    /admin    -> tgadmin backend (FastAPI + React Admin)
#    /bot      -> bot info page (tgadmin served)
# ============================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${REPO_DIR:-$ROOT_DIR}"

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root." >&2
  exit 1
fi

# --- Deployment targets ---
TGBOT_USER="tgbot"
TGADMIN_USER="tgadmin"
TGBOT_DIR="/opt/tgbot"
TGADMIN_DIR="/opt/tgadmin"
TGBOT_ENV_FILE="/etc/default/tgbot"
TGADMIN_ENV_FILE="/etc/default/tgadmin"
TGBOT_SERVICE_FILE="/etc/systemd/system/tgbot.service"
TGADMIN_SERVICE_FILE="/etc/systemd/system/tgadmin.service"
NGINX_SITE_FILE="/etc/nginx/sites-available/winvn.store"
DATABASE_PATH="/opt/shared.db"

# --- Default environment values ---
# Override by exporting before running.
BOT_TOKEN="${BOT_TOKEN:-8845776726:AAEALSwhhDv2dfOdz6x1__xM7ffyuIWc5ms}"
ABA_BOT_TOKEN="${ABA_BOT_TOKEN:-8682768706:AAE-PNNwN_kiqDz44B5zS2nbZl4Zujovqzo}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-/opt/tgbot/migrations}"
BOT_NAME="${BOT_NAME:-wing-bank}"
BOT_VERSION="${BOT_VERSION:-1.0.0}"
PUSH_BASE_URL="${PUSH_BASE_URL:-http://127.0.0.1:8000}"
POLLER_TIMEOUT="${POLLER_TIMEOUT:-30s}"

TGADMIN_HOST="${TGADMIN_HOST:-127.0.0.1}"
TGADMIN_PORT="${TGADMIN_PORT:-8000}"
TGADMIN_WORKERS="${TGADMIN_WORKERS:-2}"
TGADMIN_DEBUG="${TGADMIN_DEBUG:-false}"
TGADMIN_PAGE_SIZE="${TGADMIN_PAGE_SIZE:-20}"
TGADMIN_DATABASE_URL="${TGADMIN_DATABASE_URL:-sqlite:////opt/tgadmin/app/tgadmin.db}"
TGADMIN_BOT_TOKEN="${TGADMIN_BOT_TOKEN:-$BOT_TOKEN}"
TGADMIN_CORS_ORIGINS="${TGADMIN_CORS_ORIGINS:-https://winvn.store,https://www.winvn.store}"
DOMAIN="${DOMAIN:-winvn.store}"
ENABLE_NGINX="${ENABLE_NGINX:-true}"

echo "=========================================="
echo "  Deploying WinVN Store Services"
echo "  Domain: $DOMAIN"
echo "  Repo:   $REPO_DIR"
echo "=========================================="

# --- 1. Create service users and directories ---
echo ""
echo "[1/7] Creating service users and directories..."
useradd --system --no-create-home --shell /usr/sbin/nologin "$TGBOT_USER" 2>/dev/null || true
useradd --system --no-create-home --shell /usr/sbin/nologin "$TGADMIN_USER" 2>/dev/null || true
mkdir -p "$TGBOT_DIR" "$TGADMIN_DIR" /etc/tgbot /etc/tgadmin /opt
chown -R "$TGBOT_USER":"$TGBOT_USER" "$TGBOT_DIR" /etc/tgbot
chown -R "$TGADMIN_USER":"$TGADMIN_USER" "$TGADMIN_DIR" /etc/tgadmin

# --- 2. Sync code ---
echo ""
echo "[2/7] Syncing code..."
echo "  -> tgbot -> $TGBOT_DIR"
rsync -a --delete "$REPO_DIR/tgbot/" "$TGBOT_DIR/"
chown -R "$TGBOT_USER":"$TGBOT_USER" "$TGBOT_DIR"

echo "  -> tgadmin -> $TGADMIN_DIR"
rsync -a --delete "$REPO_DIR/tgadmin/" "$TGADMIN_DIR/"
chown -R "$TGADMIN_USER":"$TGADMIN_USER" "$TGADMIN_DIR"

# Copy shared database if it exists
if [ -f "$REPO_DIR/shared.db" ]; then
    echo "  -> shared.db -> $DATABASE_PATH"
    cp "$REPO_DIR/shared.db" "$DATABASE_PATH"
    chown "$TGBOT_USER":"$TGADMIN_USER" "$DATABASE_PATH"
    chmod 660 "$DATABASE_PATH"
fi

# --- 3. Build tgbot binary ---
echo ""
echo "[3/7] Building tgbot (Go)..."
if ! command -v go >/dev/null 2>&1; then
  echo "ERROR: Go is not installed. Please install Go before running this script." >&2
  echo "  Install: wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz && tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz" >&2
  exit 1
fi
cd "$TGBOT_DIR"
chown -R "$TGBOT_USER":"$TGBOT_USER" .
sudo -u "$TGBOT_USER" go build -o "$TGBOT_DIR/tgbot" main.go
chmod 750 "$TGBOT_DIR/tgbot"
echo "  tgbot binary built: $($TGBOT_DIR/tgbot --version 2>/dev/null || echo 'built ok')"

# --- 4. Build tgadmin frontend ---
echo ""
echo "[4/7] Building tgadmin frontend (React/Vite)..."
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm is not installed. Please install Node.js/npm before running this script." >&2
  echo "  Install: curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs" >&2
  exit 1
fi
cd "$TGADMIN_DIR/frontend"
sudo -u "$TGADMIN_USER" npm install
sudo -u "$TGADMIN_USER" npm run build
echo "  Frontend built: $(ls -la dist/index.html 2>/dev/null | awk '{print $5}') bytes"

# --- 5. Setup tgadmin Python environment ---
echo ""
echo "[5/7] Setting up tgadmin backend (Python/FastAPI)..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is not installed. Please install Python 3 before running this script." >&2
  exit 1
fi
cd "$TGADMIN_DIR"
sudo -u "$TGADMIN_USER" python3 -m venv "$TGADMIN_DIR/.venv"
sudo -u "$TGADMIN_USER" "$TGADMIN_DIR/.venv/bin/pip" install --upgrade pip setuptools
sudo -u "$TGADMIN_USER" "$TGADMIN_DIR/.venv/bin/pip" install -r "$TGADMIN_DIR/requirements.txt"

# --- 6. Write environment files ---
echo ""
echo "[6/7] Writing environment files..."

cat > "$TGBOT_ENV_FILE" <<EOF
# tgbot environment - winvn.store
BOT_TOKEN=${BOT_TOKEN}
ABA_BOT_TOKEN=${ABA_BOT_TOKEN}
ABA_BOT_NAME=aba-bank
DATABASE_PATH=${DATABASE_PATH}
MIGRATIONS_DIR=${MIGRATIONS_DIR}
BOT_NAME=${BOT_NAME}
BOT_VERSION=${BOT_VERSION}
PUSH_BASE_URL=${PUSH_BASE_URL}
POLLER_TIMEOUT=${POLLER_TIMEOUT}
EOF
chmod 640 "$TGBOT_ENV_FILE"
chown root:"$TGBOT_USER" "$TGBOT_ENV_FILE"

cat > "$TGADMIN_ENV_FILE" <<EOF
# tgadmin environment - winvn.store
TGADMIN_HOST=${TGADMIN_HOST}
TGADMIN_PORT=${TGADMIN_PORT}
TGADMIN_WORKERS=${TGADMIN_WORKERS}
TGADMIN_DEBUG=${TGADMIN_DEBUG}
TGADMIN_PAGE_SIZE=${TGADMIN_PAGE_SIZE}
TGADMIN_DATABASE_URL=${TGADMIN_DATABASE_URL}
BOT_TOKEN=${BOT_TOKEN}
TGADMIN_BOT_TOKEN=${TGADMIN_BOT_TOKEN:-$BOT_TOKEN}
ABA_BOT_TOKEN=${ABA_BOT_TOKEN}
TGADMIN_ABA_BOT_TOKEN=${TGADMIN_ABA_BOT_TOKEN:-$ABA_BOT_TOKEN}
EXTRA_BOT_TOKENS=${EXTRA_BOT_TOKENS}
TGADMIN_EXTRA_BOT_TOKENS=${TGADMIN_EXTRA_BOT_TOKENS:-$EXTRA_BOT_TOKENS}
TGADMIN_CORS_ORIGINS=${TGADMIN_CORS_ORIGINS}
EOF
chmod 640 "$TGADMIN_ENV_FILE"
chown root:"$TGADMIN_USER" "$TGADMIN_ENV_FILE"

# --- 7. Create systemd unit files ---
echo ""
echo "[7/7] Creating systemd services..."

cat > "$TGBOT_SERVICE_FILE" <<'EOF'
[Unit]
Description=TGBot - Telegram Bot Service (winvn.store)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=tgbot
Group=tgbot
WorkingDirectory=/opt/tgbot
EnvironmentFile=/etc/default/tgbot
ExecStart=/opt/tgbot/tgbot
Restart=on-failure
RestartSec=5s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

cat > "$TGADMIN_SERVICE_FILE" <<EOF
[Unit]
Description=TGAdmin - FastAPI Admin Panel (winvn.store)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=tgadmin
Group=tgadmin
WorkingDirectory=/opt/tgadmin
EnvironmentFile=/etc/default/tgadmin
Environment=PYTHONPATH=/opt/tgadmin
ExecStart=/opt/tgadmin/.venv/bin/uvicorn app.main:app \
  --host \${TGADMIN_HOST:-127.0.0.1} \
  --port \${TGADMIN_PORT:-8000} \
  --workers \${TGADMIN_WORKERS:-2} \
  --log-level info
Restart=on-failure
RestartSec=5s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# --- Nginx configuration ---
if [ "$ENABLE_NGINX" = "true" ] || [ "$ENABLE_NGINX" = "1" ]; then
  echo ""
  echo "Configuring nginx..."
  if command -v nginx >/dev/null 2>&1; then
    cp "$REPO_DIR/deploy/nginx-winvn.conf" "$NGINX_SITE_FILE"
    ln -sf "$NGINX_SITE_FILE" /etc/nginx/sites-enabled/winvn.store
    nginx -t && systemctl reload nginx
    echo "  Nginx configured and reloaded."
  else
    echo "  WARNING: nginx not installed, skipping nginx configuration." >&2
    echo "  Install with: apt-get install -y nginx"
  fi
fi

# --- Start services ---
echo ""
echo "Starting services..."
systemctl daemon-reload

enable_and_start() {
  local unit="$1"
  systemctl enable --now "$unit" 2>/dev/null || true
  systemctl restart "$unit"
  sleep 2
  if systemctl is-active --quiet "$unit"; then
    echo "  ✓ $unit - running"
  else
    echo "  ✗ $unit - FAILED"
    journalctl -u "$unit" -n 20 --no-pager
  fi
}

enable_and_start tgbot.service
enable_and_start tgadmin.service

# --- Summary ---
echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "  Domain:    https://winvn.store"
echo ""
echo "  Paths:"
echo "    /        -> Frontend (React SPA + Landing)"
echo "    /admin   -> Admin Panel (React + FastAPI)"
echo "    /bot     -> Bot Info Page"
echo ""
echo "  Services:"
echo "    tgbot.service    - Telegram bot (long-polling)"
echo "    tgadmin.service  - FastAPI backend + React frontend"
echo ""
echo "  Useful commands:"
echo "    systemctl status tgbot.service"
echo "    systemctl status tgadmin.service"
echo "    journalctl -u tgbot.service -f"
echo "    journalctl -u tgadmin.service -f"
echo ""
echo "  Next steps:"
echo "    1. Configure SSL with Certbot:"
echo "       certbot --nginx -d winvn.store -d www.winvn.store"
echo "    2. Update bot webhook if using webhook mode"
echo "    3. Change default admin password in /etc/default/tgadmin"
echo ""

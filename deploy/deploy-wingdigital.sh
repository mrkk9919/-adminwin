#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${REPO_DIR:-$ROOT_DIR}"

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root." >&2
  exit 1
fi

# Deployment targets
TGBOT_USER="tgbot"
TGADMIN_USER="tgadmin"
TGBOT_DIR="/opt/tgbot"
TGADMIN_DIR="/opt/tgadmin"
TGBOT_ENV_FILE="/etc/default/tgbot"
TGADMIN_ENV_FILE="/etc/default/tgadmin"
TGBOT_SERVICE_FILE="/etc/systemd/system/tgbot.service"
TGADMIN_SERVICE_FILE="/etc/systemd/system/tgadmin.service"
NGINX_SITE_FILE="/etc/nginx/sites-available/wingdigital.fit"

# Default environment values. Override by exporting before running.
BOT_TOKEN="${BOT_TOKEN:-8845776726:AAEALSwhhDv2dfOdz6x1__xM7ffyuIWc5ms}"
ABA_BOT_TOKEN="${ABA_BOT_TOKEN:-8682768706:AAE-PNNwN_kiqDz44B5zS2nbZl4Zujovqzo}"
DATABASE_PATH="${DATABASE_PATH:-/opt/shared.db}"
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
TGADMIN_CORS_ORIGINS="${TGADMIN_CORS_ORIGINS:-https://wingdigital.fit}"
DOMAIN="${DOMAIN:-wingdigital.fit}"
ENABLE_NGINX="${ENABLE_NGINX:-true}"

echo "Deploying WingDigital services from $REPO_DIR"

# Create service users and directories.
useradd --system --no-create-home --shell /usr/sbin/nologin "$TGBOT_USER" 2>/dev/null || true
useradd --system --no-create-home --shell /usr/sbin/nologin "$TGADMIN_USER" 2>/dev/null || true
mkdir -p "$TGBOT_DIR" "$TGADMIN_DIR" /etc/tgbot /etc/tgadmin
chown -R "$TGBOT_USER":"$TGBOT_USER" "$TGBOT_DIR" /etc/tgbot
chown -R "$TGADMIN_USER":"$TGADMIN_USER" "$TGADMIN_DIR" /etc/tgadmin

# Sync code to target locations.
echo "Syncing tgbot code to $TGBOT_DIR"
rsync -a --delete "$REPO_DIR/tgbot/" "$TGBOT_DIR/"
chown -R "$TGBOT_USER":"$TGBOT_USER" "$TGBOT_DIR"

echo "Syncing tgadmin code to $TGADMIN_DIR"
rsync -a --delete "$REPO_DIR/tgadmin/" "$TGADMIN_DIR/"
chown -R "$TGADMIN_USER":"$TGADMIN_USER" "$TGADMIN_DIR"

# Build tgbot binary.
if ! command -v go >/dev/null 2>&1; then
  echo "Go is not installed. Please install Go before running this script." >&2
  exit 1
fi
cd "$TGBOT_DIR"
chown -R "$TGBOT_USER":"$TGBOT_USER" .
sudo -u "$TGBOT_USER" go build -o "$TGBOT_DIR/tgbot" main.go
chmod 750 "$TGBOT_DIR/tgbot"

# Build tgadmin frontend.
if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not installed. Please install Node.js/npm before running this script." >&2
  exit 1
fi
cd "$TGADMIN_DIR/frontend"
sudo -u "$TGADMIN_USER" npm install
sudo -u "$TGADMIN_USER" npm run build

# Create tgadmin virtualenv.
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed. Please install Python 3 before running this script." >&2
  exit 1
fi
cd "$TGADMIN_DIR"
sudo -u "$TGADMIN_USER" python3 -m venv "$TGADMIN_DIR/.venv"
sudo -u "$TGADMIN_USER" "$TGADMIN_DIR/.venv/bin/pip" install --upgrade pip setuptools
sudo -u "$TGADMIN_USER" "$TGADMIN_DIR/.venv/bin/pip" install -r "$TGADMIN_DIR/requirements.txt"

# Write environment files.
cat > "$TGBOT_ENV_FILE" <<EOF
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

cat > "$TGADMIN_ENV_FILE" <<EOF
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

# Create systemd unit files.
cat > "$TGBOT_SERVICE_FILE" <<'EOF'
[Unit]
Description=TGBot service
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
Description=TGAdmin (FastAPI) service
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
  --host \\${TGADMIN_HOST:-127.0.0.1} \
  --port \\${TGADMIN_PORT:-8000} \
  --workers \\${TGADMIN_WORKERS:-2} \
  --log-level info
Restart=on-failure
RestartSec=5s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# Optionally configure nginx.
if [ "$ENABLE_NGINX" = "true" ] || [ "$ENABLE_NGINX" = "1" ]; then
  if command -v nginx >/dev/null 2>&1; then
    cat > "$NGINX_SITE_FILE" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${TGADMIN_PORT};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
    ln -sf "$NGINX_SITE_FILE" /etc/nginx/sites-enabled/wingdigital.fit
    nginx -t
    systemctl restart nginx
  else
    echo "nginx not installed, skipping nginx configuration." >&2
  fi
fi

# Reload and start services.
systemctl daemon-reload
enable_and_start() {
  local unit="$1"
  systemctl enable --now "$unit"
  systemctl restart "$unit"
  systemctl status --no-pager "$unit"
}
enable_and_start tgbot.service
enable_and_start tgadmin.service

echo "Deployment complete. Verify http://$DOMAIN/ and http://$DOMAIN/admin"

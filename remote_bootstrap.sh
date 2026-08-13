#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 REMOTE_PATH DOMAIN"; exit 1
fi
REMOTE_PATH="$1"
DOMAIN="$2"

# Basic vars
ADMIN_PORT=8001
TGADMIN_PORT=8002
# tgbot runs as a systemd service (no HTTP exposed)

echo "Bootstrap on remote: install packages, create venvs, build projects, configure services"

# Ensure sudo is available
if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required but not found. Aborting."; exit 1
fi

# Create remote path
sudo mkdir -p "${REMOTE_PATH}"
sudo chown -R $(whoami):$(whoami) "${REMOTE_PATH}"

# Install system packages (CentOS Stream 10 / dnf)
echo "Installing system packages (nginx, python3, nodejs, npm, golang, git, certbot)..."
# Enable EPEL if needed
sudo dnf -y install epel-release || true
sudo dnf -y update
sudo dnf -y install nginx git python3 python3-venv python3-pip nodejs npm golang

# Install certbot from EPEL or snap fallback
if ! command -v certbot >/dev/null 2>&1; then
  sudo dnf -y install certbot python3-certbot-nginx || true
fi

# Create directories
mkdir -p "${REMOTE_PATH}/tgbot"
mkdir -p "${REMOTE_PATH}/admin"
mkdir -p "${REMOTE_PATH}/tgadmin"

# Move synced files into place if rsync put them under REMOTE_PATH/ (they already are in REMOTE_PATH)
# Build Go tgbot
if [[ -d "${REMOTE_PATH}/tgbot" ]]; then
  echo "Building Go bot..."
  (cd "${REMOTE_PATH}/tgbot" && go build -o "${REMOTE_PATH}/bin/tgbot" main.go) || echo "Go build failed; ensure Go sources exist and main.go is present"
fi

# Setup admin (Python)
if [[ -d "${REMOTE_PATH}/admin" ]]; then
  echo "Setting up admin backend..."
  python3 -m venv "${REMOTE_PATH}/admin/venv"
  source "${REMOTE_PATH}/admin/venv/bin/activate"
  if [[ -f "${REMOTE_PATH}/admin/requirements.txt" ]]; then
    pip install --upgrade pip
    pip install -r "${REMOTE_PATH}/admin/requirements.txt"
  else
    echo "No requirements.txt in admin/, skipping pip install"
  fi
  deactivate
fi

# Setup tgadmin backend
if [[ -d "${REMOTE_PATH}/tgadmin" ]]; then
  echo "Setting up tgadmin backend..."
  if [[ -f "${REMOTE_PATH}/tgadmin/requirements.txt" ]]; then
    python3 -m venv "${REMOTE_PATH}/tgadmin/venv"
    source "${REMOTE_PATH}/tgadmin/venv/bin/activate"
    pip install --upgrade pip
    pip install -r "${REMOTE_PATH}/tgadmin/requirements.txt"
    deactivate
  else
    echo "No requirements.txt in tgadmin/, skipping pip install"
  fi
fi

# Build frontend (tgadmin/frontend)
if [[ -d "${REMOTE_PATH}/tgadmin/frontend" ]]; then
  echo "Building frontend..."
  (cd "${REMOTE_PATH}/tgadmin/frontend" && npm ci && npm run build) || echo "Frontend build failed; ensure Node/npm availability"
  # Copy build to web root
  sudo mkdir -p /var/www/${DOMAIN}
  sudo rm -rf /var/www/${DOMAIN}/* || true
  sudo cp -r "${REMOTE_PATH}/tgadmin/frontend/dist/"* /var/www/${DOMAIN}/ || true
  sudo chown -R $(whoami):$(whoami) /var/www/${DOMAIN}
fi

# Create systemd service for tgbot
sudo mkdir -p /etc/systemd/system
cat > /tmp/tgbot.service <<'EOF'
[Unit]
Description=TgBot Service
After=network.target

[Service]
Type=simple
User=%s
WorkingDirectory=%s/tgbot
ExecStart=%s/bin/tgbot
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

printf "$(cat /tmp/tgbot.service)" | sed "s/%s/$(whoami)/g; s#%s#${REMOTE_PATH}#g; s#%s#${REMOTE_PATH}#g" > /tmp/tgbot.service.out || true
sudo mv /tmp/tgbot.service.out /etc/systemd/system/tgbot.service || true

# admin (uvicorn) systemd service
cat > /tmp/admin.service <<EOF
[Unit]
Description=Admin FastAPI (uvicorn)
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=${REMOTE_PATH}/admin
Environment=PATH=${REMOTE_PATH}/admin/venv/bin
ExecStart=${REMOTE_PATH}/admin/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${ADMIN_PORT}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo mv /tmp/admin.service /etc/systemd/system/admin.service

# tgadmin backend service
cat > /tmp/tgadmin.service <<EOF
[Unit]
Description=tgadmin FastAPI (uvicorn)
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=${REMOTE_PATH}/tgadmin
Environment=PATH=${REMOTE_PATH}/tgadmin/venv/bin
ExecStart=${REMOTE_PATH}/tgadmin/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${TGADMIN_PORT}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo mv /tmp/tgadmin.service /etc/systemd/system/tgadmin.service

# Reload systemd
sudo systemctl daemon-reload
sudo systemctl enable --now nginx || true
sudo systemctl enable --now tgbot.service || true
sudo systemctl enable --now admin.service || true
sudo systemctl enable --now tgadmin.service || true

# Configure nginx
NGINX_CONF="/etc/nginx/conf.d/${DOMAIN}.conf"
cat > /tmp/nginx_site.conf <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    root /var/www/${DOMAIN};
    index index.html index.htm;

    location /admin/ {
        proxy_pass http://127.0.0.1:${ADMIN_PORT}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${TGADMIN_PORT}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # try files for SPA
    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

sudo mv /tmp/nginx_site.conf ${NGINX_CONF}
sudo nginx -t && sudo systemctl reload nginx || echo "nginx config test failed"

# Obtain TLS cert via certbot (non-interactive)
if command -v certbot >/dev/null 2>&1; then
  echo "Requesting TLS cert for ${DOMAIN} via certbot..."
  sudo certbot --nginx -d "${DOMAIN}" --agree-tos --non-interactive -m "admin@${DOMAIN}" || echo "certbot failed; please run certbot manually"
else
  echo "certbot not available; install certbot and run: sudo certbot --nginx -d ${DOMAIN}"
fi

# Final reloads
sudo systemctl daemon-reload
sudo systemctl restart nginx || true
sudo systemctl restart tgbot.service || true
sudo systemctl restart admin.service || true
sudo systemctl restart tgadmin.service || true

echo "Bootstrap finished. Services: tgbot, admin(${ADMIN_PORT}), tgadmin(${TGADMIN_PORT}). Frontend served at https://${DOMAIN} (if cert obtained)."

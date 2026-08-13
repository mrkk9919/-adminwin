#!/bin/bash
set -e

# ============================================================
# Wing Bank Telegram Bot - Complete Deployment Script
# Supports: CentOS Stream 10 / Ubuntu 22.04+ / Debian 12
# ============================================================

# Configuration - EDIT THESE VALUES
DOMAIN="your-domain.com"
ADMIN_USER="www-data"
INSTALL_DIR="/opt/wingbank"
GIT_REPO="git@github.com:mrkk9919/-adminwin.git"
EMAIL="admin@your-domain.com"  # For Certbot

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        error "Cannot detect OS"
    fi
    log "Detected OS: $OS $VERSION"
}

# Install system dependencies
install_deps() {
    log "Installing system dependencies..."
    case $OS in
        centos|rhel|rocky|almalinux)
            dnf install -y epel-release
            dnf install -y git python3 python3-pip python3-venv golang nginx certbot python3-certbot-nginx
            ;;
        ubuntu|debian)
            apt update
            apt install -y git python3 python3-pip python3-venv golang nginx certbot python3-certbot-nginx
            ;;
        *)
            error "Unsupported OS: $OS"
            ;;
    esac
    log "Dependencies installed"
}

# Create directory structure
setup_dirs() {
    log "Creating directory structure..."
    mkdir -p $INSTALL_DIR
    mkdir -p /var/www/certbot
    mkdir -p /var/log/wingbank
    log "Directories created"
}

# Clone or update repository
clone_repo() {
    if [ -d "$INSTALL_DIR/.git" ]; then
        log "Updating existing repository..."
        cd $INSTALL_DIR
        git pull origin main
    else
        log "Cloning repository..."
        git clone $GIT_REPO $INSTALL_DIR
    fi
}

# Build Go bot
build_tgbot() {
    log "Building Telegram bot (Go)..."
    cd $INSTALL_DIR/tgbot
    go mod download
    CGO_ENABLED=1 GOOS=linux GOARCH=amd64 go build -o tgbot .
    chmod +x tgbot
    log "Bot built successfully"
}

# Setup Python admin panel
setup_admin() {
    log "Setting up Admin panel (Python)..."
    cd $INSTALL_DIR/admin
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    log "Admin panel setup complete"
}

# Setup Python tgadmin
setup_tgadmin() {
    log "Setting up TGAdmin (Python)..."
    cd $INSTALL_DIR/tgadmin
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate

    # Build frontend if exists
    if [ -d "frontend" ]; then
        log "Building frontend..."
        cd frontend
        npm install
        npm run build
        cd ..
    fi
    log "TGAdmin setup complete"
}

# Setup environment files
setup_env() {
    log "Setting up environment files..."

    # tgbot .env
    if [ ! -f "$INSTALL_DIR/tgbot/.env" ]; then
        cp $INSTALL_DIR/tgbot/.env.example $INSTALL_DIR/tgbot/.env
        warn "Edit $INSTALL_DIR/tgbot/.env with your bot token"
    fi

    # admin .env
    if [ ! -f "$INSTALL_DIR/admin/.env" ]; then
        cp $INSTALL_DIR/admin/.env.example $INSTALL_DIR/admin/.env
        warn "Edit $INSTALL_DIR/admin/.env with your admin credentials"
    fi

    # tgadmin .env
    if [ ! -f "$INSTALL_DIR/tgadmin/.env" ]; then
        cp $INSTALL_DIR/tgadmin/.env.example $INSTALL_DIR/tgadmin/.env
        warn "Edit $INSTALL_DIR/tgadmin/.env with your configuration"
    fi
}

# Setup systemd services
setup_systemd() {
    log "Setting up systemd services..."

    cp $INSTALL_DIR/deploy/systemd/tgbot.service /etc/systemd/system/
    cp $INSTALL_DIR/deploy/systemd/admin.service /etc/systemd/system/
    cp $INSTALL_DIR/deploy/systemd/tgadmin.service /etc/systemd/system/

    # Set permissions
    chown -R $ADMIN_USER:$ADMIN_USER $INSTALL_DIR

    systemctl daemon-reload
    systemctl enable tgbot admin tgadmin
    log "Systemd services enabled"
}

# Setup Nginx
setup_nginx() {
    log "Setting up Nginx..."

    # Remove default config
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
    rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true

    # Copy HTTP config first for Certbot validation
    cp $INSTALL_DIR/deploy/nginx/wingbank-http.conf /etc/nginx/conf.d/wingbank.conf
    sed -i "s/YOUR_DOMAIN/$DOMAIN/g" /etc/nginx/conf.d/wingbank.conf

    nginx -t
    systemctl restart nginx
    log "Nginx HTTP config active"
}

# Get TLS certificate
setup_tls() {
    log "Obtaining TLS certificate..."

    certbot certonly --webroot \
        -w /var/www/certbot \
        -d $DOMAIN \
        -d www.$DOMAIN \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        --non-interactive

    # Switch to SSL config
    cp $INSTALL_DIR/deploy/nginx/wingbank-ssl.conf /etc/nginx/conf.d/wingbank.conf
    sed -i "s/YOUR_DOMAIN/$DOMAIN/g" /etc/nginx/conf.d/wingbank.conf

    nginx -t
    systemctl restart nginx
    log "TLS certificate installed and HTTPS active"
}

# Start all services
start_services() {
    log "Starting all services..."
    systemctl start tgbot
    systemctl start admin
    systemctl start tgadmin

    sleep 3

    # Check status
    systemctl status tgbot --no-pager | head -5
    systemctl status admin --no-pager | head -5
    systemctl status tgadmin --no-pager | head -5
}

# Setup firewall
setup_firewall() {
    log "Configuring firewall..."
    case $OS in
        centos|rhel|rocky|almalinux)
            firewall-cmd --permanent --add-service=http
            firewall-cmd --permanent --add-service=https
            firewall-cmd --reload
            ;;
        ubuntu|debian)
            ufw allow 'Nginx Full'
            ufw --force enable
            ;;
    esac
    log "Firewall configured"
}

# Setup auto-renewal for certificates
setup_certbot_renewal() {
    log "Setting up automatic certificate renewal..."
    # Certbot packages usually set up a systemd timer
    systemctl enable certbot-renew.timer 2>/dev/null || true
    systemctl start certbot-renew.timer 2>/dev/null || true
    log "Certificate auto-renewal configured"
}

# Main
main() {
    log "=== Wing Bank Deployment Script ==="
    log "Domain: $DOMAIN"
    log "Install dir: $INSTALL_DIR"
    echo ""

    detect_os
    install_deps
    setup_dirs
    clone_repo
    build_tgbot
    setup_admin
    setup_tgadmin
    setup_env
    setup_systemd
    setup_nginx
    setup_firewall
    setup_tls
    setup_certbot_renewal
    start_services

    echo ""
    log "=== Deployment Complete ==="
    log "Website: https://$DOMAIN"
    log "Admin: https://$DOMAIN/admin/"
    echo ""
    warn "IMPORTANT: Edit the .env files before starting services:"
    warn "  $INSTALL_DIR/tgbot/.env"
    warn "  $INSTALL_DIR/admin/.env"
    warn "  $INSTALL_DIR/tgadmin/.env"
    echo ""
    log "After editing .env files, restart services with:"
    log "  systemctl restart tgbot admin tgadmin"
}

# Run main
main "$@"

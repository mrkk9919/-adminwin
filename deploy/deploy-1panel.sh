#!/bin/bash
# Wing Bank Telegram Bot - 1Panel 一键部署脚本
# 用法：bash deploy/deploy-1panel.sh

set -e

echo "=========================================="
echo "  Wing Bank Bot - 1Panel 一键部署脚本"
echo "=========================================="
echo ""

# 配置变量
INSTALL_DIR="/opt/wingbank-bot"
ADMIN_PORT=8000
BOT_TOKEN="8682768706:AAGFDk_dsW_-HTwNUijPMR66rjumeQFupZg"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin123"
JWT_SECRET=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then 
    error "请使用 root 用户运行此脚本"
    exit 1
fi

# 获取当前脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

info "项目目录: $PROJECT_DIR"
info "安装目录: $INSTALL_DIR"
echo ""

# ==========================================
# 步骤 1：安装系统依赖
# ==========================================
info "步骤 1/6: 安装系统依赖..."

if command -v apt &> /dev/null; then
    # Debian/Ubuntu
    apt update -y
    apt install -y python3 python3-venv python3-pip sqlite3 curl wget unzip
elif command -v yum &> /dev/null; then
    # CentOS/RHEL
    yum install -y python3 python3-venv python3-pip sqlite curl wget unzip
else
    warn "无法确定系统类型，请手动安装 Python 3 和 SQLite"
fi

info "系统依赖安装完成"
echo ""

# ==========================================
# 步骤 2：复制代码到安装目录
# ==========================================
info "步骤 2/6: 复制代码到安装目录..."

if [ -d "$INSTALL_DIR" ]; then
    warn "安装目录已存在，是否覆盖？(y/n)"
    read -p "请输入: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "取消部署"
        exit 0
    fi
    rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"
cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/"

info "代码复制完成"
echo ""

# ==========================================
# 步骤 3：配置管理后台（Admin）
# ==========================================
info "步骤 3/6: 配置管理后台..."

cd "$INSTALL_DIR/admin"

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建 .env 文件
cat > .env << EOF
# Wing Bank Telegram Bot — Admin Panel
BOT_TOKEN=$BOT_TOKEN
DATABASE_PATH=$INSTALL_DIR/shared.db
ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=$ADMIN_PASSWORD
JWT_SECRET=$JWT_SECRET
HOST=0.0.0.0
PORT=$ADMIN_PORT
ALLOWED_IPS=
FCM_SERVER_KEY=
PAYMENT_API_TOKEN=6da90fc90e0b5468554082c8d364300f1224db89abdece7b
ADMIN_TELEGRAM_ID=8619129145
SMS_PROVIDER=WINGSMS
SMS_API_KEY=
SMS_API_SECRET=
EOF

info "管理后台配置完成"
echo ""

# ==========================================
# 步骤 4：配置机器人（TGBot）
# ==========================================
info "步骤 4/6: 配置 Telegram 机器人..."

cd "$INSTALL_DIR/tgbot"

# 检查是否有预编译的二进制文件
if [ -f "tgbot-linux-amd64" ]; then
    info "找到预编译的二进制文件"
    cp tgbot-linux-amd64 tgbot
    chmod +x tgbot
elif command -v go &> /dev/null; then
    info "检测到 Go 环境，开始编译..."
    go build -o tgbot main.go
else
    warn "未找到 Go 环境，也没有预编译的二进制文件"
    warn "请在本地编译后上传 tgbot-linux-amd64 文件"
    warn "或者在服务器上安装 Go 环境"
    echo ""
    warn "跳过机器人部署，只部署管理后台"
    SKIP_BOT=true
fi

# 创建配置文件（如果需要）
if [ ! -f "config.yaml" ]; then
    cat > config.yaml << EOF
bot:
  token: "$BOT_TOKEN"
  debug: false

database:
  path: "$INSTALL_DIR/shared.db"

push:
  base_url: "http://localhost:$ADMIN_PORT"
EOF
fi

info "机器人配置完成"
echo ""

# ==========================================
# 步骤 5：配置 systemd 服务
# ==========================================
info "步骤 5/6: 配置 systemd 服务..."

# 创建管理后台服务
cat > /etc/systemd/system/wingbank-admin.service << EOF
[Unit]
Description=Wing Bank Admin Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/admin
Environment="PATH=$INSTALL_DIR/admin/venv/bin"
ExecStart=$INSTALL_DIR/admin/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $ADMIN_PORT
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 创建机器人服务（如果没有跳过）
if [ "$SKIP_BOT" != "true" ]; then
    cat > /etc/systemd/system/wingbank-tgbot.service << EOF
[Unit]
Description=Wing Bank Telegram Bot
After=network.target wingbank-admin.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/tgbot
Environment="BOT_TOKEN=$BOT_TOKEN"
Environment="DATABASE_PATH=$INSTALL_DIR/shared.db"
Environment="PUSH_BASE_URL=http://localhost:$ADMIN_PORT"
ExecStart=$INSTALL_DIR/tgbot/tgbot
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
fi

# 重新加载 systemd
systemctl daemon-reload

info "systemd 服务配置完成"
echo ""

# ==========================================
# 步骤 6：启动服务
# ==========================================
info "步骤 6/6: 启动服务..."

# 启动管理后台
systemctl enable wingbank-admin
systemctl start wingbank-admin

# 等待一下
sleep 3

# 检查管理后台状态
if systemctl is-active --quiet wingbank-admin; then
    info "管理后台启动成功"
else
    error "管理后台启动失败，请查看日志：journalctl -u wingbank-admin -n 50"
fi

# 启动机器人（如果没有跳过）
if [ "$SKIP_BOT" != "true" ]; then
    systemctl enable wingbank-tgbot
    systemctl start wingbank-tgbot
    
    sleep 3
    
    if systemctl is-active --quiet wingbank-tgbot; then
        info "机器人启动成功"
    else
        warn "机器人启动失败，请查看日志：journalctl -u wingbank-tgbot -n 50"
    fi
fi

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "📊 服务状态："
echo "   - 管理后台: $(systemctl is-active wingbank-admin)"
if [ "$SKIP_BOT" != "true" ]; then
    echo "   - 机器人: $(systemctl is-active wingbank-tgbot)"
fi
echo ""
echo "🌐 访问地址："
echo "   - 管理后台: http://$(curl -s ifconfig.me):$ADMIN_PORT"
echo "   - 用户名: $ADMIN_USERNAME"
echo "   - 密码: $ADMIN_PASSWORD"
echo ""
echo "⚠️  重要提示："
echo "   1. 请尽快修改管理员密码！"
echo "   2. 请配置防火墙，只允许必要的端口访问"
echo "   3. 建议配置 HTTPS（SSL 证书）"
echo ""
echo "📝 常用命令："
echo "   查看管理后台日志: journalctl -u wingbank-admin -f"
echo "   查看机器人日志: journalctl -u wingbank-tgbot -f"
echo "   重启管理后台: systemctl restart wingbank-admin"
echo "   重启机器人: systemctl restart wingbank-tgbot"
echo ""

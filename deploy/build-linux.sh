#!/bin/bash
# 本地编译 Go 程序为 Linux 版本
# 用法：bash build-linux.sh

set -e

echo "=========================================="
echo "  Wing Bank Bot - Linux 编译脚本"
echo "=========================================="
echo ""

# 获取当前脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TGBOT_DIR="$PROJECT_DIR/tgbot"

cd "$TGBOT_DIR"

echo "📁 工作目录: $TGBOT_DIR"
echo ""

# 检查 Go 是否安装
if ! command -v go &> /dev/null; then
    echo "❌ 未找到 Go 环境，请先安装 Go"
    exit 1
fi

echo "🔍 Go 版本: $(go version)"
echo ""

# 编译 Linux AMD64 版本
echo "🔨 开始编译 Linux AMD64 版本..."
GOOS=linux GOARCH=amd64 go build -o tgbot-linux-amd64 main.go

echo ""
echo "✅ 编译完成！"
echo ""
echo "📦 输出文件: $TGBOT_DIR/tgbot-linux-amd64"
echo "📦 文件大小: $(du -h tgbot-linux-amd64 | awk '{print $1}')"
echo ""
echo "📤 下一步："
echo "   1. 登录 1Panel 面板"
echo "   2. 进入文件管理器"
echo "   3. 上传 tgbot-linux-amd64 到 /opt/wingbank-bot/tgbot/ 目录"
echo "   4. 给文件添加执行权限"
echo "   5. 启动机器人服务"
echo ""

#!/bin/bash
# Telegram Bot 启动脚本
# 用于 macOS launchd 服务

cd "/Volumes/CODE/telegram bot/tgbot"

# 加载 .env 文件
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 启动 bot
exec ./tgbot

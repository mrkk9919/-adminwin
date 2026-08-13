#!/bin/bash
# Wing Bank 服务管理脚本 (macOS)
# 用法: ./manage-mac.sh [start|stop|restart|status|logs]

PLIST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="/Volumes/CODE/telegram bot/logs"

SERVICES=(
    "com.wingbank.admin"
    "com.wingbank.tgbot"
)

case "$1" in
    start)
        echo "🚀 启动所有服务..."
        for svc in "${SERVICES[@]}"; do
            launchctl load "$PLIST_DIR/$svc.plist" 2>/dev/null
            echo "  ✅ $svc"
        done
        echo ""
        echo "✅ 所有服务已启动"
        ;;
    
    stop)
        echo "🛑 停止所有服务..."
        for svc in "${SERVICES[@]}"; do
            launchctl unload "$PLIST_DIR/$svc.plist" 2>/dev/null
            echo "  ⏹️  $svc"
        done
        echo ""
        echo "✅ 所有服务已停止"
        ;;
    
    restart)
        echo "🔄 重启所有服务..."
        for svc in "${SERVICES[@]}"; do
            launchctl unload "$PLIST_DIR/$svc.plist" 2>/dev/null
            sleep 1
            launchctl load "$PLIST_DIR/$svc.plist" 2>/dev/null
            echo "  🔄 $svc"
        done
        echo ""
        echo "✅ 所有服务已重启"
        ;;
    
    status)
        echo "📊 服务状态:"
        echo ""
        for svc in "${SERVICES[@]}"; do
            pid=$(launchctl list | grep "$svc" | awk '{print $1}')
            if [ -n "$pid" ] && [ "$pid" != "-" ]; then
                echo "  ✅ $svc (PID: $pid)"
            else
                echo "  ❌ $svc (未运行)"
            fi
        done
        echo ""
        echo "🌐 端口:"
        if lsof -ti :8082 > /dev/null 2>&1; then
            echo "  ✅ 8082 (Admin 后台)"
        else
            echo "  ❌ 8082 (未监听)"
        fi
        ;;
    
    logs)
        echo "📋 查看日志 (按 Ctrl+C 退出)"
        echo ""
        echo "Admin 日志: $LOG_DIR/admin.log"
        echo "Bot 日志:   $LOG_DIR/tgbot.log"
        echo ""
        if [ "$2" = "admin" ]; then
            tail -f "$LOG_DIR/admin.log"
        elif [ "$2" = "bot" ]; then
            tail -f "$LOG_DIR/tgbot.log"
        else
            echo "用法: ./manage-mac.sh logs [admin|bot]"
        fi
        ;;
    
    *)
        echo "Wing Bank 服务管理脚本 (macOS)"
        echo ""
        echo "用法: $0 [命令]"
        echo ""
        echo "命令:"
        echo "  start     启动所有服务"
        echo "  stop      停止所有服务"
        echo "  restart   重启所有服务"
        echo "  status    查看服务状态"
        echo "  logs      查看日志"
        echo ""
        echo "示例:"
        echo "  $0 start"
        echo "  $0 status"
        echo "  $0 logs admin"
        echo "  $0 logs bot"
        ;;
esac

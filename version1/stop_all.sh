#!/bin/bash
# 标注系统一键停止脚本

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "======================================"
echo "  标注系统一键停止"
echo "======================================"
echo ""

echo "停止Nginx..."
sudo systemctl stop nginx 2>/dev/null

echo "停止后端服务..."
pkill -f "backend.main" 2>/dev/null

echo "停止前端服务..."
pkill -f "http.server" 2>/dev/null

sleep 1

# 验证是否已停止
REMAINING=$(ps aux | grep -E 'backend.main|http.server|nginx: master' | grep -v grep)

if [ -z "$REMAINING" ]; then
    echo -e "${GREEN}所有服务已停止${NC}"
else
    echo -e "${RED}以下进程仍在运行:${NC}"
    echo "$REMAINING"
    echo ""
    echo "强制停止命令:"
    echo "  pkill -9 -f 'backend.main'"
    echo "  pkill -9 -f 'http.server'"
    echo "  sudo systemctl stop nginx"
fi

echo ""

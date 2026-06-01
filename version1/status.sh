#!/bin/bash
# 标注系统状态检查脚本

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================"
echo "  标注系统状态检查"
echo "======================================"
echo ""

# 检查进程
echo "进程状态:"
NGINX=$(ps aux | grep "nginx: master" | grep -v grep)
BACKEND=$(ps aux | grep "backend.main" | grep -v grep)
FRONTEND=$(ps aux | grep "http.server" | grep -v grep)

if [ -n "$NGINX" ]; then
    echo -e "  ${GREEN}✓ Nginx${NC}"
else
    echo -e "  ${RED}✗ Nginx${NC}"
fi

if [ -n "$BACKEND" ]; then
    echo -e "  ${GREEN}✓ 后端 (8000)${NC}"
else
    echo -e "  ${RED}✗ 后端 (8000)${NC}"
fi

if [ -n "$FRONTEND" ]; then
    echo -e "  ${GREEN}✓ 前端 (5173)${NC}"
else
    echo -e "  ${RED}✗ 前端 (5173)${NC}"
fi

echo ""

# 检查端口
echo "端口监听:"
ss -tlnp | grep -E ':80|:8000|:5173' | while read line; do
    echo "  $line"
done

echo ""

# 测试服务
echo "服务测试:"
HEALTH=$(curl -s http://127.0.0.1/api/health 2>/dev/null)
if [ "$HEALTH" = '{"status": "ok"}' ]; then
    echo -e "  ${GREEN}✓ API接口正常${NC}"
else
    echo -e "  ${RED}✗ API接口异常${NC}"
fi

FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/ 2>/dev/null)
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo -e "  ${GREEN}✓ 前端页面正常${NC}"
else
    echo -e "  ${RED}✗ 前端页面异常${NC}"
fi

echo ""

# 防火墙状态
echo "防火墙状态:"
UFW=$(sudo ufw status 2>/dev/null | head -1)
if [ "$UFW" = "Status: inactive" ]; then
    echo -e "  ${YELLOW}UFW 未启用${NC}"
else
    sudo ufw status | grep -E '80|8000|5173' | while read line; do
        echo "  $line"
    done
fi

echo ""

# 服务器IP
echo "服务器信息:"
IP=$(curl -s ifconfig.me 2>/dev/null)
if [ -n "$IP" ]; then
    echo "  公网IP: $IP"
fi
echo "  内网IP: $(ip addr show | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}' | cut -d/ -f1)"

echo ""
echo "访问地址: http://$(curl -s ifconfig.me 2>/dev/null || echo '你的服务器IP')"
echo ""

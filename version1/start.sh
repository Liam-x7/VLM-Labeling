#!/bin/bash
# 标注系统启动脚本
# 用法:
#   ./start.sh          开发模式（直连，无 Nginx）
#   ./start.sh --prod   生产模式（Nginx 反向代理）

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MODE="dev"
if [ "$1" = "--prod" ]; then
    MODE="prod"
fi

echo "======================================"
echo "  标注系统启动 ($MODE 模式)"
echo "======================================"
echo ""

# 停止旧服务
echo "停止现有服务..."
pkill -f "backend.main" 2>/dev/null
pkill -f "http.server" 2>/dev/null
if [ "$MODE" = "prod" ]; then
    sudo systemctl stop nginx 2>/dev/null
fi
sleep 1

if [ "$MODE" = "prod" ]; then
    # ---- 生产模式: 绑定 127.0.0.1, Nginx 反向代理 ----

    # 检查/安装 Nginx
    if ! command -v nginx &> /dev/null; then
        echo -e "${YELLOW}Nginx 未安装，正在安装...${NC}"
        sudo apt update && sudo apt install nginx -y
        if [ $? -ne 0 ]; then
            echo -e "${RED}错误: Nginx 安装失败${NC}"
            exit 1
        fi
        echo -e "${GREEN}Nginx 安装完成${NC}"
    fi

    # 部署 Nginx 配置
    if [ -f /etc/nginx/sites-enabled/default ]; then
        sudo cp /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/default.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null
        sudo rm /etc/nginx/sites-enabled/default
    fi
    sudo cp nginx.conf /etc/nginx/sites-enabled/label-system.conf
    sudo nginx -t || { echo -e "${RED}错误: Nginx 配置测试失败${NC}"; exit 1; }

    # 启动后端和前端（绑定 127.0.0.1）
    echo "启动后端 (127.0.0.1:8000)..."
    nohup python3 -m backend.main --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
    echo -e "${GREEN}后端 PID: $!${NC}"

    echo "启动前端 (127.0.0.1:5173)..."
    nohup python3 -m http.server 5173 --bind 127.0.0.1 --directory frontend > frontend.log 2>&1 &
    echo -e "${GREEN}前端 PID: $!${NC}"

    sleep 2

    # 启动 Nginx
    echo "启动 Nginx..."
    sudo systemctl start nginx
    sudo systemctl enable nginx 2>/dev/null

    # 验证
    echo ""
    HEALTH=$(curl -s http://127.0.0.1/api/health 2>/dev/null)
    [ "$HEALTH" = '{"status": "ok"}' ] && echo -e "${GREEN}✓ 后端 API 正常${NC}" || echo -e "${RED}✗ 后端 API 异常${NC}"
    FRONTEND=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/ 2>/dev/null)
    [ "$FRONTEND" = "200" ] && echo -e "${GREEN}✓ 前端页面正常${NC}" || echo -e "${RED}✗ 前端页面异常${NC}"

    echo ""
    echo "访问地址: http://$(curl -s ifconfig.me 2>/dev/null || echo '你的服务器IP')"

else
    # ---- 开发模式: 绑定 0.0.0.0, 无 Nginx ----

    echo "启动后端 (0.0.0.0:8000)..."
    python3 -m backend.main --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    echo -e "${GREEN}后端 PID: $BACKEND_PID${NC}"

    echo "启动前端 (0.0.0.0:5173)..."
    python3 -m http.server 5173 --bind 0.0.0.0 --directory frontend &
    FRONTEND_PID=$!
    echo -e "${GREEN}前端 PID: $FRONTEND_PID${NC}"

    echo ""
    echo "访问: http://127.0.0.1:5173"
    echo "按 Ctrl+C 停止所有服务"

    cleanup() {
        echo ""
        echo "停止服务..."
        kill $BACKEND_PID 2>/dev/null
        kill $FRONTEND_PID 2>/dev/null
        echo "已停止"
        exit 0
    }
    trap cleanup INT TERM
    wait
fi

echo ""
echo "停止服务: ./stop_all.sh"
echo "查看状态: ./status.sh"
echo ""

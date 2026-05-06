#!/bin/bash
# Hybrid-Agent 启动脚本
# 同时启动后端 API (FastAPI) 和前端 Web (Vue 3 + Vite)

set -e

# 设置 PYTHONPATH
export PYTHONPATH="$(pwd)/src"

# 端口配置(可通过环境变量覆盖)
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

echo "=========================================="
echo "  Hybrid-Agent 启动中..."
echo "=========================================="

# 清理可能占用的端口
lsof -ti :"$BACKEND_PORT" -ti :"$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true

# 启动后端 API
echo "[1/2] 启动后端 API (端口 $BACKEND_PORT)..."
uv run uvicorn hybrid_agent.api.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

# 等待后端启动
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -s "http://localhost:$BACKEND_PORT/api/v1/health" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# 检查后端是否启动成功
if curl -s "http://localhost:$BACKEND_PORT/api/v1/health" > /dev/null 2>&1; then
    echo "✅ 后端 API 启动成功"
else
    echo "❌ 后端 API 启动失败"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# 检查前端依赖
if [ ! -d "frontend/node_modules" ]; then
    echo "[前端] 未检测到 node_modules,执行 npm install..."
    (cd frontend && npm install)
fi

echo ""
echo "=========================================="
echo "  服务已启动"
echo "=========================================="
echo "  后端 API:  http://localhost:$BACKEND_PORT"
echo "  API 文档:  http://localhost:$BACKEND_PORT/docs"
echo "  前端 Web:  http://localhost:$FRONTEND_PORT"
echo "=========================================="
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 捕获退出信号,清理进程
cleanup() {
    echo ""
    echo "正在停止服务..."
    kill $BACKEND_PID 2>/dev/null || true
    lsof -ti :"$BACKEND_PORT" -ti :"$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
    echo "服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 启动前端 (前台运行)
# Vite dev server 会代理 /api 到 VITE_API_PROXY_TARGET (默认 127.0.0.1:8000)
echo "[2/2] 启动前端 Vue 3 (端口 $FRONTEND_PORT)..."
cd frontend
VITE_API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT" \
    npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"

# 前端关闭时清理后端
cleanup

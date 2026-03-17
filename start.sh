#!/bin/bash
# Hybrid-Agent 启动脚本
# 同时启动后端 API 和前端 Web 界面

set -e

# 设置 PYTHONPATH
export PYTHONPATH="$(pwd)/src"

echo "=========================================="
echo "  Hybrid-Agent 启动中..."
echo "=========================================="

# 清理可能占用的端口
lsof -ti :8000 -ti :8501 | xargs kill -9 2>/dev/null || true

# 启动后端 API
echo "[1/2] 启动后端 API (端口 8000)..."
uv run uvicorn hybrid_agent.api.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 检查后端是否启动成功
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 后端 API 启动成功"
else
    echo "❌ 后端 API 启动失败"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "=========================================="
echo "  服务已启动"
echo "=========================================="
echo "  后端 API:  http://localhost:8000"
echo "  API 文档:  http://localhost:8000/docs"
echo "  前端 Web:  http://localhost:8501"
echo "=========================================="
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 捕获退出信号，清理进程
cleanup() {
    echo ""
    echo "正在停止服务..."
    kill $BACKEND_PID 2>/dev/null || true
    lsof -ti :8000 -ti :8501 | xargs kill -9 2>/dev/null || true
    echo "服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 启动前端 (前台运行)
echo "[2/2] 启动前端 Web (端口 8501)..."
uv run streamlit run src/hybrid_agent/web/app.py --server.port 8501

# 前端关闭时清理后端
cleanup

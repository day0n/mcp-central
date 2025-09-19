#!/bin/bash

# ACE Music Gen Web 快速启动脚本

echo "🎵 启动 ACE Music Gen Web 界面"

# 检查环境
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行 ./setup.sh"
    exit 1
fi

if [ -z "$ACE_MUSIC_GEN_API_KEY" ]; then
    echo "⚠️  警告: 未设置 ACE_MUSIC_GEN_API_KEY 环境变量"
    echo "   使用测试密钥，请确保已配置阿里云 DashScope API"
    export ACE_MUSIC_GEN_API_KEY="test_key"
fi

# 检查依赖
echo "📦 检查依赖..."
source .venv/bin/activate

# 安装Python依赖（如果需要）
if ! python -c "import fastapi" 2>/dev/null; then
    echo "🔄 安装Python依赖..."
    uv pip install -e .
fi

# 检查Node.js依赖
if [ ! -d "web/frontend/node_modules" ]; then
    echo "🔄 安装前端依赖..."
    cd web/frontend && npm install && cd ../..
fi

# 启动服务
echo "🚀 启动后端API服务器 (端口 8001)..."
python -m web.backend.api_server --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!

echo "⏳ 等待后端启动..."
sleep 3

echo "🚀 启动前端开发服务器 (端口 3000)..."
cd web/frontend && npm run dev &
FRONTEND_PID=$!

cd ../..

echo ""
echo "✅ 服务已启动！"
echo "🌐 前端界面: http://localhost:3000"
echo "📚 API文档: http://localhost:8001/docs"
echo "🔍 API健康检查: http://localhost:8001/health"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap 'echo "🛑 停止服务..."; kill $BACKEND_PID $FRONTEND_PID; exit' INT

wait
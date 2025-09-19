"""ACE Music Gen Web API 服务器

FastAPI 桥接层，包装 InteractiveMusicAgent 为 RESTful API
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# 添加项目根目录到Python路径
project_root = os.path.join(os.path.dirname(__file__), "../../")
sys.path.insert(0, project_root)

from .routes import session_router, chat_router, media_router
from .state_tracker import state_tracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时的初始化
    print("🚀 ACE Music Gen API 服务器启动")

    # 检查环境变量
    api_key = os.getenv("ACE_MUSIC_GEN_API_KEY")
    if not api_key:
        print("⚠️  警告: 未设置 ACE_MUSIC_GEN_API_KEY 环境变量")

    yield

    # 关闭时的清理
    print("🛑 ACE Music Gen API 服务器关闭")


# 创建FastAPI应用
app = FastAPI(
    title="ACE Music Gen API",
    description="ACE 音乐生成器 Web API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://192.168.1.2:3000"],  # 前端地址
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"服务器内部错误: {str(exc)}"
            },
            "request_id": "generated-request-id"
        }
    )


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "ace-music-gen-api",
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z"
    }


# API路由
API_V1_PREFIX = "/api/v1"

# 注册路由
app.include_router(session_router, prefix=API_V1_PREFIX)
app.include_router(chat_router, prefix=API_V1_PREFIX)
app.include_router(media_router, prefix=API_V1_PREFIX)


# 根路径
@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "ACE Music Gen API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


def main():
    """启动服务器"""
    import argparse

    parser = argparse.ArgumentParser(description="ACE Music Gen API Server")
    parser.add_argument("--host", default="127.0.0.1", help="服务器地址")
    parser.add_argument("--port", type=int, default=8001, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="开发模式自动重载")
    parser.add_argument("--log-level", default="info", help="日志级别")

    args = parser.parse_args()

    print(f"🎵 启动 ACE Music Gen API 服务器")
    print(f"📍 地址: http://{args.host}:{args.port}")
    print(f"📚 API文档: http://{args.host}:{args.port}/docs")
    print(f"🔍 健康检查: http://{args.host}:{args.port}/health")

    uvicorn.run(
        "web.backend.api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()
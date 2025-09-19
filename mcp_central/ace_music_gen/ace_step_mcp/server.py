"""ACE-Step MCP 服务器

基于FastAPI的音乐生成MCP服务，提供RESTful API接口调用ACE-Step pipeline
"""

import os
import time
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# 尝试导入ACE-Step相关模块
try:
    import sys
    # 添加父目录到路径，以便导入ace_music_gen模块
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from src.ace_music_gen.generator import SimpleACEMusicGen
    from src.ace_music_gen.evaluator import AudioEvaluator
    ACE_AVAILABLE = True
except ImportError as e:
    print(f"警告: 无法导入ACE-Step模块: {e}")
    print("MCP服务将以模拟模式运行")
    ACE_AVAILABLE = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="ACE-Step MCP服务",
    description="基于ACE-Step的音乐生成MCP服务",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局状态
ace_generator = None
audio_evaluator = None
request_stats = {
    "total_requests": 0,
    "successful_requests": 0,
    "cache_hits": 0,
    "server_start_time": datetime.now()
}


# 数据模型定义
class GenerationConfig(BaseModel):
    """音乐生成配置"""
    prompt: str = Field(..., description="英文技术描述")
    lyrics: str = Field(..., description="歌词内容")
    guidance_schedule: List[Dict[str, float]] = Field(
        default=[
            {"position": 0.0, "scale": 10.0},
            {"position": 0.4, "scale": 16.0},
            {"position": 0.8, "scale": 12.0},
            {"position": 1.0, "scale": 8.0}
        ],
        description="指导调度"
    )
    lora_config: Dict[str, Any] = Field(default_factory=dict, description="LoRA配置")
    audio_duration: float = Field(default=30.0, description="音频时长（秒）")
    candidate_count: int = Field(default=3, description="候选数量")
    cache_settings: Dict[str, bool] = Field(
        default_factory=lambda: {
            "enable_cache": True,
            "force_refresh": False
        },
        description="缓存设置"
    )


class GenerateMusicRequest(BaseModel):
    """音乐生成请求"""
    prompt: str = Field(..., description="英文技术描述")
    lyrics: str = Field(..., description="歌词内容")
    generation_config: GenerationConfig = Field(..., description="生成配置")


class MCPResponse(BaseModel):
    """MCP统一响应格式"""
    success: bool = Field(..., description="是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")
    request_id: str = Field(..., description="请求ID")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# 启动时初始化
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    global ace_generator, audio_evaluator

    logger.info("正在启动ACE-Step MCP服务...")

    if ACE_AVAILABLE:
        try:
            logger.info("初始化ACE音乐生成器...")
            ace_generator = SimpleACEMusicGen()

            logger.info("初始化音频评估器...")
            audio_evaluator = AudioEvaluator()

            logger.info("✅ ACE-Step组件初始化成功")
        except Exception as e:
            logger.error(f"❌ ACE-Step组件初始化失败: {e}")
            ace_generator = None
            audio_evaluator = None
    else:
        logger.warning("⚠️  以模拟模式启动（ACE-Step不可用）")

    request_stats["server_start_time"] = datetime.now()
    logger.info(f"🚀 ACE-Step MCP服务已启动，时间: {request_stats['server_start_time']}")


# API端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    uptime = datetime.now() - request_stats["server_start_time"]

    return {
        "status": "healthy",
        "service": "ACE-Step MCP服务",
        "version": "1.0.0",
        "ace_available": ACE_AVAILABLE,
        "uptime_seconds": uptime.total_seconds(),
        "stats": request_stats
    }


@app.post("/generate_music", response_model=MCPResponse)
async def generate_music(request: GenerateMusicRequest):
    """生成音乐端点"""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # 更新统计
    request_stats["total_requests"] += 1

    logger.info(f"[{request_id}] 收到音乐生成请求")
    logger.info(f"[{request_id}] Prompt: {request.prompt[:100]}...")
    logger.info(f"[{request_id}] 歌词长度: {len(request.lyrics)}字符")
    logger.info(f"[{request_id}] 时长: {request.generation_config.audio_duration}秒")

    try:
        if not ACE_AVAILABLE or ace_generator is None:
            # 模拟模式：返回模拟结果
            logger.warning(f"[{request_id}] 运行在模拟模式")

            # 模拟生成时间
            await asyncio.sleep(2)

            mock_result = {
                "audio_paths": [
                    f"/tmp/mock_audio_{request_id}_1.wav",
                    f"/tmp/mock_audio_{request_id}_2.wav",
                    f"/tmp/mock_audio_{request_id}_3.wav"
                ],
                "metadata": {
                    "generation_time": 2.0,
                    "model_version": "mock-1.0",
                    "prompt_used": request.prompt,
                    "lyrics_length": len(request.lyrics),
                    "cache_hit": False,
                    "evaluation_scores": {
                        "overall_score": 7.5,
                        "audio_quality": 8.0,
                        "lyric_matching": 7.0
                    }
                }
            }

            request_stats["successful_requests"] += 1
            logger.info(f"[{request_id}] ✅ 模拟生成完成")

            return MCPResponse(
                success=True,
                data=mock_result,
                request_id=request_id
            )

        # 真实生成模式
        logger.info(f"[{request_id}] 开始音乐生成...")

        # 设置guidance schedule
        ace_generator.set_guidance_schedule(request.generation_config.guidance_schedule)

        # 生成音乐 - 直接传递确认好的prompt和lyrics作为music_params
        music_params = {
            "prompt": request.prompt,
            "lyrics": request.lyrics
        }

        generation_result = ace_generator.generate_and_create_music(
            user_idea=f"用户确认的音乐: {request.prompt}",
            music_params=music_params,  # 🔥 传递确认好的参数，避免重新LLM生成
            guidance_schedule=request.generation_config.guidance_schedule,
            candidate_count=request.generation_config.candidate_count,
            audio_duration=request.generation_config.audio_duration,
            # 🔥 添加缓存配置
            enable_text_cache=request.generation_config.cache_settings.get("enable_cache", True),
            enable_lyric_cache=request.generation_config.cache_settings.get("enable_cache", True)
        )

        generation_time = time.time() - start_time

        # 调试：打印返回结构
        logger.info(f"[{request_id}] 调试：generation_result类型: {type(generation_result)}")
        logger.info(f"[{request_id}] 调试：generation_result内容: {str(generation_result)[:500]}...")

        if generation_result:
            audio_paths = []

            # 处理新的返回结构
            if "ace_step_result" in generation_result:
                logger.info(f"[{request_id}] 调试：找到ace_step_result")
                ace_result = generation_result["ace_step_result"]
                if isinstance(ace_result, dict) and "metadata" in ace_result:
                    metadata = ace_result["metadata"]
                    logger.info(f"[{request_id}] 调试：metadata内容: {str(metadata)[:300]}...")
                    # 尝试获取选中的音频路径
                    selected_audio = metadata.get("selected_audio_path")
                    if selected_audio:
                        audio_paths = [selected_audio]
                        logger.info(f"[{request_id}] 调试：找到selected_audio_path: {selected_audio}")

                    # 如果没有选中的，尝试获取所有候选音频
                    if not audio_paths:
                        candidate_scores = metadata.get("candidate_scores", [])
                        logger.info(f"[{request_id}] 调试：candidate_scores数量: {len(candidate_scores)}")
                        for i, candidate in enumerate(candidate_scores):
                            logger.info(f"[{request_id}] 调试：candidate {i}: {str(candidate)[:200]}...")
                            if "audio_path" in candidate and candidate["audio_path"]:
                                audio_paths.append(candidate["audio_path"])

            # 兼容旧的返回格式
            elif generation_result.get("audio_path"):
                logger.info(f"[{request_id}] 调试：找到旧格式audio_path")
                if isinstance(generation_result["audio_path"], list):
                    audio_paths = generation_result["audio_path"]
                else:
                    audio_paths = [generation_result["audio_path"]]

            logger.info(f"[{request_id}] 调试：最终audio_paths: {audio_paths}")

            if audio_paths:
                # 评估生成的音频
                evaluation_scores = {}
                if audio_evaluator and audio_paths:
                    try:
                        eval_result = audio_evaluator.evaluate_audio(audio_paths[0])
                        evaluation_scores = eval_result
                        logger.info(f"[{request_id}] 音频评估完成: {eval_result.get('overall_score', 'N/A')}")
                    except Exception as e:
                        logger.warning(f"[{request_id}] 音频评估失败: {e}")

                result_data = {
                    "audio_paths": audio_paths,
                    "metadata": {
                        "generation_time": generation_time,
                        "model_version": "ace-step-1.0",
                        "prompt_used": request.prompt,
                        "lyrics_used": request.lyrics,
                        "guidance_schedule": request.generation_config.guidance_schedule,
                        "audio_duration": request.generation_config.audio_duration,
                        "candidate_count": len(audio_paths),
                        "cache_hit": generation_result.get("cache_hit", False),
                        "evaluation_scores": evaluation_scores
                    }
                }

                if result_data["metadata"]["cache_hit"]:
                    request_stats["cache_hits"] += 1

                request_stats["successful_requests"] += 1
                logger.info(f"[{request_id}] ✅ 生成成功，耗时: {generation_time:.1f}秒")

                return MCPResponse(
                    success=True,
                    data=result_data,
                    request_id=request_id
                )
            else:
                raise Exception("生成结果为空或无效：未找到音频文件路径")
        else:
            raise Exception("生成结果为空或无效")

    except Exception as e:
        error_msg = f"生成失败: {str(e)}"
        logger.exception(f"[{request_id}] ❌ {error_msg}")

        return MCPResponse(
            success=False,
            error=error_msg,
            request_id=request_id
        )


# 启动脚本入口
def main():
    """MCP服务器主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="ACE-Step MCP服务器")
    parser.add_argument("--host", default="127.0.0.1", help="服务器主机地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="启用热重载（开发模式）")
    parser.add_argument("--log-level", default="info", help="日志级别")

    args = parser.parse_args()

    logger.info(f"启动MCP服务器: {args.host}:{args.port}")

    uvicorn.run(
        "ace_step_mcp.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()

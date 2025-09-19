"""API 请求模型"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class SessionStartRequest(BaseModel):
    """会话创建请求"""
    config: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "audio_duration": 30.0,
            "language": "中文",
            "enable_pinyin": True
        },
        description="会话配置参数"
    )


class ChatMessageRequest(BaseModel):
    """聊天消息请求"""
    content: str = Field(..., min_length=1, description="消息内容")
    message_type: str = Field(default="user_input", description="消息类型")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="额外元数据")


class LyricsReviewRequest(BaseModel):
    """歌词审核请求"""
    version: int = Field(..., description="歌词版本号")
    approved: bool = Field(..., description="是否批准")
    feedback: Optional[str] = Field(default=None, description="用户反馈")


class GenerationConfigRequest(BaseModel):
    """生成配置请求"""
    audio_duration: Optional[float] = Field(default=30.0, description="音频时长")
    candidate_count: Optional[int] = Field(default=3, description="候选数量")
    guidance_schedule: Optional[list] = Field(default=None, description="引导调度")
    lora_config: Optional[Dict[str, Any]] = Field(default=None, description="LoRA配置")
    cache_settings: Optional[Dict[str, bool]] = Field(default=None, description="缓存设置")
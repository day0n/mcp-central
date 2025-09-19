"""API 响应模型"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(..., description="操作是否成功")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="请求ID")


class ErrorResponse(BaseResponse):
    """错误响应"""
    success: bool = Field(default=False)
    error: Dict[str, Any] = Field(..., description="错误信息")

    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "输入参数验证失败",
                    "details": {"field": "audio_duration", "reason": "必须大于0"}
                },
                "request_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class SessionStartResponse(BaseResponse):
    """会话创建响应"""
    data: Dict[str, Any] = Field(..., description="会话数据")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "session_id": "123e4567-e89b-12d3-a456-426614174000",
                    "created_at": "2024-01-01T00:00:00Z",
                    "status": "initializing"
                },
                "request_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class ChatMessageResponse(BaseResponse):
    """聊天消息响应"""
    data: Dict[str, Any] = Field(..., description="消息数据")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "message_id": "123e4567-e89b-12d3-a456-426614174000",
                    "agent_response": "我了解您想要一首伤感的说唱歌曲...",
                    "stage": "collecting_requirements",
                    "next_action": "继续收集具体需求"
                },
                "request_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class SessionStateResponse(BaseResponse):
    """会话状态响应"""
    data: Dict[str, Any] = Field(..., description="会话状态数据")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "session_id": "123e4567-e89b-12d3-a456-426614174000",
                    "current_stage": "generating_lyrics",
                    "stage_description": "正在生成歌词候选版本...",
                    "progress_percentage": 65.5,
                    "conversation_history": [],
                    "user_requirement": {},
                    "lyrics_versions": []
                },
                "request_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class SessionResultResponse(BaseResponse):
    """会话结果响应"""
    data: Dict[str, Any] = Field(..., description="会话结果数据")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "audio_files": [
                        {
                            "url": "/api/v1/media/session_id/audio_1.wav",
                            "filename": "audio_1.wav",
                            "duration": 30.2,
                            "score": 8.5
                        }
                    ],
                    "final_lyrics": "最终确认的歌词内容...",
                    "metadata": {
                        "generation_time": 125.3,
                        "quality_scores": {"overall": 8.5}
                    }
                },
                "request_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class SessionListResponse(BaseResponse):
    """会话列表响应"""
    data: Dict[str, Any] = Field(..., description="会话列表数据")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "sessions": [
                        {
                            "session_id": "123e4567-e89b-12d3-a456-426614174000",
                            "created_at": "2024-01-01T00:00:00Z",
                            "status": "completed",
                            "summary": {
                                "style": "伤感说唱",
                                "duration": 30.0,
                                "audio_count": 3
                            }
                        }
                    ],
                    "total": 50,
                    "has_more": True
                },
                "request_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }
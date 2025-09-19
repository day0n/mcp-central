"""会话管理路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import asyncio

from ..models.requests import SessionStartRequest
from ..models.responses import (
    SessionStartResponse, SessionStateResponse, SessionResultResponse,
    SessionListResponse, ErrorResponse
)
from ..state_tracker import state_tracker

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest):
    """创建新的音乐生成会话"""
    try:
        session_id = state_tracker.create_session(request.config)

        return SessionStartResponse(
            success=True,
            data={
                "session_id": session_id,
                "created_at": "2024-01-01T00:00:00Z",  # TODO: 使用实际时间
                "status": "initializing"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"创建会话失败: {str(e)}"
            }
        )


@router.get("/{session_id}/state", response_model=SessionStateResponse)
async def get_session_state(session_id: str):
    """获取会话当前状态"""
    session_data = state_tracker.get_session_data(session_id)

    if not session_data:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"会话 {session_id} 不存在"
            }
        )

    return SessionStateResponse(
        success=True,
        data=session_data
    )


@router.get("/{session_id}/result", response_model=SessionResultResponse)
async def get_session_result(session_id: str):
    """获取会话最终结果"""
    session = state_tracker.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"会话 {session_id} 不存在"
            }
        )

    if session.current_stage != "completed":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SESSION_NOT_COMPLETED",
                "message": "会话尚未完成"
            }
        )

    result_data = state_tracker.get_session_result(session_id)

    if not result_data:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "RESULT_NOT_FOUND",
                "message": "会话结果不存在"
            }
        )

    return SessionResultResponse(
        success=True,
        data=result_data
    )


@router.get("/{session_id}/stream")
async def stream_session_events(session_id: str):
    """SSE 流式推送会话事件"""
    session = state_tracker.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"会话 {session_id} 不存在"
            }
        )

    from fastapi.responses import StreamingResponse
    import json

    async def event_stream():
        queue = state_tracker.register_sse_queue(session_id)

        # 发送初始连接事件
        yield f"event: connected\ndata: {json.dumps({'session_id': session_id})}\n\n"

        try:
            while True:
                # 等待新事件，带超时
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)

                    event_type = event.get("event", "message")
                    event_data = json.dumps(event.get("data", {}), ensure_ascii=False)

                    yield f"event: {event_type}\ndata: {event_data}\n\n"

                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': '2024-01-01T00:00:00Z'})}\n\n"

        except asyncio.CancelledError:
            # 客户端断开连接
            yield f"event: disconnected\ndata: {json.dumps({'session_id': session_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """获取会话列表"""
    try:
        sessions_data = state_tracker.list_sessions(limit, offset)

        return SessionListResponse(
            success=True,
            data=sessions_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"获取会话列表失败: {str(e)}"
            }
        )
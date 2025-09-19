"""媒体文件路由"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional
import os
import mimetypes

from ..state_tracker import state_tracker

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{session_id}/{filename}")
async def get_media_file(
    session_id: str,
    filename: str,
    token: Optional[str] = Query(None, description="访问令牌")
):
    """获取媒体文件"""
    # 验证会话存在
    session = state_tracker.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"会话 {session_id} 不存在"
            }
        )

    # 构造文件路径
    # TODO: 从配置获取outputs目录
    outputs_dir = os.path.join(os.getcwd(), "outputs")
    session_dir = os.path.join(outputs_dir, f"session_{session_id}")
    file_path = os.path.join(session_dir, filename)

    # 安全检查：确保文件在允许的目录内
    if not os.path.abspath(file_path).startswith(os.path.abspath(session_dir)):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PATH",
                "message": "无效的文件路径"
            }
        )

    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "FILE_NOT_FOUND",
                "message": f"文件 {filename} 不存在"
            }
        )

    # 检查文件类型
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith(('audio/', 'image/')):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_FILE_TYPE",
                "message": "不支持的文件类型"
            }
        )

    # TODO: 实现token验证
    # if token:
    #     if not verify_media_token(session_id, filename, token):
    #         raise HTTPException(status_code=403, detail="无效的访问令牌")

    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=filename,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.get("/{session_id}/files")
async def list_session_files(session_id: str):
    """列出会话的所有文件"""
    session = state_tracker.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"会话 {session_id} 不存在"
            }
        )

    # 构造会话目录路径
    outputs_dir = os.path.join(os.getcwd(), "outputs")
    session_dir = os.path.join(outputs_dir, f"session_{session_id}")

    files = []
    if os.path.exists(session_dir):
        for filename in os.listdir(session_dir):
            file_path = os.path.join(session_dir, filename)

            if os.path.isfile(file_path):
                # 获取文件信息
                stat = os.stat(file_path)
                mime_type, _ = mimetypes.guess_type(file_path)

                files.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "created_at": "2024-01-01T00:00:00Z",  # TODO: 使用实际创建时间
                    "mime_type": mime_type,
                    "download_url": f"/api/v1/media/{session_id}/{filename}"
                })

    return {
        "success": True,
        "data": {
            "audio_files": [f for f in files if f["mime_type"] and f["mime_type"].startswith("audio/")],
            "other_files": [f for f in files if not f["mime_type"] or not f["mime_type"].startswith("audio/")]
        }
    }
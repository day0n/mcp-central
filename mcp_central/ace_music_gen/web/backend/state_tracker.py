"""Agent 状态跟踪器

管理多个会话的状态，提供线程安全的读写接口
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import asdict
from threading import Lock
import uuid

from src.ace_music_gen.session_state import MusicSessionState, ConversationTurn


class AgentStateTracker:
    """Agent 状态跟踪器"""

    def __init__(self):
        self._sessions: Dict[str, MusicSessionState] = {}
        self._session_lock = Lock()
        self._event_callbacks: Dict[str, List[Callable]] = {}
        self._sse_queues: Dict[str, asyncio.Queue] = {}

    def create_session(self, config: Optional[Dict[str, Any]] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())

        with self._session_lock:
            session = MusicSessionState(session_id=session_id)
            session.add_debug_log("会话已创建")
            self._sessions[session_id] = session
            self._sse_queues[session_id] = asyncio.Queue()

        self._emit_event(session_id, "session_created", {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "status": "initializing"
        })

        return session_id

    def get_session(self, session_id: str) -> Optional[MusicSessionState]:
        """获取会话状态"""
        with self._session_lock:
            return self._sessions.get(session_id)

    def update_stage(self, session_id: str, stage: str, description: str = "",
                    progress: float = 0.0, metadata: Optional[Dict[str, Any]] = None):
        """更新会话阶段"""
        with self._session_lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            session.update_stage(stage)
            session.add_debug_log(f"阶段更新: {stage}")

            # 计算进度百分比
            stage_progress_map = {
                "initializing": 0,
                "collecting_requirements": 20,
                "generating_lyrics": 40,
                "reviewing_lyrics": 60,
                "preparing_generation": 70,
                "generating_music": 85,
                "evaluating_results": 95,
                "completed": 100,
                "failed": 0
            }
            calculated_progress = stage_progress_map.get(stage, progress)

        self._emit_event(session_id, "state_update", {
            "stage": stage,
            "description": description,
            "progress": calculated_progress,
            "timestamp": datetime.now().isoformat()
        })

        return True

    def add_conversation(self, session_id: str, role: str, content: str,
                        metadata: Optional[Dict[str, Any]] = None):
        """添加对话记录"""
        with self._session_lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            turn = ConversationTurn(
                role=role,
                content=content,
                meta=metadata or {}
            )
            session.conversation_history.append(turn)

        self._emit_event(session_id, "chat_message", {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        })

        return True

    def add_debug_log(self, session_id: str, message: str, level: str = "INFO",
                     metadata: Optional[Dict[str, Any]] = None):
        """添加调试日志"""
        with self._session_lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            session.add_debug_log(message)

        self._emit_event(session_id, "debug_log", {
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        })

        return True

    def set_error(self, session_id: str, error_message: str,
                 error_code: str = "AGENT_ERROR"):
        """设置会话错误"""
        with self._session_lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            session.update_stage("failed")
            session.add_debug_log(f"错误: {error_message}")

        self._emit_event(session_id, "error", {
            "error": error_message,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat()
        })

        return True

    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取完整会话数据（用于API响应）"""
        session = self.get_session(session_id)
        if not session:
            return None

        # 转换为可序列化的数据
        conversation_history = []
        for turn in session.conversation_history:
            conversation_history.append({
                "role": turn.role,
                "content": turn.content,
                "timestamp": turn.timestamp.isoformat(),
                "metadata": turn.meta or {}
            })

        lyrics_versions = []
        for lyrics in session.lyrics_versions:
            lyrics_versions.append({
                "version": lyrics.version,
                "content": lyrics.content,
                "approved": lyrics.approved,
                "user_feedback": lyrics.user_feedback,
                "created_at": lyrics.created_at.isoformat(),
                "pinyin_annotated": lyrics.pinyin_annotated
            })

        user_requirement = {}
        if session.user_requirement:
            user_requirement = asdict(session.user_requirement)

        # 处理ReAct元信息
        actions = []
        for action in getattr(session, 'actions', []):
            actions.append({
                "action_type": getattr(action, 'action_type', ''),
                "action_data": getattr(action, 'action_data', {}),
                "timestamp": getattr(action, 'timestamp', datetime.now()).isoformat(),
                "result": getattr(action, 'result', None),
                "error": getattr(action, 'error', None),
                "duration_seconds": getattr(action, 'duration_seconds', None)
            })

        thoughts = getattr(session, 'thoughts', [])

        final_assets = []
        for asset in getattr(session, 'final_assets', []):
            final_assets.append({
                "asset_type": getattr(asset, 'asset_type', ''),
                "asset_id": getattr(asset, 'asset_id', ''),
                "file_path": getattr(asset, 'file_path', None),
                "content": getattr(asset, 'content', None),
                "metadata": getattr(asset, 'metadata', {}),
                "created_at": getattr(asset, 'created_at', datetime.now()).isoformat(),
                "is_final": getattr(asset, 'is_final', False)
            })

        return {
            "session_id": session.session_id,
            "current_stage": session.current_stage,
            "stage_description": self._get_stage_description(session.current_stage),
            "progress_percentage": self._calculate_progress(session.current_stage),
            "conversation_history": conversation_history,
            "user_requirement": user_requirement,
            "lyrics_versions": lyrics_versions,
            "debug_logs": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": log,
                    "metadata": {}
                }
                for log in session.debug_logs[-10:]  # 只返回最近10条
            ],
            "react_metadata": {
                "actions": actions[-10:],  # 最近10个行动
                "thoughts": thoughts[-20:],  # 最近20个思考
                "final_assets": final_assets
            }
        }

    def get_session_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话最终结果"""
        session = self.get_session(session_id)
        if not session or not hasattr(session, 'generation_result') or not session.generation_result:
            return None

        result = session.generation_result
        audio_files = []

        # 安全获取音频路径列表
        audio_paths = getattr(result, 'audio_paths', [])
        if audio_paths and isinstance(audio_paths, list):
            for i, path in enumerate(audio_paths):
                if path:  # 确保路径不为空
                    # 构造相对URL路径
                    filename = path.split('/')[-1] if '/' in path else path
                    # 安全获取元数据
                    metadata = getattr(result, 'metadata', {})
                    evaluation_scores = getattr(result, 'evaluation_scores', {})

                    audio_files.append({
                        "url": f"/api/v1/media/{session_id}/{filename}",
                        "filename": filename,
                        "duration": metadata.get("duration", 30.0) if isinstance(metadata, dict) else 30.0,
                        "score": evaluation_scores.get("overall", 0.0) if isinstance(evaluation_scores, dict) else 0.0
                    })

        # 获取最终歌词
        final_lyrics = ""
        if hasattr(session, 'selected_lyrics') and session.selected_lyrics:
            final_lyrics = getattr(session.selected_lyrics, 'content', '')
        elif session.lyrics_versions:
            # 使用最后一个已批准的歌词版本
            for lyrics in reversed(session.lyrics_versions):
                if hasattr(lyrics, 'approved') and getattr(lyrics, 'approved', False):
                    final_lyrics = getattr(lyrics, 'content', '')
                    break
            # 如果没有已批准的，使用第一个
            if not final_lyrics and session.lyrics_versions:
                final_lyrics = getattr(session.lyrics_versions[0], 'content', '')

        # 安全获取结果元数据
        metadata = getattr(result, 'metadata', {})
        evaluation_scores = getattr(result, 'evaluation_scores', {})
        generation_time = getattr(result, 'generation_time', None)

        return {
            "audio_files": audio_files,
            "final_lyrics": final_lyrics,
            "metadata": {
                "generation_time": generation_time,
                "quality_scores": evaluation_scores if isinstance(evaluation_scores, dict) else {},
                **(metadata if isinstance(metadata, dict) else {})
            }
        }

    def list_sessions(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """列出会话"""
        with self._session_lock:
            sessions = list(self._sessions.values())

        # 按创建时间排序
        sessions.sort(key=lambda s: s.session_id, reverse=True)

        # 分页
        total = len(sessions)
        paginated_sessions = sessions[offset:offset + limit]

        session_summaries = []
        for session in paginated_sessions:
            summary = {
                "session_id": session.session_id,
                "created_at": datetime.now().isoformat(),  # 暂时使用当前时间
                "status": session.current_stage,
                "summary": {}
            }

            if session.user_requirement:
                # 安全获取用户需求信息
                style = getattr(session.user_requirement, 'style', '')
                duration = getattr(session.user_requirement, 'duration', 30)

                # 安全获取音频数量
                audio_count = 0
                if session.generation_result:
                    audio_paths = getattr(session.generation_result, 'audio_paths', [])
                    if audio_paths and isinstance(audio_paths, list):
                        audio_count = len(audio_paths)

                summary["summary"] = {
                    "style": style,
                    "duration": duration,
                    "audio_count": audio_count
                }

            session_summaries.append(summary)

        return {
            "sessions": session_summaries,
            "total": total,
            "has_more": offset + limit < total
        }

    def register_sse_queue(self, session_id: str) -> asyncio.Queue:
        """注册SSE队列"""
        if session_id not in self._sse_queues:
            self._sse_queues[session_id] = asyncio.Queue()
        return self._sse_queues[session_id]

    def _emit_event(self, session_id: str, event_type: str, data: Dict[str, Any]):
        """发送事件到SSE队列"""
        if session_id in self._sse_queues:
            event = {
                "event": event_type,
                "data": data
            }
            try:
                self._sse_queues[session_id].put_nowait(event)
            except asyncio.QueueFull:
                # 队列满了，丢弃最旧的事件
                try:
                    self._sse_queues[session_id].get_nowait()
                    self._sse_queues[session_id].put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

    def _get_stage_description(self, stage: str) -> str:
        """获取阶段描述"""
        descriptions = {
            "initializing": "初始化会话...",
            "collecting_requirements": "收集用户需求",
            "generating_lyrics": "生成歌词候选版本",
            "reviewing_lyrics": "等待用户审核歌词",
            "preparing_generation": "准备音乐生成参数",
            "generating_music": "调用MCP生成音乐",
            "evaluating_results": "评估音频质量",
            "completed": "音乐生成完成",
            "failed": "生成失败"
        }
        return descriptions.get(stage, stage)

    def _calculate_progress(self, stage: str) -> float:
        """计算进度百分比"""
        progress_map = {
            "initializing": 0,
            "collecting_requirements": 20,
            "generating_lyrics": 40,
            "reviewing_lyrics": 60,
            "preparing_generation": 70,
            "generating_music": 85,
            "evaluating_results": 95,
            "completed": 100,
            "failed": 0
        }
        return progress_map.get(stage, 0)


# 全局状态跟踪器实例
state_tracker = AgentStateTracker()
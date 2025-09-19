"""Agent回调钩子系统

提供Agent事件的回调钩子机制，支持事件驱动的架构
"""

from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class AgentEventType(Enum):
    """Agent事件类型"""
    # 阶段变更事件
    STAGE_CHANGED = "stage_changed"

    # 思考事件
    THOUGHT_STARTED = "thought_started"
    THOUGHT_COMPLETED = "thought_completed"

    # 行动事件
    ACTION_STARTED = "action_started"
    ACTION_COMPLETED = "action_completed"
    ACTION_FAILED = "action_failed"

    # 观察事件
    OBSERVATION_MADE = "observation_made"

    # 用户交互事件
    USER_INPUT_RECEIVED = "user_input_received"
    ASSISTANT_RESPONSE_SENT = "assistant_response_sent"

    # 数据变更事件
    REQUIREMENT_UPDATED = "requirement_updated"
    LYRICS_GENERATED = "lyrics_generated"
    LYRICS_APPROVED = "lyrics_approved"
    MUSIC_GENERATION_STARTED = "music_generation_started"
    MUSIC_GENERATION_COMPLETED = "music_generation_completed"

    # 资产管理事件
    ASSET_CREATED = "asset_created"
    ASSET_UPDATED = "asset_updated"
    ASSET_FINALIZED = "asset_finalized"

    # 错误事件
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"


@dataclass
class AgentEvent:
    """Agent事件数据结构"""
    event_type: AgentEventType
    session_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata
        }


class AgentEventBus:
    """Agent事件总线"""

    def __init__(self):
        self._sync_hooks: Dict[AgentEventType, List[Callable]] = {}
        self._async_hooks: Dict[AgentEventType, List[Callable]] = {}
        self._global_sync_hooks: List[Callable] = []
        self._global_async_hooks: List[Callable] = []
        self._event_history: List[AgentEvent] = []
        self._max_history_size = 1000

    def register_hook(self, event_type: AgentEventType, hook: Callable, is_async: bool = False):
        """注册事件钩子

        Args:
            event_type: 事件类型
            hook: 钩子函数，签名为 (event: AgentEvent) -> None
            is_async: 是否为异步钩子
        """
        if is_async:
            if event_type not in self._async_hooks:
                self._async_hooks[event_type] = []
            self._async_hooks[event_type].append(hook)
        else:
            if event_type not in self._sync_hooks:
                self._sync_hooks[event_type] = []
            self._sync_hooks[event_type].append(hook)

    def register_global_hook(self, hook: Callable, is_async: bool = False):
        """注册全局钩子，监听所有事件

        Args:
            hook: 钩子函数
            is_async: 是否为异步钩子
        """
        if is_async:
            self._global_async_hooks.append(hook)
        else:
            self._global_sync_hooks.append(hook)

    def unregister_hook(self, event_type: AgentEventType, hook: Callable, is_async: bool = False):
        """取消注册钩子"""
        try:
            if is_async:
                if event_type in self._async_hooks:
                    self._async_hooks[event_type].remove(hook)
            else:
                if event_type in self._sync_hooks:
                    self._sync_hooks[event_type].remove(hook)
        except ValueError:
            logger.warning(f"Hook not found for event type {event_type}")

    async def emit(self, event: AgentEvent):
        """发射事件"""
        # 记录事件历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history.pop(0)

        logger.debug(f"Emitting event: {event.event_type.value} for session {event.session_id}")

        # 执行同步钩子
        sync_hooks = self._sync_hooks.get(event.event_type, []) + self._global_sync_hooks
        for hook in sync_hooks:
            try:
                hook(event)
            except Exception as e:
                logger.error(f"Error in sync hook {hook.__name__}: {e}")

        # 执行异步钩子
        async_hooks = self._async_hooks.get(event.event_type, []) + self._global_async_hooks
        if async_hooks:
            await asyncio.gather(
                *[self._safe_async_hook(hook, event) for hook in async_hooks],
                return_exceptions=True
            )

    async def _safe_async_hook(self, hook: Callable, event: AgentEvent):
        """安全执行异步钩子"""
        try:
            await hook(event)
        except Exception as e:
            logger.error(f"Error in async hook {hook.__name__}: {e}")

    def get_event_history(self, session_id: Optional[str] = None,
                         event_type: Optional[AgentEventType] = None,
                         limit: int = 100) -> List[AgentEvent]:
        """获取事件历史

        Args:
            session_id: 会话ID过滤
            event_type: 事件类型过滤
            limit: 返回数量限制
        """
        events = self._event_history

        if session_id:
            events = [e for e in events if e.session_id == session_id]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def clear_history(self, session_id: Optional[str] = None):
        """清理事件历史"""
        if session_id:
            self._event_history = [e for e in self._event_history if e.session_id != session_id]
        else:
            self._event_history.clear()


class AgentHookManager:
    """Agent钩子管理器

    提供Agent钩子的高级管理功能
    """

    def __init__(self, event_bus: AgentEventBus):
        self.event_bus = event_bus
        self._hook_groups: Dict[str, List[Callable]] = {}

    def create_hook_group(self, group_name: str) -> 'HookGroup':
        """创建钩子组"""
        return HookGroup(group_name, self.event_bus, self)

    def register_hook_group(self, group_name: str, hooks: List[Callable]):
        """注册钩子组"""
        self._hook_groups[group_name] = hooks
        for hook in hooks:
            # 这里可以添加批量注册逻辑
            pass

    def unregister_hook_group(self, group_name: str):
        """取消注册钩子组"""
        if group_name in self._hook_groups:
            hooks = self._hook_groups[group_name]
            for hook in hooks:
                # 这里可以添加批量取消注册逻辑
                pass
            del self._hook_groups[group_name]

    async def emit_thought_event(self, session_id: str, thought: str, stage: str):
        """发射思考事件"""
        event = AgentEvent(
            event_type=AgentEventType.THOUGHT_COMPLETED,
            session_id=session_id,
            data={"thought": thought, "stage": stage}
        )
        await self.event_bus.emit(event)

    async def emit_action_event(self, session_id: str, action_type: str,
                               action_data: Dict[str, Any], result: str = None, error: str = None):
        """发射行动事件"""
        if error:
            event_type = AgentEventType.ACTION_FAILED
            data = {"action_type": action_type, "action_data": action_data, "error": error}
        else:
            event_type = AgentEventType.ACTION_COMPLETED
            data = {"action_type": action_type, "action_data": action_data, "result": result}

        event = AgentEvent(
            event_type=event_type,
            session_id=session_id,
            data=data
        )
        await self.event_bus.emit(event)

    async def emit_stage_change_event(self, session_id: str, old_stage: str, new_stage: str):
        """发射阶段变更事件"""
        event = AgentEvent(
            event_type=AgentEventType.STAGE_CHANGED,
            session_id=session_id,
            data={"old_stage": old_stage, "new_stage": new_stage}
        )
        await self.event_bus.emit(event)

    async def emit_asset_event(self, session_id: str, asset_type: str, asset_id: str,
                              file_path: str = None, content: str = None, is_final: bool = False):
        """发射资产事件"""
        event_type = AgentEventType.ASSET_FINALIZED if is_final else AgentEventType.ASSET_CREATED
        event = AgentEvent(
            event_type=event_type,
            session_id=session_id,
            data={
                "asset_type": asset_type,
                "asset_id": asset_id,
                "file_path": file_path,
                "content": content,
                "is_final": is_final
            }
        )
        await self.event_bus.emit(event)


class HookGroup:
    """钩子组"""

    def __init__(self, name: str, event_bus: AgentEventBus, manager: AgentHookManager):
        self.name = name
        self.event_bus = event_bus
        self.manager = manager
        self.hooks: List[Callable] = []

    def add_hook(self, event_type: AgentEventType, hook: Callable, is_async: bool = False):
        """添加钩子到组"""
        self.hooks.append(hook)
        self.event_bus.register_hook(event_type, hook, is_async)

    def remove_all_hooks(self):
        """移除组内所有钩子"""
        for hook in self.hooks:
            # 这里需要知道事件类型才能正确移除，实际实现可能需要调整
            pass
        self.hooks.clear()


# 全局事件总线实例
global_event_bus = AgentEventBus()
global_hook_manager = AgentHookManager(global_event_bus)
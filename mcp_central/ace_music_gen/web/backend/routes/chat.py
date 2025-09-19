"""聊天对话路由"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import asyncio
import os

from ..models.requests import ChatMessageRequest, LyricsReviewRequest
from ..models.responses import ChatMessageResponse, ErrorResponse
from ..state_tracker import state_tracker

# 引入现有的Agent类
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../"))

from src.ace_music_gen.interactive_agent import InteractiveMusicAgent
from src.ace_music_gen.llm_client import LLMClient
from src.ace_music_gen.mcp_client import ACEStepMCPClient
from src.ace_music_gen.agent_hooks import (
    global_event_bus,
    global_hook_manager,
    AgentEvent,
    AgentEventType
)

router = APIRouter(prefix="/session", tags=["chat"])

# 全局Agent实例缓存
_agent_instances = {}


# 设置事件钩子以连接Agent事件系统和state_tracker
def _setup_event_hooks():
    """设置事件钩子"""

    def on_stage_changed(event: AgentEvent):
        """阶段变更事件钩子"""
        session_id = event.session_id
        data = event.data
        new_stage = data.get("new_stage")
        if new_stage:
            state_tracker.update_stage(session_id, new_stage, f"Agent阶段变更为: {new_stage}")

    def on_thought_completed(event: AgentEvent):
        """思考完成事件钩子"""
        session_id = event.session_id
        data = event.data
        thought = data.get("thought")
        if thought:
            state_tracker.add_debug_log(session_id, f"💭 思考: {thought}")

    def on_action_completed(event: AgentEvent):
        """行动完成事件钩子"""
        session_id = event.session_id
        data = event.data
        action_type = data.get("action_type")
        result = data.get("result")
        if action_type and result:
            state_tracker.add_debug_log(session_id, f"✅ 行动完成: {action_type} -> {result}")

    def on_action_failed(event: AgentEvent):
        """行动失败事件钩子"""
        session_id = event.session_id
        data = event.data
        action_type = data.get("action_type")
        error = data.get("error")
        if action_type and error:
            state_tracker.add_debug_log(session_id, f"❌ 行动失败: {action_type} -> {error}")

    def on_asset_created(event: AgentEvent):
        """资产创建事件钩子"""
        session_id = event.session_id
        data = event.data
        asset_type = data.get("asset_type")
        asset_id = data.get("asset_id")
        state_tracker.add_debug_log(session_id, f"📄 资产创建: {asset_type} ({asset_id})")

    # 注册事件钩子
    global_event_bus.register_hook(AgentEventType.STAGE_CHANGED, on_stage_changed)
    global_event_bus.register_hook(AgentEventType.THOUGHT_COMPLETED, on_thought_completed)
    global_event_bus.register_hook(AgentEventType.ACTION_COMPLETED, on_action_completed)
    global_event_bus.register_hook(AgentEventType.ACTION_FAILED, on_action_failed)
    global_event_bus.register_hook(AgentEventType.ASSET_CREATED, on_asset_created)


# 初始化事件钩子
_setup_event_hooks()


def get_agent_instance(session_id: str) -> InteractiveMusicAgent:
    """获取或创建Agent实例"""
    if session_id not in _agent_instances:
        # 创建LLM和MCP客户端
        api_key = os.getenv("ACE_MUSIC_GEN_API_KEY")
        if not api_key:
            raise ValueError("缺少 ACE_MUSIC_GEN_API_KEY 环境变量")

        llm_client = LLMClient(api_key=api_key)
        mcp_client = ACEStepMCPClient()

        # 创建Agent实例
        agent = InteractiveMusicAgent(llm_client, mcp_client)

        # 包装Agent方法以集成状态跟踪
        agent = _wrap_agent_with_state_tracking(agent, session_id)

        _agent_instances[session_id] = agent

    return _agent_instances[session_id]


def _wrap_agent_with_state_tracking(agent: InteractiveMusicAgent, session_id: str):
    """包装Agent方法以集成状态跟踪"""
    original_update_stage = agent.session.update_stage
    original_add_debug_log = agent.session.add_debug_log

    def wrapped_update_stage(stage: str):
        result = original_update_stage(stage)
        state_tracker.update_stage(session_id, stage)
        # 同步完整状态
        _sync_agent_to_tracker(agent, session_id)
        return result

    def wrapped_add_debug_log(message: str):
        result = original_add_debug_log(message)
        state_tracker.add_debug_log(session_id, message)
        return result

    agent.session.update_stage = wrapped_update_stage
    agent.session.add_debug_log = wrapped_add_debug_log

    return agent


def _sync_agent_to_tracker(agent: InteractiveMusicAgent, session_id: str):
    """同步Agent状态到state_tracker"""
    tracker_session = state_tracker.get_session(session_id)
    if tracker_session:
        tracker_session.current_stage = agent.session.current_stage
        tracker_session.user_requirement = agent.session.user_requirement
        tracker_session.lyrics_versions = agent.session.lyrics_versions
        tracker_session.selected_lyrics = agent.session.selected_lyrics
        tracker_session.generation_result = agent.session.generation_result

        # 同步ReAct元数据
        if hasattr(agent.session, 'actions'):
            tracker_session.actions = agent.session.actions
        if hasattr(agent.session, 'thoughts'):
            tracker_session.thoughts = agent.session.thoughts
        if hasattr(agent.session, 'final_assets'):
            tracker_session.final_assets = agent.session.final_assets


async def process_message_async(session_id: str, content: str):
    """异步处理用户消息 - ReAct Agent模式"""
    try:
        # 获取Agent实例
        agent = get_agent_instance(session_id)

        # 发送用户消息到SSE
        state_tracker.add_conversation(session_id, "user", content)

        # 开始Agent思考和行动循环
        state_tracker.update_stage(session_id, "processing", "Agent正在分析您的需求...")
        state_tracker.add_debug_log(session_id, f"开始处理用户输入: {content}")

        # Agent进行ReAct循环
        await agent_react_loop(agent, session_id, content)

        return {
            "success": True,
            "message": "Agent processing completed"
        }

    except Exception as e:
        error_msg = f"处理消息时发生错误: {str(e)}"
        state_tracker.add_debug_log(session_id, error_msg)
        state_tracker.set_error(session_id, error_msg)
        raise


async def agent_react_loop(agent, session_id: str, user_input: str):
    """Agent的ReAct思考→行动循环"""
    max_iterations = 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        state_tracker.add_debug_log(session_id, f"ReAct循环第{iteration}轮")

        # 步骤1: 思考 (Reasoning)
        thought = await agent_think(agent, session_id, user_input)
        if thought:
            state_tracker.add_conversation(session_id, "assistant", f"💭 思考: {thought}")

        # 步骤2: 决定行动 (Action)
        action = await agent_decide_action(agent, session_id)
        if not action:
            break

        state_tracker.add_debug_log(session_id, f"决定执行行动: {action['type']}")

        # 步骤3: 执行行动
        action_result = await agent_execute_action(agent, session_id, action)

        # 步骤4: 观察结果，决定是否继续
        if action.get('type') == 'complete':
            state_tracker.add_debug_log(session_id, "Agent任务完成")
            break

        # 如果是生成音乐，开始异步生成
        if action.get('type') == 'generate_music':
            await start_music_generation(agent, session_id)
            break

        await asyncio.sleep(0.5)  # 避免过快循环


async def agent_think(agent, session_id: str, context: str) -> str:
    """Agent思考阶段"""
    current_stage = agent.session.current_stage

    # 根据当前阶段和上下文进行思考
    thought = None
    if current_stage == "init":
        thought = f"用户想要生成音乐：{context}。我需要分析他们的需求，然后生成合适的歌词。"
    elif current_stage == "collecting_requirements":
        thought = "我需要进一步了解用户的具体需求，如音乐风格、情绪等。"
    elif current_stage == "generating_lyrics":
        thought = "我正在基于用户需求生成歌词候选版本。"
    elif current_stage == "reviewing_lyrics":
        thought = "我需要展示歌词给用户审核，等待他们的反馈。"
    elif current_stage == "preparing_generation":
        thought = "歌词已确认，我需要准备音乐生成参数。"
    elif current_stage == "generating_music":
        thought = "正在调用MCP服务生成音乐..."

    # 记录思考过程到session
    if thought:
        agent.session.add_thought(thought)
        # 发射思考事件
        await global_hook_manager.emit_thought_event(session_id, thought, current_stage)

    return thought


async def agent_decide_action(agent, session_id: str) -> dict:
    """Agent决定下一步行动"""
    current_stage = agent.session.current_stage

    # 调试日志
    state_tracker.add_debug_log(session_id, f"Agent current stage: {current_stage}")

    if current_stage == "init":
        return {"type": "analyze_requirements", "data": {}}
    elif current_stage == "collecting_requirements":
        return {"type": "generate_lyrics", "data": {}}
    elif current_stage == "generating_lyrics":
        return {"type": "present_lyrics", "data": {}}
    elif current_stage == "reviewing_lyrics":
        if agent.session.lyrics_versions and hasattr(agent.session.lyrics_versions[0], 'approved') and agent.session.lyrics_versions[0].approved:
            return {"type": "generate_music", "data": {}}
        else:
            return {"type": "wait_for_review", "data": {}}
    elif current_stage == "completed":
        return {"type": "complete", "data": {}}

    # 如果stage不匹配，默认回到分析需求
    state_tracker.add_debug_log(session_id, f"Unknown stage '{current_stage}', defaulting to analyze_requirements")
    return {"type": "analyze_requirements", "data": {}}


async def agent_execute_action(agent, session_id: str, action: dict) -> str:
    """执行Agent行动"""
    import time
    start_time = time.time()
    action_type = action["type"]
    result = None
    error = None

    try:
        if action_type == "analyze_requirements":
            # 分析用户需求
            # 从state_tracker获取最新的用户消息
            session = state_tracker.get_session(session_id)
            if session and session.conversation_history:
                last_user_message = None
                for turn in reversed(session.conversation_history):
                    if turn.role == "user":
                        last_user_message = turn.content
                        break

                if last_user_message:
                    response = await asyncio.to_thread(agent.process_user_input, last_user_message)
                    state_tracker.add_conversation(session_id, "assistant", response)

                    # 确保用户需求已经设置并同步到state_tracker
                    if agent.session.user_requirement:
                        # 同步Agent的session状态到state_tracker
                        tracker_session = state_tracker.get_session(session_id)
                        if tracker_session:
                            tracker_session.user_requirement = agent.session.user_requirement
                            tracker_session.current_stage = agent.session.current_stage

                        # 需求收集完成，可以进入歌词生成
                        state_tracker.update_stage(session_id, "collecting_requirements", "用户需求已分析，准备生成歌词")
                        result = "需求分析完成，已收集用户需求"
                    else:
                        # 需求还未完全收集，保持在collecting_requirements阶段
                        state_tracker.update_stage(session_id, "collecting_requirements", "正在收集用户需求详情")
                        result = "需求收集中，需要更多信息"
                else:
                    result = "没有找到用户消息"
            else:
                result = "会话历史为空"

        elif action_type == "generate_lyrics":
            # 生成歌词
            state_tracker.update_stage(session_id, "generating_lyrics", "正在生成歌词...")

            try:
                # 确保Agent有用户需求数据
                tracker_session = state_tracker.get_session(session_id)
                if tracker_session and tracker_session.user_requirement and not agent.session.user_requirement:
                    agent.session.user_requirement = tracker_session.user_requirement

                lyrics_candidates = await asyncio.to_thread(agent._generate_lyrics_candidates)
                if lyrics_candidates:
                    agent.session.lyrics_versions = lyrics_candidates
                    agent.session.update_stage("reviewing_lyrics")

                    # 同步lyrics到state_tracker
                    if tracker_session:
                        tracker_session.lyrics_versions = lyrics_candidates
                        tracker_session.current_stage = "reviewing_lyrics"

                    best_lyrics = lyrics_candidates[0]
                    response = f"🎵 我为您创作了以下歌词：\n\n{best_lyrics.content}\n\n请问您对这首歌词满意吗？如果满意请回复'满意'或'生成音乐'，如需修改请告诉我您的建议。"

                    state_tracker.add_conversation(session_id, "assistant", response)
                    state_tracker.update_stage(session_id, "reviewing_lyrics", "等待用户审核歌词")

                    result = "歌词生成完成"
                else:
                    result = "歌词生成失败"
            except Exception as e:
                error = str(e)
                state_tracker.add_debug_log(session_id, f"歌词生成错误: {str(e)}")
                result = f"歌词生成失败: {str(e)}"

        elif action_type == "present_lyrics":
            # 展示歌词给用户
            if agent.session.lyrics_versions:
                lyrics = agent.session.lyrics_versions[0]
                response = f"这是为您创作的歌词：\n\n{lyrics.content}\n\n您觉得怎么样？"
                state_tracker.add_conversation(session_id, "assistant", response)
            result = "歌词已展示"

        elif action_type == "wait_for_review":
            # 等待用户审核
            result = "等待用户审核歌词"

        elif action_type == "complete":
            state_tracker.update_stage(session_id, "completed", "任务完成")
            result = "任务完成"

        else:
            result = "未知行动"

    except Exception as e:
        error = str(e)
        result = f"执行失败: {str(e)}"
    finally:
        # 记录行动日志
        duration = time.time() - start_time
        agent.session.add_action_log(
            action_type=action_type,
            action_data=action.get("data", {}),
            result=result,
            error=error,
            duration=duration
        )

        # 发射行动事件
        await global_hook_manager.emit_action_event(
            session_id=session_id,
            action_type=action_type,
            action_data=action.get("data", {}),
            result=result,
            error=error
        )

    return result or "执行完成"


async def start_music_generation(agent, session_id: str):
    """开始音乐生成过程"""
    try:
        state_tracker.update_stage(session_id, "generating_music", "正在生成音乐...")
        state_tracker.add_debug_log(session_id, "开始音乐生成")

        if agent.session.lyrics_versions:
            selected_lyrics = agent.session.lyrics_versions[0]
            agent.session.selected_lyrics = selected_lyrics

            # 构建生成参数
            params = await asyncio.to_thread(agent._build_generation_params, selected_lyrics)

            # 调用MCP生成音乐
            result = await asyncio.to_thread(agent._invoke_mcp, params)

            # 保存结果
            agent.session.generation_result = result
            agent.session.update_stage("completed")

            # 记录生成的资产
            if hasattr(result, 'audio_paths') and result.audio_paths:
                for audio_path in result.audio_paths:
                    if audio_path:
                        asset = agent.session.add_asset(
                            asset_type="audio",
                            file_path=audio_path,
                            metadata=getattr(result, 'metadata', {}),
                            is_final=True
                        )
                        # 发射资产事件
                        await global_hook_manager.emit_asset_event(
                            session_id=session_id,
                            asset_type="audio",
                            asset_id=asset.asset_id,
                            file_path=audio_path,
                            is_final=True
                        )

            # 记录最终歌词资产
            if agent.session.selected_lyrics:
                asset = agent.session.add_asset(
                    asset_type="lyrics",
                    content=agent.session.selected_lyrics.content,
                    metadata={"version": agent.session.selected_lyrics.version},
                    is_final=True
                )
                # 发射资产事件
                await global_hook_manager.emit_asset_event(
                    session_id=session_id,
                    asset_type="lyrics",
                    asset_id=asset.asset_id,
                    content=agent.session.selected_lyrics.content,
                    is_final=True
                )

            # 发送完成事件
            state_tracker.update_stage(session_id, "completed", "音乐生成完成！")
            state_tracker.add_conversation(session_id, "assistant", "🎉 音乐生成完成！您可以在右侧播放器中试听和下载。")

            # 发送完成事件到前端
            state_tracker._emit_event(session_id, "complete", {
                "session_id": session_id,
                "result": "音乐生成完成"
            })

        else:
            raise Exception("没有找到歌词版本")

    except Exception as e:
        state_tracker.add_debug_log(session_id, f"音乐生成失败: {str(e)}")
        state_tracker.set_error(session_id, f"音乐生成失败: {str(e)}")
        agent.session.update_stage("failed")


@router.post("/{session_id}/message", response_model=ChatMessageResponse)
async def send_message(
    session_id: str,
    request: ChatMessageRequest,
    background_tasks: BackgroundTasks
):
    """发送聊天消息"""
    session = state_tracker.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"会话 {session_id} 不存在"
            }
        )

    try:
        # 立即返回响应，在后台处理消息
        message_id = f"msg_{int(asyncio.get_event_loop().time())}"

        background_tasks.add_task(
            process_message_async,
            session_id,
            request.content
        )

        return ChatMessageResponse(
            success=True,
            data={
                "message_id": message_id,
                "agent_response": "正在处理您的消息...",
                "stage": "processing_message",
                "next_action": "请稍候"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"处理消息失败: {str(e)}"
            }
        )


@router.post("/{session_id}/lyrics/review")
async def review_lyrics(
    session_id: str,
    request: LyricsReviewRequest
):
    """审核歌词"""
    session = state_tracker.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SESSION_NOT_FOUND",
                "message": f"会话 {session_id} 不存在"
            }
        )

    try:
        # 更新歌词审核状态
        state_tracker.update_stage(
            session_id,
            "reviewing_lyrics" if not request.approved else "preparing_generation",
            f"歌词版本 {request.version} {'已批准' if request.approved else '需要修改'}"
        )

        if request.feedback:
            state_tracker.add_debug_log(
                session_id,
                f"用户反馈: {request.feedback}",
                metadata={"lyrics_version": request.version}
            )

        return {
            "success": True,
            "data": {
                "version": request.version,
                "approved": request.approved,
                "next_action": "准备生成音乐" if request.approved else "重新生成歌词"
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"歌词审核失败: {str(e)}"
            }
        )


@router.get("/{session_id}/events")
async def get_session_events(
    session_id: str,
    event_type: Optional[str] = None,
    limit: int = 50
):
    """获取会话事件历史"""
    try:
        # 解析事件类型
        parsed_event_type = None
        if event_type:
            try:
                parsed_event_type = AgentEventType(event_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "INVALID_EVENT_TYPE", "message": f"无效的事件类型: {event_type}"}
                )

        # 获取事件历史
        events = global_event_bus.get_event_history(
            session_id=session_id,
            event_type=parsed_event_type,
            limit=limit
        )

        # 转换为API响应格式
        event_data = [event.to_dict() for event in events]

        return {
            "success": True,
            "data": {
                "events": event_data,
                "total": len(event_data),
                "session_id": session_id
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"获取事件历史失败: {str(e)}"
            }
        )
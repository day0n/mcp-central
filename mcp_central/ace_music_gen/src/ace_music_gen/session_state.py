"""会话状态管理模块

定义音乐生成对话Agent的完整数据模型
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import json


@dataclass
class ConversationTurn:
    """单轮对话记录"""
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    meta: Optional[Dict[str, Any]] = None


@dataclass
class UserRequirement:
    """用户需求结构化表示"""
    style: str = ""  # 音乐风格，如"伤感说唱"、"激昂摇滚"
    mood: str = ""   # 情绪描述，如"悲伤"、"愤怒"、"温柔"
    duration: float = 30.0  # 音频时长（秒）
    language: str = "中文"  # 歌词语言
    specific_requests: List[str] = field(default_factory=list)  # 用户特殊要求
    theme: str = ""  # 主题内容，如"失恋"、"励志"、"友情"
    target_audience: str = ""  # 目标听众，如"年轻人"、"中年群体"


@dataclass
class AgentActionLog:
    """Agent行动记录"""
    action_type: str  # "analyze_requirements" | "generate_lyrics" | "present_lyrics" | "generate_music" | "wait_for_review" | "complete"
    action_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    result: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class GeneratedAsset:
    """统一生成资产管理"""
    asset_type: str  # "lyrics" | "audio" | "metadata" | "evaluation"
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: Optional[str] = None
    content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    is_final: bool = False


@dataclass
class LyricsVersion:
    """歌词版本管理"""
    content: str
    version: int
    user_feedback: Optional[str] = None
    approved: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    pinyin_annotated: Optional[str] = None  # 拼音标注版本


@dataclass
class GenerationParams:
    """音乐生成参数"""
    prompt: str  # 英文技术描述
    lyrics: str  # 最终确认的歌词
    guidance_schedule: List[Dict[str, float]] = field(default_factory=lambda: [
        {"position": 0.0, "scale": 10.0},
        {"position": 0.4, "scale": 16.0},
        {"position": 0.8, "scale": 12.0},
        {"position": 1.0, "scale": 8.0}
    ])
    lora_config: Dict[str, Any] = field(default_factory=dict)
    audio_duration: float = 30.0
    candidate_count: int = 3
    cache_settings: Dict[str, bool] = field(default_factory=lambda: {
        "enable_cache": True,
        "force_refresh": False
    })


@dataclass
class MusicGenerationResult:
    """音乐生成结果"""
    success: bool
    audio_paths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    error: Optional[str] = None
    generation_time: Optional[float] = None  # 生成耗时（秒）
    evaluation_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class MusicSessionState:
    """完整的音乐生成会话状态"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 对话历史
    conversation_history: List[ConversationTurn] = field(default_factory=list)

    # 用户需求
    user_requirement: Optional[UserRequirement] = None

    # 歌词管理
    lyrics_versions: List[LyricsVersion] = field(default_factory=list)
    selected_lyrics: Optional[LyricsVersion] = None

    # 生成参数
    generation_params: Optional[GenerationParams] = None

    # 生成结果
    generation_result: Optional[MusicGenerationResult] = None

    # 当前阶段
    current_stage: str = "init"  # "init" | "collecting_requirements" | "generating_lyrics" | "reviewing_lyrics" | "generating_music" | "completed" | "failed"

    # 调试日志
    debug_logs: List[str] = field(default_factory=list)

    # 配置选项
    config: Dict[str, Any] = field(default_factory=dict)

    # ReAct 元信息扩展
    actions: List[AgentActionLog] = field(default_factory=list)  # Agent行动记录
    thoughts: List[str] = field(default_factory=list)  # 思考过程记录
    final_assets: List[GeneratedAsset] = field(default_factory=list)  # 统一资产管理

    def add_conversation_turn(self, role: str, content: str, meta: Optional[Dict] = None):
        """添加对话记录"""
        turn = ConversationTurn(role=role, content=content, meta=meta)
        self.conversation_history.append(turn)
        self.updated_at = datetime.now()

    def add_debug_log(self, message: str):
        """添加调试日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.debug_logs.append(log_entry)
        self.updated_at = datetime.now()

    def update_stage(self, new_stage: str):
        """更新当前阶段"""
        old_stage = self.current_stage
        self.current_stage = new_stage
        self.add_debug_log(f"Stage transition: {old_stage} -> {new_stage}")

    def add_lyrics_version(self, content: str) -> LyricsVersion:
        """添加新的歌词版本"""
        version = len(self.lyrics_versions) + 1
        lyrics = LyricsVersion(content=content, version=version)
        self.lyrics_versions.append(lyrics)
        self.updated_at = datetime.now()
        return lyrics

    def select_lyrics(self, version: int) -> bool:
        """选择指定版本的歌词"""
        for lyrics in self.lyrics_versions:
            if lyrics.version == version:
                self.selected_lyrics = lyrics
                lyrics.approved = True
                self.add_debug_log(f"Selected lyrics version {version}")
                return True
        return False

    def add_action_log(self, action_type: str, action_data: Dict[str, Any] = None,
                      result: str = None, error: str = None, duration: float = None):
        """添加Agent行动记录"""
        action_log = AgentActionLog(
            action_type=action_type,
            action_data=action_data or {},
            result=result,
            error=error,
            duration_seconds=duration
        )
        self.actions.append(action_log)
        self.updated_at = datetime.now()

    def add_thought(self, thought: str):
        """添加思考记录"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        thought_entry = f"[{timestamp}] {thought}"
        self.thoughts.append(thought_entry)
        self.updated_at = datetime.now()

    def add_asset(self, asset_type: str, file_path: str = None, content: str = None,
                 metadata: Dict[str, Any] = None, is_final: bool = False) -> GeneratedAsset:
        """添加生成资产"""
        asset = GeneratedAsset(
            asset_type=asset_type,
            file_path=file_path,
            content=content,
            metadata=metadata or {},
            is_final=is_final
        )
        self.final_assets.append(asset)
        self.updated_at = datetime.now()
        return asset

    def get_final_assets_by_type(self, asset_type: str) -> List[GeneratedAsset]:
        """根据类型获取最终资产"""
        return [asset for asset in self.final_assets if asset.asset_type == asset_type and asset.is_final]

    def get_latest_action(self) -> Optional[AgentActionLog]:
        """获取最新的行动记录"""
        return self.actions[-1] if self.actions else None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于序列化）"""
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif hasattr(obj, '__dict__'):
                return convert_datetime(obj.__dict__)
            return obj

        return convert_datetime(self.__dict__)

    def save_to_file(self, filepath: str):
        """保存会话状态到JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> 'MusicSessionState':
        """从JSON文件加载会话状态"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 这里可以添加更复杂的反序列化逻辑
        # 目前简化处理，实际使用时可能需要处理datetime等特殊类型
        session = cls()
        session.__dict__.update(data)
        return session


@dataclass
class LLMExchange:
    """统一的LLM交互消息模型"""
    role: str  # "user" | "assistant" | "system"
    content: str
    meta: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, str]:
        """转换为LLM API调用格式"""
        return {
            "role": self.role,
            "content": self.content
        }


@dataclass
class InteractiveAgentConfig:
    """交互式Agent配置"""
    max_lyrics_retries: int = 3  # 歌词生成最大重试次数
    max_generation_retries: int = 2  # 音乐生成最大重试次数
    enable_pinyin_annotation: bool = True  # 是否启用拼音标注
    auto_approve_single_lyrics: bool = False  # 只有一个歌词版本时是否自动确认
    default_audio_duration: float = 30.0
    default_candidate_count: int = 3
    enable_memory: bool = False  # 是否启用长期记忆（预留）

    # LLM配置
    llm_model: str = "qwen-turbo-latest"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000

    # MCP配置
    mcp_base_url: str = "http://localhost:8000"
    mcp_timeout: int = 300  # 5分钟超时
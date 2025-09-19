"""ACE Music Generator - 基于ACE-Step的音乐生成工具包"""

from .generator import SimpleACEMusicGen, main
from .evaluator import AudioEvaluator
from .llm_client import LLMClient
from .mcp_client import ACEStepMCPClient, MCPError
from .interactive_agent import InteractiveMusicAgent
from .pinyin_helper import annotate_polyphonic_lyrics, get_polyphonic_stats, quick_annotate
from .session_state import (
    MusicSessionState,
    UserRequirement,
    LyricsVersion,
    GenerationParams,
    MusicGenerationResult,
    LLMExchange,
    InteractiveAgentConfig
)

__version__ = "0.1.0"
__all__ = [
    "SimpleACEMusicGen",
    "AudioEvaluator",
    "LLMClient",
    "ACEStepMCPClient",
    "MCPError",
    "InteractiveMusicAgent",
    "annotate_polyphonic_lyrics",
    "get_polyphonic_stats",
    "quick_annotate",
    "MusicSessionState",
    "UserRequirement",
    "LyricsVersion",
    "GenerationParams",
    "MusicGenerationResult",
    "LLMExchange",
    "InteractiveAgentConfig",
    "main",
]

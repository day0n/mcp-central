"""ACE Music Generator - 基于ACE-Step的音乐生成工具包"""

from .generator import SimpleACEMusicGen, main
from .evaluator import AudioEvaluator
from .llm_client import LLMClient

__version__ = "0.1.0"
__all__ = ["SimpleACEMusicGen", "AudioEvaluator", "LLMClient", "main"]
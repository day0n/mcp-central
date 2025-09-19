"""MCP 客户端封装，用于访问 ACE-Step 音乐生成服务"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, List
import requests

from .session_state import MusicGenerationResult


class MCPError(RuntimeError):
    """表示在调用 MCP 服务时出现的错误。"""


class ACEStepMCPClient:
    """面向 ACE-Step 的简单 MCP 客户端。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 300.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        env_url = os.environ.get("ACE_MCP_BASE_URL")
        self.base_url = (base_url or env_url or "http://127.0.0.1:8000").rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def health_check(self) -> Dict[str, Any]:
        """检查 MCP 服务器健康状态。返回 JSON 字典，如失败则抛出 MCPError。"""
        url = f"{self.base_url}/health"
        try:
            response = self.session.get(url, timeout=10, headers={"Connection": "close"})
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # pragma: no cover - 运行时保护
            raise MCPError(f"健康检查失败: {exc}") from exc

    def generate_music(
        self,
        prompt: str,
        lyrics: str,
        audio_duration: float = 30.0,
        candidate_count: int = 3,
        guidance_schedule: Optional[List[Dict[str, float]]] = None,
        lora_config: Optional[Dict[str, Any]] = None,
        cache_settings: Optional[Dict[str, bool]] = None
    ) -> MusicGenerationResult:
        """调用 ACE-Step MCP 服务生成音乐。

        Args:
            prompt: 英文技术描述
            lyrics: 歌词内容
            audio_duration: 音频时长（秒）
            candidate_count: 候选数量
            guidance_schedule: 指导调度
            lora_config: LoRA配置
            cache_settings: 缓存设置

        Returns:
            MusicGenerationResult: 生成结果
        """
        # 构建请求payload（根据MCP服务的实际格式）
        generation_config = {
            "prompt": prompt,
            "lyrics": lyrics,
            "guidance_schedule": guidance_schedule or [
                {"position": 0.0, "scale": 10.0},
                {"position": 0.4, "scale": 16.0},
                {"position": 0.8, "scale": 12.0},
                {"position": 1.0, "scale": 8.0}
            ],
            "lora_config": lora_config or {},
            "audio_duration": audio_duration,
            "candidate_count": candidate_count,
            "cache_settings": cache_settings or {
                "enable_cache": True,
                "force_refresh": False
            }
        }

        payload = {
            "prompt": prompt,
            "lyrics": lyrics,
            "generation_config": generation_config
        }

        url = f"{self.base_url}/generate_music"
        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={"Connection": "close"}
            )
            response.raise_for_status()
            result_data = response.json()

            # 解析响应
            if result_data.get("success", False):
                return MusicGenerationResult(
                    success=True,
                    audio_paths=result_data.get("data", {}).get("audio_paths", []),
                    metadata=result_data.get("data", {}).get("metadata", {}),
                    session_id=result_data.get("request_id", "")
                )
            else:
                return MusicGenerationResult(
                    success=False,
                    error=result_data.get("error", "未知错误"),
                    session_id=result_data.get("request_id", "")
                )

        except requests.exceptions.Timeout:
            return MusicGenerationResult(
                success=False,
                error=f"请求超时（{self.timeout}秒）"
            )
        except requests.exceptions.ConnectionError:
            return MusicGenerationResult(
                success=False,
                error=f"无法连接到MCP服务 ({self.base_url})"
            )
        except requests.exceptions.RequestException as e:
            return MusicGenerationResult(
                success=False,
                error=f"网络请求失败: {str(e)}"
            )
        except Exception as exc:
            return MusicGenerationResult(
                success=False,
                error=f"调用 MCP 服务失败: {str(exc)}"
            )

    def generate_music_legacy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """传统的generate_music接口（向后兼容）"""
        url = f"{self.base_url}/generate_music"
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # pragma: no cover - 运行时保护
            raise MCPError(f"调用 MCP 服务失败: {exc}") from exc


__all__ = ["ACEStepMCPClient", "MCPError"]

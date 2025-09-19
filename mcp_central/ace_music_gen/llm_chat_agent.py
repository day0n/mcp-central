#!/usr/bin/env python3
"""
基于LLM多轮对话的音乐生成Agent
真正使用LLM进行智能对话和推理
"""

import os
import sys
import json
import time
import threading
import shutil
import itertools
from pathlib import Path
from typing import List, Dict, Any

# 添加src路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

from ace_music_gen.llm_client import LLMClient
from ace_music_gen.mcp_client import ACEStepMCPClient
from ace_music_gen.session_state import MusicSessionState, UserRequirement, LyricsVersion

class LLMMusicChatAgent:
    """基于LLM的多轮对话音乐Agent"""

    def __init__(self, api_key: str):
        self.llm_client = LLMClient(api_key=api_key, model="qwen-turbo-latest")
        self.mcp_client = ACEStepMCPClient(base_url="http://localhost:8000")
        self.session = MusicSessionState()
        self.conversation_history: List[Dict[str, str]] = []

        # Agent的系统提示
        self.system_prompt = """你是ACE音乐生成助手，一个专业的音乐创作AI助理。

你的核心能力：
1. 通过多轮对话收集用户的音乐需求
2. 生成个性化的歌词内容
3. 调用MCP服务生成实际音频
4. 提供音乐创作建议和指导

工作流程：
1. 需求收集阶段 - 了解用户想要的音乐风格、情感、主题等
2. 歌词创作阶段 - 根据需求生成符合要求的歌词
3. 音乐生成阶段 - 调用MCP服务生成音频文件
4. 结果展示阶段 - 展示生成结果并收集反馈

重要规则：
- 始终保持友好、专业的语调
- 主动引导用户完善需求信息
- 在每个阶段都要确认用户是否满意
- 如果用户不满意，要主动询问修改建议
- 记住对话上下文，避免重复询问已确认的信息

当前会话状态：刚开始对话
请主动问候用户并了解他们的音乐创作需求。"""

    def get_conversation_context(self) -> List[Dict[str, str]]:
        """构建LLM对话上下文"""
        messages = [{"role": "system", "content": self.system_prompt}]

        # 添加会话状态信息
        if self.session.current_stage != "init":
            status_info = f"\n\n当前会话状态：\n"
            status_info += f"- 阶段：{self.session.current_stage}\n"

            if self.session.user_requirement:
                req = self.session.user_requirement
                status_info += f"- 音乐风格：{req.style or '未确定'}\n"
                status_info += f"- 情感基调：{req.mood or '未确定'}\n"
                status_info += f"- 主题内容：{req.theme or '未确定'}\n"
                status_info += f"- 音频时长：{req.duration}秒\n"
                status_info += f"- 歌词语言：{req.language}\n"

            if self.session.lyrics_versions:
                status_info += f"- 已生成歌词版本：{len(self.session.lyrics_versions)}个\n"

            messages[0]["content"] += status_info

        # 添加对话历史
        messages.extend(self.conversation_history)

        return messages

    def chat_with_llm(self, user_input: str) -> str:
        """与LLM进行对话"""
        try:
            # 添加用户输入到历史
            self.conversation_history.append({"role": "user", "content": user_input})
            self.session.add_conversation_turn("user", user_input)

            # 构建对话上下文
            messages = self.get_conversation_context()

            # 调用LLM
            assistant_response = self.llm_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )

            # 添加助手回复到历史
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            self.session.add_conversation_turn("assistant", assistant_response)

            # 分析回复内容，更新会话状态
            self.analyze_and_update_session(user_input, assistant_response)

            return assistant_response

        except Exception as e:
            return f"抱歉，处理您的请求时出现错误：{e}"

    def analyze_and_update_session(self, user_input: str, assistant_response: str):
        """分析对话内容并更新会话状态"""
        user_lower = user_input.lower()
        assistant_lower = assistant_response.lower()

        # 检测是否进入需求收集阶段
        if any(keyword in user_lower for keyword in ['音乐', '歌曲', '创作', '生成', '想要']):
            if self.session.current_stage == "init":
                self.session.update_stage("collecting_requirements")
                self.session.add_debug_log("开始收集用户音乐需求")

        # 尝试提取和更新用户需求
        self.extract_user_requirements(user_input)

        # 检测是否需要生成歌词
        if any(keyword in user_lower for keyword in ['生成歌词', '开始创作', '写歌词', '继续']):
            if self.session.current_stage == "collecting_requirements":
                self.session.update_stage("generating_lyrics")
                self.session.add_debug_log("开始生成歌词")

        # 检测歌词确认 - 当用户满意时开始音乐生成
        if any(keyword in user_lower for keyword in ['确认', '满意', '很好', '不错', '可以', '生成音乐', '开始生成']):
            if self.session.current_stage == "reviewing_lyrics" and self.session.lyrics_versions:
                self.session.update_stage("generating_music")
                self.session.add_debug_log("用户确认歌词，开始音乐生成")
                # 立即启动音乐生成
                self.generate_music_sync()

    def extract_user_requirements(self, user_input: str):
        """从用户输入中提取音乐需求信息"""
        user_lower = user_input.lower()

        # 初始化需求对象
        if not self.session.user_requirement:
            self.session.user_requirement = UserRequirement()

        req = self.session.user_requirement

        # 提取风格信息
        style_keywords = {
            '说唱': '说唱', 'rap': '说唱', 'hip-hop': '说唱',
            '流行': '流行', 'pop': '流行',
            '摇滚': '摇滚', 'rock': '摇滚',
            '民谣': '民谣', 'folk': '民谣',
            '电子': '电子音乐', 'electronic': '电子音乐',
            '古典': '古典音乐', 'classical': '古典音乐'
        }

        for keyword, style in style_keywords.items():
            if keyword in user_lower and not req.style:
                req.style = style
                self.session.add_debug_log(f"识别音乐风格：{style}")
                break

        # 提取情感信息
        mood_keywords = {
            '悲伤': '悲伤', '难过': '悲伤', '伤心': '悲伤',
            '快乐': '快乐', '开心': '快乐', '愉悦': '快乐',
            '激昂': '激昂', '热血': '激昂', '振奋': '激昂',
            '温柔': '温柔', '柔和': '温柔', '轻柔': '温柔',
            '愤怒': '愤怒', '生气': '愤怒',
            '浪漫': '浪漫', '甜蜜': '浪漫'
        }

        for keyword, mood in mood_keywords.items():
            if keyword in user_lower and not req.mood:
                req.mood = mood
                self.session.add_debug_log(f"识别情感基调：{mood}")
                break

        # 提取主题信息
        theme_keywords = {
            '失恋': '失恋', '分手': '失恋',
            '友情': '友情', '朋友': '友情',
            '爱情': '爱情', '恋爱': '爱情',
            '励志': '励志', '奋斗': '励志',
            '家庭': '家庭', '亲情': '亲情',
            '青春': '青春', '学生': '青春'
        }

        for keyword, theme in theme_keywords.items():
            if keyword in user_lower and not req.theme:
                req.theme = theme
                self.session.add_debug_log(f"识别主题内容：{theme}")
                break

        # 提取时长信息
        import re
        duration_match = re.search(r'(\d+)\s*秒', user_input)
        if duration_match:
            req.duration = float(duration_match.group(1))
            self.session.add_debug_log(f"设置音频时长：{req.duration}秒")

    def generate_lyrics_with_llm(self) -> str:
        """使用LLM生成歌词"""
        if not self.session.user_requirement:
            return "请先完善您的音乐需求信息"

        req = self.session.user_requirement

        lyrics_prompt = f"""请根据以下需求创作歌词：

音乐风格：{req.style or '流行'}
情感基调：{req.mood or '自然'}
主题内容：{req.theme or '生活感悟'}
歌词语言：{req.language}
音频时长：{req.duration}秒

要求：
1. 歌词要符合指定的风格和情感
2. 内容要积极向上，避免过于消极的表达
3. 语言要自然流畅，朗朗上口
4. 根据时长控制歌词长度（30秒约2-4句）
5. 如果是说唱风格，要有韵律感

请直接输出歌词内容，不要其他说明文字："""

        try:
            messages = [{"role": "user", "content": lyrics_prompt}]
            lyrics_content = self.llm_client.chat_completion(
                messages=messages,
                temperature=0.8,
                max_tokens=500
            ).strip()

            # 添加到会话中
            lyrics_version = self.session.add_lyrics_version(lyrics_content)
            self.session.add_debug_log(f"生成歌词版本 {lyrics_version.version}")

            return lyrics_content

        except Exception as e:
            return f"歌词生成失败：{e}"

    def generate_music_sync(self):
        """异步生成音乐"""
        try:
            print("\n🎵 正在为您生成音乐...")
            self.session.add_debug_log("开始调用MCP生成音乐")

            # 检查是否有歌词
            if not self.session.lyrics_versions:
                print("❌ 没有可用的歌词版本")
                return

            # 获取最新的歌词
            latest_lyrics = self.session.lyrics_versions[-1]
            lyrics_content = latest_lyrics.content

            # 根据用户需求生成音乐参数
            req = self.session.user_requirement
            if not req:
                print("❌ 缺少用户需求信息")
                return

            # 构造音乐生成提示词
            style_map = {
                "说唱": "Rap, hip-hop",
                "流行": "Pop, melodic",
                "摇滚": "Rock, energetic",
                "民谣": "Folk, acoustic",
                "电子": "Electronic, synthesized"
            }

            mood_map = {
                "悲伤": "melancholic, emotional, slow tempo",
                "快乐": "upbeat, cheerful, energetic",
                "激昂": "powerful, intense, driving",
                "温柔": "soft, gentle, warm",
                "愤怒": "aggressive, intense, heavy"
            }

            style_desc = style_map.get(req.style, "Pop")
            mood_desc = mood_map.get(req.mood, "emotional")

            # 构造英文prompt
            prompt = f"{style_desc}, {mood_desc}, male vocals, clear pronunciation, professional production"

            print(f"🎧 音乐参数:")
            print(f"   风格: {req.style} -> {style_desc}")
            print(f"   情感: {req.mood} -> {mood_desc}")
            print(f"   时长: {req.duration}秒")
            print(f"   提示词: {prompt}")

            # 调用MCP服务生成音乐
            try:
                print("🔗 正在连接MCP服务...")

                # 检查MCP服务健康状态
                health = self.mcp_client.health_check()
                print(f"✅ MCP服务状态: {health.get('status', 'unknown')}")

                # 调用音乐生成
                print("🎼 开始生成音频...")

                # 启动进度条线程
                stop_event = threading.Event()
                progress_thread = threading.Thread(
                    target=self._render_progress_bar,
                    args=(stop_event,),
                    daemon=True,
                )
                progress_thread.start()

                try:
                    generation_result = self.call_mcp_generate_music(prompt, lyrics_content, req.duration)
                finally:
                    stop_event.set()
                    progress_thread.join(timeout=1)
                    sys.stdout.write("\r" + " " * 80 + "\r")

                if generation_result and generation_result.success:
                    # 生成成功
                    self.session.generation_result = generation_result
                    self.session.update_stage("completed")

                    print(f"\n✅ 音乐生成成功！")
                    print(f"🎵 生成的音频文件:")
                    for i, path in enumerate(generation_result.audio_paths, 1):
                        print(f"   {i}. {path}")

                    if generation_result.generation_time:
                        print(f"⏱️  生成耗时: {generation_result.generation_time:.1f}秒")

                    # 保存到会话资产
                    for i, audio_path in enumerate(generation_result.audio_paths):
                        asset = self.session.add_asset(
                            asset_type="audio",
                            file_path=audio_path,
                            metadata={
                                "style": req.style,
                                "mood": req.mood,
                                "duration": req.duration,
                                "prompt": prompt,
                                "lyrics": lyrics_content
                            },
                            is_final=True
                        )
                        print(f"💾 保存音频资产: {asset.asset_id}")

                else:
                    # 生成失败
                    error_msg = generation_result.error if generation_result else "未知错误"
                    print(f"❌ 音乐生成失败: {error_msg}")
                    self.session.update_stage("failed")
                    self.session.add_debug_log(f"音乐生成失败: {error_msg}")

            except Exception as e:
                print(f"❌ MCP调用失败: {e}")
                self.session.update_stage("failed")
                self.session.add_debug_log(f"MCP调用失败: {e}")

        except Exception as e:
            print(f"❌ 音乐生成过程出错: {e}")
            self.session.update_stage("failed")

    def call_mcp_generate_music(self, prompt: str, lyrics: str, duration: float):
        """调用MCP服务生成音乐"""
        try:
            # 准备生成参数
            generation_params = {
                "prompt": prompt,
                "lyrics": lyrics,
                "audio_duration": duration,
                "candidate_count": 1,  # 先生成一个候选
                "guidance_schedule": [
                    {"position": 0.0, "scale": 10.0},
                    {"position": 0.4, "scale": 16.0},
                    {"position": 0.8, "scale": 12.0},
                    {"position": 1.0, "scale": 8.0}
                ],
                "cache_settings": {
                    "enable_cache": True,
                    "force_refresh": False
                }
            }

            # 调用MCP生成接口
            import time
            start_time = time.time()

            result = self.mcp_client.generate_music(**generation_params)

            generation_time = time.time() - start_time

            # 构造结果对象
            from ace_music_gen.session_state import MusicGenerationResult

            if result and hasattr(result, 'success') and result.success:
                generation_result = MusicGenerationResult(
                    success=True,
                    audio_paths=result.audio_paths if hasattr(result, 'audio_paths') else [],
                    session_id=self.session.session_id,
                    generation_time=generation_time,
                    metadata={
                        "prompt": prompt,
                        "lyrics": lyrics,
                        "duration": duration,
                        "model_version": getattr(result, 'model_version', 'unknown')
                    }
                )
            else:
                generation_result = MusicGenerationResult(
                    success=False,
                    session_id=self.session.session_id,
                    error=getattr(result, 'error', '生成失败'),
                    generation_time=generation_time
                )

            return generation_result

        except Exception as e:
            from ace_music_gen.session_state import MusicGenerationResult
            return MusicGenerationResult(
                success=False,
                session_id=self.session.session_id,
                error=str(e)
            )

    def start_chat(self):
        """开始聊天对话"""
        print("=" * 60)
        print("🎵 ACE音乐生成助手 - LLM驱动版")
        print("=" * 60)
        print("我是您的AI音乐创作助手！我会通过对话了解您的需求，")
        print("然后为您创作个性化的音乐作品。")
        print()
        print("输入 'quit'、'exit' 或 '退出' 来结束对话")
        print("输入 'status' 查看当前会话状态")
        print("输入 'generate' 生成歌词（需求收集完成后）")
        print("-" * 60)

        # 获取AI的开场白
        try:
            messages = self.get_conversation_context()
            response = self.llm_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            print(f"\n🤖 助手: {response}")
            self.conversation_history.append({"role": "assistant", "content": response})
        except Exception as e:
            print(f"\n🤖 助手: 您好！我是ACE音乐生成助手。请告诉我您想要创作什么样的音乐？")

        while True:
            try:
                user_input = input("\n🧑 您: ").strip()

                if not user_input:
                    continue

                # 检查退出命令
                if user_input.lower() in ['quit', 'exit', '退出', 'bye']:
                    print("\n👋 感谢使用ACE音乐生成助手！再见！")
                    break

                # 检查状态命令
                if user_input.lower() == 'status':
                    self.show_status()
                    continue

                # 检查歌词生成命令
                if user_input.lower() == 'generate':
                    if self.session.current_stage in ["collecting_requirements", "generating_lyrics"]:
                        print("\n🎵 正在为您生成歌词...")
                        lyrics = self.generate_lyrics_with_llm()
                        print(f"\n📝 生成的歌词：\n{lyrics}")
                        self.session.update_stage("reviewing_lyrics")
                        print("\n请告诉我您对这个歌词版本的看法，满意的话我们可以继续生成音乐。")
                    else:
                        print("请先完善您的音乐需求信息")
                    continue

                # 与LLM对话
                print("\n🤖 助手: ", end="")
                response = self.chat_with_llm(user_input)
                print(response)

                # 显示简化状态
                stage_desc = {
                    "init": "初始状态",
                    "collecting_requirements": "收集需求中",
                    "generating_lyrics": "准备生成歌词",
                    "reviewing_lyrics": "歌词审核中",
                    "preparing_generation": "准备生成音乐",
                    "generating_music": "生成音乐中",
                    "completed": "完成"
                }
                current_desc = stage_desc.get(self.session.current_stage, self.session.current_stage)
                print(f"\n📍 状态: {current_desc}")

            except KeyboardInterrupt:
                print("\n\n👋 用户中断，再见！")
                break
            except EOFError:
                print("\n\n👋 输入结束，再见！")
                break
            except Exception as e:
                print(f"\n❌ 出现错误: {e}")

    def show_status(self):
        """显示详细状态"""
        print("\n📊 当前会话状态：")
        print(f"  会话ID: {self.session.session_id[:8]}...")
        print(f"  当前阶段: {self.session.current_stage}")
        print(f"  对话轮次: {len(self.session.conversation_history)}")

        if self.session.user_requirement:
            req = self.session.user_requirement
            print(f"  音乐需求:")
            print(f"    - 风格: {req.style or '未确定'}")
            print(f"    - 情感: {req.mood or '未确定'}")
            print(f"    - 主题: {req.theme or '未确定'}")
            print(f"    - 时长: {req.duration}秒")
            print(f"    - 语言: {req.language}")

        if self.session.lyrics_versions:
            print(f"  歌词版本: {len(self.session.lyrics_versions)}个")
            for i, lyrics in enumerate(self.session.lyrics_versions, 1):
                status = "✅已确认" if lyrics.approved else "⏳待审核"
                print(f"    版本{i}: {status}")

    def _render_progress_bar(self, stop_event: threading.Event) -> None:
        """简单的命令行进度条动画（模拟进度，缓解等待感）。"""
        try:
            term_width = shutil.get_terminal_size((80, 20)).columns
        except OSError:
            term_width = 80

        bar_width = max(20, min(40, term_width - 30))
        progress = 0
        spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])

        while not stop_event.is_set():
            progress = min(progress + 1, 99)
            filled = int(progress / 100 * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            sys.stdout.write(f"\r{next(spinner)} 音乐生成中: |{bar}| {progress:3d}%")
            sys.stdout.flush()
            stop_event.wait(0.25)

        # 停止后清空进度条占位
        sys.stdout.write("\r" + " " * (bar_width + 30) + "\r")
        sys.stdout.flush()


def main():
    """主函数"""
    print("🚀 启动基于LLM的音乐生成聊天助手...")

    # 获取API密钥
    api_key = os.getenv("ACE_MUSIC_GEN_API_KEY")
    if not api_key:
        api_key = input("请输入您的API密钥: ").strip()
        if not api_key:
            print("❌ 需要API密钥才能继续")
            sys.exit(1)

    print(f"✅ API密钥: {api_key[:10]}...")

    # 创建并启动Agent
    try:
        agent = LLMMusicChatAgent(api_key)
        agent.start_chat()
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""交互式音乐生成Agent

基于多轮对话的音乐生成Agent，支持需求收集、歌词生成确认、参数调优等功能
"""

import os
import re
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

from .session_state import (
    MusicSessionState,
    UserRequirement,
    LyricsVersion,
    GenerationParams,
    MusicGenerationResult,
    LLMExchange,
    InteractiveAgentConfig
)
from .llm_client import LLMClient
from .mcp_client import ACEStepMCPClient
from .pinyin_helper import annotate_polyphonic_lyrics, get_polyphonic_stats


class InteractiveMusicAgent:
    """交互式音乐生成Agent"""

    def __init__(
        self,
        llm_client: LLMClient,
        mcp_client: ACEStepMCPClient,
        config: Optional[InteractiveAgentConfig] = None
    ):
        self.llm_client = llm_client
        self.mcp_client = mcp_client
        self.config = config or InteractiveAgentConfig()
        self.session = MusicSessionState()
        self.memory_provider = None  # 预留长期记忆接口

    def run_dialog(self) -> MusicGenerationResult:
        """运行完整的对话流程"""
        try:
            self.session.update_stage("collecting_requirements")
            self.session.add_debug_log("开始交互式音乐生成流程")

            # 1. 收集用户需求
            user_requirement = self._collect_user_requirements()
            self.session.user_requirement = user_requirement

            # 2. 生成歌词候选
            self.session.update_stage("generating_lyrics")
            lyrics_candidates = self._generate_lyrics_candidates()

            # 3. 用户确认歌词
            self.session.update_stage("reviewing_lyrics")
            final_lyrics = self._review_with_user(lyrics_candidates)

            # 4. 构建生成参数
            generation_params = self._build_generation_params(final_lyrics)
            self.session.generation_params = generation_params

            # 5. 准备歌词用于生成
            prepared_lyrics = self._prepare_lyrics_for_generation(final_lyrics)

            # 🔥 修复：将拼音标注版本写回generation_params.lyrics
            generation_params.lyrics = prepared_lyrics

            # 6. 调用MCP生成音乐
            self.session.update_stage("generating_music")
            result = self._invoke_mcp(generation_params)

            self.session.generation_result = result
            if result.success:
                self.session.update_stage("completed")
            else:
                self.session.update_stage("failed")

            return result

        except Exception as e:
            error_msg = f"Agent运行失败: {str(e)}"
            self.session.add_debug_log(error_msg)
            self.session.update_stage("failed")
            return MusicGenerationResult(
                success=False,
                error=error_msg,
                session_id=self.session.session_id
            )

    def reset_session(self):
        """重置会话状态"""
        self.session = MusicSessionState()
        self.session.add_debug_log("会话已重置")

    def attach_memory_provider(self, provider):
        """附加长期记忆提供者（预留接口）"""
        self.memory_provider = provider
        self.session.add_debug_log("已附加记忆提供者")

    def process_user_input(self, user_message: str) -> str:
        """处理单个用户消息（用于web集成）"""
        self.session.add_conversation_turn("user", user_message)

        try:
            # 根据当前阶段决定如何处理用户输入
            current_stage = self.session.current_stage

            if current_stage == "init":
                # 开始收集需求
                self.session.update_stage("collecting_requirements")
                return self._handle_initial_message(user_message)

            elif current_stage == "collecting_requirements":
                return self._handle_requirement_collection(user_message)

            elif current_stage == "reviewing_lyrics":
                return self._handle_lyrics_review(user_message)

            elif current_stage == "generating_music":
                return "音乐正在生成中，请稍候..."

            elif current_stage == "completed":
                return "音乐生成已完成！您可以查看和下载生成的音乐。"

            else:
                return "抱歉，我不确定当前的状态。请描述您想要的音乐类型。"

        except Exception as e:
            self.session.add_debug_log(f"处理用户输入时出错: {str(e)}")
            return f"处理您的消息时出现了问题: {str(e)}"

    def _handle_initial_message(self, message: str) -> str:
        """处理初始消息，使用React式思维模式"""
        self.session.add_debug_log(f"Agent正在分析用户需求: {message}")

        # 使用LLM进行React式分析
        analysis_prompt = f"""
作为一个音乐生成助手，我需要分析用户的需求并制定行动计划。

用户输入: "{message}"

我需要理解：
1. 用户想要什么类型的音乐？
2. 什么风格和情绪？
3. 是否有特殊要求？

让我分析一下：

思考：用户说"{message}"
"""

        try:
            # 使用LLM分析用户需求
            analysis_response = self.llm_client.call(analysis_prompt, max_tokens=300)
            self.session.add_debug_log(f"LLM分析结果: {analysis_response[:100]}...")

            # 智能提取关键信息
            if "爱国" in message or "国家" in message or "祖国" in message:
                style = "流行"
                mood = "激昂"
                theme = "爱国情怀"
                analysis = "我理解您想要一首体现爱国情怀的音乐。这类音乐通常情感激昂，能够激发人们的爱国热情。"
            elif "悲伤" in message or "难过" in message or "失恋" in message:
                style = "民谣"
                mood = "悲伤"
                theme = "悲伤情感"
                analysis = "我感受到您想要表达悲伤或失落的情感。民谣风格很适合传达这种深层的情感体验。"
            elif "快乐" in message or "开心" in message or "庆祝" in message:
                style = "流行"
                mood = "快乐"
                theme = "快乐庆祝"
                analysis = "我听出您想要轻快愉悦的音乐！流行风格能很好地表达这种积极向上的情绪。"
            else:
                # 使用LLM智能分析
                mood = self._extract_mood_from_theme(message)
                style = "流行"  # 默认
                theme = message
                analysis = f"我正在分析您的需求：{message}。让我为您创作相应的音乐。"

            # 创建用户需求
            requirement = UserRequirement(
                style=style,
                mood=mood,
                duration=self.config.default_audio_duration,
                language="中文",
                specific_requests=[],
                theme=theme
            )

            self.session.user_requirement = requirement
            self.session.add_debug_log(f"解析的需求: 风格={style}, 情绪={mood}, 主题={theme}")

            # 构建智能回复
            response = f"""🎵 {analysis}

我将为您创作一首{style}风格的音乐，表达{mood}的情绪。

我的创作计划：
1. 📝 根据您的主题"{theme}"创作歌词
2. 🎼 生成相应的音乐旋律
3. 🎵 制作完整的音频作品

请稍等，我现在开始为您创作歌词..."""

            self.session.add_conversation_turn("assistant", response)

            # 异步开始歌词生成（这里先返回planning消息）
            return response

        except Exception as e:
            self.session.add_debug_log(f"分析用户需求时出错: {str(e)}")
            return f"我正在分析您的音乐需求：{message}。让我为您量身定制一首音乐作品！"

    def _handle_requirement_collection(self, message: str) -> str:
        """处理需求收集阶段的用户输入"""
        # 这里可以进一步完善需求
        return "请告诉我更多关于您想要的音乐的信息。"

    def _handle_lyrics_review(self, message: str) -> str:
        """处理歌词审核阶段的用户输入"""
        if "满意" in message or "好的" in message or "可以" in message or "开始生成" in message:
            # 用户满意，开始生成音乐
            if self.session.lyrics_versions:
                selected_lyrics = self.session.lyrics_versions[0]
                self.session.selected_lyrics = selected_lyrics
                self.session.update_stage("preparing_generation")

                # 构建生成参数
                params = self._build_generation_params(selected_lyrics)

                # 开始音乐生成
                self.session.update_stage("generating_music")
                try:
                    result = self._invoke_mcp(params)
                    self.session.final_result = result
                    self.session.update_stage("completed")

                    return "太好了！音乐已经生成完成。您可以在右侧面板中试听和下载生成的音乐。"
                except Exception as e:
                    self.session.add_debug_log(f"音乐生成失败: {str(e)}")
                    self.session.update_stage("failed")
                    return f"抱歉，音乐生成时遇到了问题: {str(e)}"
            else:
                return "没有找到歌词，请重新开始。"
        else:
            # 用户要求修改
            if self.session.lyrics_versions:
                original_lyrics = self.session.lyrics_versions[0].content
                modified_lyrics = self._modify_lyrics_based_on_feedback(original_lyrics, message)

                # 创建新的歌词版本
                new_version = LyricsVersion(
                    version=len(self.session.lyrics_versions) + 1,
                    content=modified_lyrics,
                    approved=False
                )
                self.session.lyrics_versions.append(new_version)

                response = f"根据您的反馈，我重新创作了歌词：\n\n{modified_lyrics}\n\n这个版本怎么样？"
                self.session.add_conversation_turn("assistant", response)
                return response
            else:
                return "没有找到原始歌词，请重新开始。"

    def _collect_user_requirements(self) -> UserRequirement:
        """收集用户需求"""
        print("\n🎵 欢迎使用 ACE 音乐生成助手！")
        print("我将帮助您创作个性化的音乐作品。")

        # 询问音乐主题和风格
        theme = input("\\n请描述您想要的音乐主题或情感（如：失恋的悲伤、成功的喜悦、朋友间的温暖）: ").strip()
        self.session.add_conversation_turn("user", f"音乐主题: {theme}")

        # 询问具体风格偏好
        style_prompt = """
请选择或描述您喜欢的音乐风格：
1. 说唱/Hip-hop（嘻哈、rap）
2. 流行/Pop（流行歌曲）
3. 摇滚/Rock（摇滚乐）
4. 民谣/Folk（民间音乐）
5. 电子/Electronic（电子音乐）
6. 其他（请描述）

您的选择: """
        style_input = input(style_prompt).strip()
        self.session.add_conversation_turn("user", f"风格选择: {style_input}")

        # 解析风格
        style = self._parse_style_input(style_input)

        # 询问时长
        duration_input = input(f"\\n音频时长（秒，默认{self.config.default_audio_duration}秒）: ").strip()
        try:
            duration = float(duration_input) if duration_input else self.config.default_audio_duration
        except ValueError:
            duration = self.config.default_audio_duration

        # 询问特殊要求
        special_requests = input("\\n有什么特殊要求吗？（如：要有吉他solo、节奏要快一些等，可选）: ").strip()
        requests_list = [special_requests] if special_requests else []

        # 使用LLM提取情绪
        mood = self._extract_mood_from_theme(theme)

        requirement = UserRequirement(
            style=style,
            mood=mood,
            duration=duration,
            language="中文",
            specific_requests=requests_list,
            theme=theme
        )

        self.session.add_debug_log(f"收集到用户需求: {requirement}")
        return requirement

    def _parse_style_input(self, style_input: str) -> str:
        """解析用户的风格输入"""
        style_input = style_input.lower()
        if "1" in style_input or "说唱" in style_input or "rap" in style_input or "hip" in style_input:
            return "说唱"
        elif "2" in style_input or "流行" in style_input or "pop" in style_input:
            return "流行"
        elif "3" in style_input or "摇滚" in style_input or "rock" in style_input:
            return "摇滚"
        elif "4" in style_input or "民谣" in style_input or "folk" in style_input:
            return "民谣"
        elif "5" in style_input or "电子" in style_input or "electronic" in style_input:
            return "电子"
        else:
            return style_input  # 用户自定义描述

    def _extract_mood_from_theme(self, theme: str) -> str:
        """使用LLM从主题中提取情绪"""
        prompt = f"""
根据用户描述的音乐主题，提取出主要的情绪关键词。

用户主题: {theme}

请从以下情绪中选择最符合的1-2个，用逗号分隔：
悲伤, 愤怒, 快乐, 温柔, 激昂, 忧郁, 浪漫, 怀旧, 励志, 平静, 狂野, 梦幻

如果以上都不合适，请直接用1-2个形容词概括情绪。

情绪:"""

        try:
            exchanges = [LLMExchange(role="user", content=prompt)]
            response = self.llm_client.chat_completion(exchanges)
            mood = response.strip()
            self.session.add_debug_log(f"LLM提取的情绪: {mood}")
            return mood
        except Exception as e:
            self.session.add_debug_log(f"情绪提取失败: {e}")
            return "未知"

    def _generate_lyrics_candidates(self) -> List[LyricsVersion]:
        """生成歌词候选"""
        requirement = self.session.user_requirement
        if not requirement:
            raise ValueError("用户需求未收集")

        print(f"\\n🎤 正在为您创作歌词...")
        print(f"主题: {requirement.theme}")
        print(f"风格: {requirement.style}")
        print(f"情绪: {requirement.mood}")

        candidates = []
        retries = 0

        while len(candidates) < 2 and retries < self.config.max_lyrics_retries:
            try:
                lyrics_content = self._generate_single_lyrics(requirement, attempt=retries + 1)
                lyrics = self.session.add_lyrics_version(lyrics_content)
                candidates.append(lyrics)
                self.session.add_debug_log(f"成功生成歌词版本 {lyrics.version}")

            except Exception as e:
                retries += 1
                self.session.add_debug_log(f"歌词生成失败 (尝试 {retries}): {e}")
                if retries >= self.config.max_lyrics_retries:
                    raise Exception(f"歌词生成多次失败，已达到最大重试次数 ({self.config.max_lyrics_retries})")

        return candidates

    def _generate_single_lyrics(self, requirement: UserRequirement, attempt: int = 1) -> str:
        """生成单个歌词"""
        style_guidance = self._get_style_guidance(requirement.style)

        prompt = f"""
你是一位专业的中文歌词创作人。请根据用户需求创作一首歌词。

用户需求:
- 主题: {requirement.theme}
- 风格: {requirement.style}
- 情绪: {requirement.mood}
- 时长: {requirement.duration}秒
- 特殊要求: {', '.join(requirement.specific_requests) if requirement.specific_requests else '无'}

风格指导:
{style_guidance}

创作要求:
1. 歌词要有真实的情感表达，贴近主题
2. 语言要生动有力，有画面感
3. 节奏要符合{requirement.style}风格
4. 考虑到{requirement.duration}秒的时长，控制歌词长度
5. 避免使用过于复杂或生僻的词汇
6. 要有层次感，包含主歌、副歌等结构

请直接输出歌词内容，不要加其他说明:"""

        try:
            exchanges = [LLMExchange(role="user", content=prompt)]
            response = self.llm_client.chat_completion(exchanges)

            # 清理响应内容
            lyrics = self._clean_lyrics_response(response)

            if len(lyrics.strip()) < 20:
                raise ValueError("生成的歌词过短")

            return lyrics

        except Exception as e:
            raise Exception(f"LLM歌词生成失败: {e}")

    def _get_style_guidance(self, style: str) -> str:
        """获取风格指导"""
        style_guides = {
            "说唱": "节奏感强，韵脚明显，可以有一些街头文化元素，语言可以更直接有力",
            "流行": "朗朗上口，易于传唱，情感表达要真挚自然，有一定的流行元素",
            "摇滚": "有力量感，可以有一些叛逆或激情的元素，语言要有冲击力",
            "民谣": "质朴自然，有故事性，语言要温暖真实，贴近生活",
            "电子": "现代感强，可以有一些科技或未来元素，节奏要明快"
        }
        return style_guides.get(style, "保持音乐风格的特色，语言要有感染力")

    def _clean_lyrics_response(self, response: str) -> str:
        """清理LLM返回的歌词"""
        # 移除常见的标记和格式
        response = re.sub(r'^歌词[:：]?\\s*', '', response.strip())
        response = re.sub(r'^[【\\[].*?[】\\]]\\s*', '', response)
        response = re.sub(r'```.*?```', '', response, flags=re.DOTALL)

        return response.strip()

    def _review_with_user(self, candidates: List[LyricsVersion]) -> LyricsVersion:
        """用户确认歌词"""
        print("\\n📝 歌词创作完成！请查看以下版本:")

        for lyrics in candidates:
            print(f"\\n--- 版本 {lyrics.version} ---")
            print(lyrics.content)
            print("-" * 40)

        # 自动确认逻辑
        if len(candidates) == 1 and self.config.auto_approve_single_lyrics:
            selected = candidates[0]
            selected.approved = True
            self.session.selected_lyrics = selected
            print(f"\\n✅ 自动选择版本 {selected.version}")
            return selected

        # 用户选择
        retry_count = 0
        max_retries = self.config.max_lyrics_retries

        while retry_count < max_retries:
            choice = input(f"\\n请选择您喜欢的版本 (1-{len(candidates)})，或输入 'r' 重新生成: ").strip().lower()

            if choice == 'r':
                print(f"\\n🔄 正在重新生成歌词... (剩余重试次数: {max_retries - retry_count - 1})")
                try:
                    new_candidates = self._generate_lyrics_candidates()
                    return self._review_with_user(new_candidates)
                except Exception as e:
                    retry_count += 1
                    print(f"❌ 重新生成失败: {e}")
                    if retry_count >= max_retries:
                        print(f"💥 已达到最大重试次数 ({max_retries})，请从现有版本中选择")
                        break
                    continue

            try:
                version = int(choice)
                if 1 <= version <= len(candidates):
                    selected = candidates[version - 1]

                    # 询问是否需要修改
                    modify = input(f"\\n选择了版本 {version}。需要修改吗？(y/n): ").strip().lower()
                    if modify == 'y':
                        feedback = input("请描述您希望如何修改: ").strip()
                        selected.user_feedback = feedback

                        # 基于反馈修改歌词
                        try:
                            modified_lyrics = self._modify_lyrics_based_on_feedback(selected.content, feedback)
                            modified_version = self.session.add_lyrics_version(modified_lyrics)
                            modified_version.user_feedback = f"基于版本{version}修改: {feedback}"
                            selected = modified_version
                            print(f"\\n✏️  已生成修改版本 {selected.version}")
                        except Exception as e:
                            print(f"⚠️  修改失败: {e}")
                            print("使用原版本继续")

                    selected.approved = True
                    self.session.selected_lyrics = selected
                    print(f"\\n✅ 已确认选择版本 {selected.version}")
                    return selected
                else:
                    print(f"请输入 1-{len(candidates)} 之间的数字")
            except ValueError:
                print("请输入有效的选项")

        # 如果达到最大重试次数，强制选择第一个版本
        selected = candidates[0]
        selected.approved = True
        self.session.selected_lyrics = selected
        print(f"\\n⚠️  自动选择版本 {selected.version}")
        return selected

    def _modify_lyrics_based_on_feedback(self, original_lyrics: str, feedback: str) -> str:
        """基于用户反馈修改歌词"""
        prompt = f"""
用户对以下歌词提出了修改意见，请根据反馈进行调整：

原歌词:
{original_lyrics}

用户反馈:
{feedback}

请根据用户的反馈对歌词进行适当修改，保持歌词的整体结构和韵律，但要满足用户的要求。

修改后的歌词:"""

        try:
            exchanges = [LLMExchange(role="user", content=prompt)]
            response = self.llm_client.chat_completion(exchanges)
            modified = self._clean_lyrics_response(response)

            if len(modified.strip()) < 20:
                raise ValueError("修改后的歌词过短")

            return modified

        except Exception as e:
            raise Exception(f"歌词修改失败: {e}")

    def _build_generation_params(self, lyrics: LyricsVersion) -> GenerationParams:
        """构建音乐生成参数"""
        requirement = self.session.user_requirement
        if not requirement:
            raise ValueError("用户需求未收集")

        # 生成英文prompt
        english_prompt = self._generate_english_prompt(requirement)

        params = GenerationParams(
            prompt=english_prompt,
            lyrics=lyrics.content,
            audio_duration=requirement.duration,
            candidate_count=self.config.default_candidate_count
        )

        # 根据风格调整guidance_schedule
        params.guidance_schedule = self._adjust_guidance_schedule(requirement.style)

        self.session.add_debug_log(f"构建生成参数: prompt='{english_prompt[:50]}...', duration={requirement.duration}")
        return params

    def _generate_english_prompt(self, requirement: UserRequirement) -> str:
        """生成英文技术描述prompt"""
        style_prompts = {
            "说唱": "Rap, hip-hop, rhythmic, urban, strong beat",
            "流行": "Pop, mainstream, catchy, melodic, contemporary",
            "摇滚": "Rock, energetic, guitar-driven, powerful, dynamic",
            "民谣": "Folk, acoustic, natural, storytelling, gentle",
            "电子": "Electronic, synthesized, digital, modern, pulsing"
        }

        mood_prompts = {
            "悲伤": "melancholic, sad, emotional, slow tempo",
            "愤怒": "angry, aggressive, intense, heavy",
            "快乐": "happy, upbeat, joyful, lively",
            "温柔": "gentle, soft, warm, tender",
            "激昂": "energetic, passionate, powerful, uplifting",
            "忧郁": "melancholic, moody, introspective, dark",
            "浪漫": "romantic, loving, intimate, sweet",
            "怀旧": "nostalgic, reminiscent, wistful, vintage",
            "励志": "inspiring, motivational, uplifting, hopeful",
            "平静": "calm, peaceful, serene, relaxed"
        }

        style_desc = style_prompts.get(requirement.style, requirement.style)

        # 处理复合情绪（如："激昂, 励志"）
        mood_parts = []
        if requirement.mood:
            mood_keywords = [m.strip() for m in requirement.mood.split(',')]
            for mood in mood_keywords:
                english_mood = mood_prompts.get(mood.strip(), "")
                if english_mood:
                    mood_parts.append(english_mood)

        mood_desc = ", ".join(mood_parts) if mood_parts else "emotional"

        # 组合prompt
        prompt_parts = [style_desc, mood_desc, "Chinese male vocals", "clear vocals"]

        # 处理特殊要求 - 转换为英文
        if requirement.specific_requests:
            english_requests = self._translate_special_requests(requirement.specific_requests)
            prompt_parts.extend(english_requests)

        return ", ".join(prompt_parts)

    def _translate_special_requests(self, requests: List[str]) -> List[str]:
        """将中文特殊要求转换为英文"""
        translation_map = {
            "希望感情很厚重": "deep emotional, rich feeling, intense",
            "要有吉他solo": "guitar solo, guitar lead",
            "节奏要快一些": "fast tempo, upbeat rhythm",
            "节奏要慢一些": "slow tempo, gentle rhythm",
            "要有电子音效": "electronic effects, synthesizer",
            "声音要清澈": "clear vocals, crisp sound",
            "要有和声": "harmony, backing vocals",
            "要有说唱部分": "rap section, hip-hop elements"
        }

        english_requests = []
        for request in requests:
            # 直接映射
            if request in translation_map:
                english_requests.append(translation_map[request])
            # 关键词匹配
            elif "吉他" in request or "guitar" in request.lower():
                english_requests.append("guitar elements")
            elif "节奏快" in request or "快节奏" in request:
                english_requests.append("fast tempo")
            elif "节奏慢" in request or "慢节奏" in request:
                english_requests.append("slow tempo")
            elif "厚重" in request or "深沉" in request:
                english_requests.append("deep, rich")
            elif "清澈" in request or "清晰" in request:
                english_requests.append("clear, crisp")
            elif "电子" in request:
                english_requests.append("electronic")
            else:
                # 对于无法识别的要求，使用通用描述
                english_requests.append("expressive")

        return english_requests

    def _adjust_guidance_schedule(self, style: str) -> List[Dict[str, float]]:
        """根据风格调整guidance调度"""
        # 基础调度
        base_schedule = [
            {"position": 0.0, "scale": 10.0},
            {"position": 0.4, "scale": 16.0},
            {"position": 0.8, "scale": 12.0},
            {"position": 1.0, "scale": 8.0}
        ]

        # 根据风格微调
        if style == "说唱":
            # 说唱需要更强的节奏控制
            return [
                {"position": 0.0, "scale": 12.0},
                {"position": 0.3, "scale": 18.0},
                {"position": 0.7, "scale": 15.0},
                {"position": 1.0, "scale": 10.0}
            ]
        elif style == "摇滚":
            # 摇滚需要更强的动态变化
            return [
                {"position": 0.0, "scale": 8.0},
                {"position": 0.2, "scale": 20.0},
                {"position": 0.8, "scale": 16.0},
                {"position": 1.0, "scale": 6.0}
            ]

        return base_schedule

    def _prepare_lyrics_for_generation(self, lyrics: LyricsVersion) -> str:
        """为生成准备歌词（包括拼音标注等）"""
        if self.config.enable_pinyin_annotation:
            try:
                print("🔤 正在为歌词添加拼音标注...")

                # 获取多音字统计
                stats = get_polyphonic_stats(lyrics.content)
                if stats:
                    print(f"   发现 {len(stats)} 个多音字需要标注")
                    for char, positions in stats.items():
                        print(f"   - '{char}': {len(positions)}次")

                # 添加拼音标注
                annotated = annotate_polyphonic_lyrics(lyrics.content)
                lyrics.pinyin_annotated = annotated

                # 显示标注结果
                if annotated != lyrics.content:
                    print("✅ 拼音标注完成")
                    self.session.add_debug_log("已添加拼音标注")

                    # 询问用户是否查看标注结果
                    show_annotated = input("\\n是否查看标注后的歌词？(y/n): ").strip().lower()
                    if show_annotated == 'y':
                        print("\\n📝 标注后的歌词:")
                        print("-" * 40)
                        print(annotated)
                        print("-" * 40)

                        # 询问是否使用标注版本
                        use_annotated = input("\\n是否使用标注版本进行生成？(y/n): ").strip().lower()
                        if use_annotated == 'y':
                            self.session.add_debug_log("使用拼音标注版本")
                            return annotated
                        else:
                            self.session.add_debug_log("使用原始歌词版本")
                else:
                    print("ℹ️  未发现需要标注的多音字")

            except Exception as e:
                error_msg = f"拼音标注失败: {e}"
                self.session.add_debug_log(error_msg)
                print(f"⚠️  {error_msg}")

        return lyrics.content

    def _invoke_mcp(self, params: GenerationParams) -> MusicGenerationResult:
        """调用MCP服务生成音乐"""
        start_time = time.time()

        max_retries = self.config.max_generation_retries
        retry_count = 0

        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    print(f"\\n🔄 正在重试音乐生成... (第{retry_count}/{max_retries}次重试)")
                else:
                    print(f"\\n🎵 正在生成音乐...")

                print(f"参数: {params.prompt}")
                print(f"时长: {params.audio_duration}秒")
                print(f"候选数: {params.candidate_count}")

                # 调用MCP客户端 - 🔥 传递所有配置参数
                result = self.mcp_client.generate_music(
                    prompt=params.prompt,
                    lyrics=params.lyrics,
                    audio_duration=params.audio_duration,
                    candidate_count=params.candidate_count,
                    guidance_schedule=params.guidance_schedule,
                    lora_config=params.lora_config,  # 🔥 添加LoRA配置
                    cache_settings=params.cache_settings  # 🔥 添加缓存设置
                )

                generation_time = time.time() - start_time
                result.generation_time = generation_time

                if result.success:
                    print(f"\\n✅ 音乐生成成功！")
                    print(f"生成时间: {generation_time:.1f}秒")
                    print(f"输出文件: {', '.join(result.audio_paths)}")

                    # 记录成功的元数据
                    if result.metadata:
                        metadata = result.metadata
                        if metadata.get("cache_hit"):
                            print("🎯 缓存命中")

                        evaluation_scores = metadata.get("evaluation_scores", {})
                        if evaluation_scores:
                            overall_score = evaluation_scores.get("overall_score", 0)
                            print(f"⭐ 评估分数: {overall_score:.1f}/10.0")

                    return result
                else:
                    error_msg = result.error or "未知错误"
                    print(f"\\n❌ 音乐生成失败: {error_msg}")

                    if retry_count < max_retries:
                        print(f"将在3秒后重试...")
                        time.sleep(3)
                        retry_count += 1
                        continue
                    else:
                        print(f"💥 已达到最大重试次数 ({max_retries})")
                        generation_time = time.time() - start_time
                        result.generation_time = generation_time
                        return result

            except Exception as e:
                generation_time = time.time() - start_time
                error_msg = f"MCP调用异常: {str(e)}"
                print(f"\\n💥 {error_msg}")

                if retry_count < max_retries:
                    print(f"将在5秒后重试...")
                    time.sleep(5)
                    retry_count += 1
                    continue
                else:
                    print(f"💥 已达到最大重试次数 ({max_retries})")
                    self.session.add_debug_log(error_msg)

                    return MusicGenerationResult(
                        success=False,
                        error=error_msg,
                        session_id=self.session.session_id,
                        generation_time=generation_time
                    )

        # 这里不应该到达，但作为保险
        generation_time = time.time() - start_time
        return MusicGenerationResult(
            success=False,
            error="未知错误：重试循环异常退出",
            session_id=self.session.session_id,
            generation_time=generation_time
        )
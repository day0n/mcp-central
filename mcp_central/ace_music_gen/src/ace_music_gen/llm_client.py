"""LLM客户端模块，用于与大语言模型交互"""

import json
import requests
from typing import Dict


class LLMClient:
    """LLM API客户端"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        self.model = model or "qwen-turbo-latest"
    
    def setup_api(self, api_key: str):
        """设置API密钥"""
        self.api_key = api_key
    
    def generate_music_params(self, user_idea: str) -> Dict[str, str]:
        """生成音乐参数"""
        system_prompt = """你是一个专业的中文音乐创作AI助手，专门为ACE-Step音乐生成模型创作内容。

用户会告诉你他们想要什么样的音乐，你需要生成两个参数：

1. **prompt** (英文): 音乐风格技术描述，格式参考：
   - 伤感: "Rap, adult, male, emotional, melancholic, slow tempo, introspective"
   - 激昂: "Rap, energetic, powerful, fast tempo, aggressive, clear"  
   - 温柔: "Rap, soft, gentle, melodic, warm, acoustic elements"
   - 愤怒: "Rap, intense, angry, heavy bass, distorted, raw vocals"

2. **lyrics** (中文): 必须是纯中文说唱歌词，绝对不能包含任何英文，必须包含标准结构：
   - [Intro] - 中文开场
   - [Verse] - 中文主歌部分（1-2段）
   - [Chorus] - 中文副歌（重复性强，朗朗上口）
   - [Bridge] - 中文桥段（可选）
   - [Outro] - 中文结尾

歌词要求：
- 必须完全使用中文，不能有任何英文单词
- 符合用户描述的情感和风格
- 有深度和感染力，避免空洞
- 保持中文说唱的韵律感和押韵
- 每句歌词的最后一个字必须押韵，特别是副歌部分
- 注意韵脚的统一性，如：疼/行/声，或者强/光/王等
- 长度适中，不要过长

请严格按JSON格式返回：
{
    "prompt": "英文风格描述",
    "lyrics": "完整纯中文歌词"
}"""

        user_prompt = f"用户想法: {user_idea}\n\n请为这个想法生成合适的音乐内容。"
        
        return self._call_api(system_prompt, user_prompt)
    
    def generate_music_evaluation(self, evaluation_data: Dict) -> str:
        """生成音乐专业评价"""
        if not self.api_key:
            return "未配置API密钥，无法生成AI评价"
        
        eval_summary = self._build_evaluation_summary(evaluation_data)
        
        system_prompt = """你是一位资深的音乐制作人和音频工程师，拥有丰富的音乐制作和音频评估经验。

你的任务是根据提供的技术评分数据，生成一份专业的音乐评价报告。

评价要求：
1. 基于技术数据进行专业分析
2. 使用通俗易懂但专业的语言
3. 指出音乐的优点和不足
4. 提供具体的改进建议
5. 评价要客观、建设性
6. 长度控制在100-150字

请从音乐制作人的角度，给出专业而友好的评价。"""

        user_prompt = f"""请基于以下技术评分数据，对这首AI生成的音乐进行专业评价：

{eval_summary}

请生成一份专业的音乐评价，包含对音质、制作水平的分析和改进建议。"""

        return self._call_llm_for_evaluation(system_prompt, user_prompt)
    
    def _build_evaluation_summary(self, evaluation):
        """构建评估数据摘要"""
        summary = f"综合评分: {evaluation['overall_score']:.1f}/10.0\n"
        
        if 'analysis_info' in evaluation:
            info = evaluation['analysis_info']
            summary += f"音频时长: {info['duration']:.1f}秒\n"
            summary += f"采样率: {info['sample_rate']}Hz\n"
        
        if 'quality_scores' in evaluation:
            scores = evaluation['quality_scores']
            summary += "技术指标:\n"
            if 'dynamic_range' in scores:
                summary += f"- 动态范围: {scores['dynamic_range']:.1f}/10.0\n"
            if 'snr_estimate' in scores:
                summary += f"- 信噪比: {scores['snr_estimate']:.1f}/10.0\n"
            if 'frequency_balance' in scores:
                summary += f"- 频谱平衡: {scores['frequency_balance']:.1f}/10.0\n"
            if scores.get('pesq_score'):
                summary += f"- 感知质量(PESQ): {scores['pesq_score']:.1f}/4.5\n"
        
        return summary
    
    def _call_api(self, system_prompt: str, user_prompt: str) -> Dict[str, str]:
        """调用阿里云API"""
        if not self.api_key:
            return self._get_fallback_content(user_prompt)
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 1500
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # 尝试解析JSON
            try:
                music_content = json.loads(content.strip())
                if "prompt" in music_content and "lyrics" in music_content:
                    return music_content
            except json.JSONDecodeError:
                pass
            
            # 备用解析
            return self._parse_response(content)
                
        except Exception as e:
            print(f"API调用失败: {e}")
            return self._get_fallback_content(user_prompt)
    
    def _call_llm_for_evaluation(self, system_prompt: str, user_prompt: str) -> str:
        """调用LLM生成评价"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 300
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return content.strip()
            
        except Exception as e:
            return f"AI评价生成失败: {str(e)}"
    
    def _parse_response(self, content: str) -> Dict[str, str]:
        """简单的文本解析逻辑"""
        lines = content.split('\n')
        prompt = ""
        lyrics = ""
        
        in_lyrics = False
        
        for line in lines:
            line = line.strip()
            if 'prompt' in line.lower() and ':' in line:
                prompt = line.split(':', 1)[1].strip().strip('"{}')
            elif 'lyrics' in line.lower() and ':' in line:
                lyrics_start = line.split(':', 1)[1].strip().strip('"{}')
                lyrics = lyrics_start
                in_lyrics = True
            elif in_lyrics and line and not line.startswith('{') and not line.startswith('}'):
                lyrics += '\n' + line
        
        return {
            "prompt": prompt or "Rap, adult, male, spoken word, clear",
            "lyrics": lyrics or self._get_default_lyrics()
        }
    
    def _get_fallback_content(self, user_input: str) -> Dict[str, str]:
        """根据用户输入关键词判断风格的备用内容"""
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ['伤感', '悲伤', '难过', '失落']):
            return {
                "prompt": "Rap, adult, male, emotional, melancholic, slow tempo, introspective, clear vocals",
                "lyrics": """[Intro]
夜深了，思绪又开始泛滥
这些年的得失，在心里翻转

[Verse]
走过这么多路，回头看那些伤
有些痛不会忘，像刻在心上的疤
曾经以为时间会带走所有难过
现在才发现，有些记忆越久越深刻

[Chorus]
伤感不是软弱，是成长的代价
每一次跌倒，都让我更懂得珍惜
虽然心会痛，但我还在这里
用音乐诉说，那些说不出的话

[Outro]
伤感也是一种美
让我学会了更深的体会"""
            }
        elif any(word in user_lower for word in ['激昂', '热血', '激情', '燃']):
            return {
                "prompt": "Rap, energetic, powerful, fast tempo, aggressive, clear, motivational",
                "lyrics": """[Intro]
点燃心中的火焰
这一刻，全世界都听见我的声音

[Verse]
不服输的心永远年轻
每一次挑战都让我更加坚定
汗水是我最好的证明
成功的路上从不缺少拼搏的身影

[Chorus]
热血在沸腾，梦想在召唤
没有什么能阻挡我前进的步伐
燃烧吧青春，释放吧力量
这是属于我们的时代

[Outro]
永不熄灭的火
照亮前行的路"""
            }
        else:
            return {
                "prompt": "Rap, adult, male, spoken word, moderate tempo, clear, versatile",
                "lyrics": """[Intro]
这是我的声音，这是我的故事

[Verse]
生活就像一场说唱
有高有低，有快有慢
重要的是保持自己的节拍
在这个世界上留下属于自己的印记

[Chorus]
用音乐表达内心的想法
让每一个音符都有灵魂
这就是说唱的魅力
真实而有力量

[Outro]
音乐永不停息
我们的故事还在继续"""
            }
    
    def _get_default_lyrics(self) -> str:
        """默认歌词"""
        return """[Intro]
这是我的声音

[Verse]
用说唱诉说心声
每一个字都是真实的表达

[Chorus]
音乐就是我的语言
说出心里话

[Outro]
永不停息的节拍"""
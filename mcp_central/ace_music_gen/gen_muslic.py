#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import requests
import librosa
import numpy as np
from typing import Dict
from acestep.pipeline_ace_step import ACEStepPipeline
try:
    from pesq import pesq
    HAS_PESQ = True
except ImportError:
    HAS_PESQ = False
    print("PESQ library not available, will use simplified audio analysis")


class AudioEvaluator:
    """音频质量评估器"""
    
    def __init__(self):
        self.has_pesq = HAS_PESQ
    
    def evaluate_audio(self, audio_path: str) -> Dict:
        """
        评估音频文件质量
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            评估结果字典
        """
        try:
            # 使用librosa加载音频
            y, sr = librosa.load(audio_path, sr=None)
            
            # 基础音频特征分析
            audio_features = self._analyze_audio_features(y, sr)
            
            # 质量评估
            quality_scores = self._calculate_quality_scores(y, sr)
            
            # 生成综合评估
            overall_score = self._calculate_overall_score(audio_features, quality_scores)
            
            # 生成建议
            recommendations = self._generate_recommendations(audio_features, quality_scores)
            
            return {
                "overall_score": overall_score,
                "audio_features": audio_features,
                "quality_scores": quality_scores,
                "recommendations": recommendations,
                "analysis_info": {
                    "duration": len(y) / sr,
                    "sample_rate": sr,
                    "channels": 1 if y.ndim == 1 else y.shape[0]
                }
            }
            
        except Exception as e:
            return {
                "error": f"音频分析失败: {str(e)}",
                "overall_score": 0.0
            }
    
    def _analyze_audio_features(self, y, sr):
        """分析音频特征"""
        features = {}
        
        # 频谱质心 (音色亮度)
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        features['spectral_centroid_mean'] = np.mean(spectral_centroids)
        features['spectral_centroid_std'] = np.std(spectral_centroids)
        
        # RMS能量 (响度)
        rms = librosa.feature.rms(y=y)[0]
        features['rms_mean'] = np.mean(rms)
        features['rms_std'] = np.std(rms)
        
        # 零交叉率 (音频纯净度)
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        features['zcr_mean'] = np.mean(zcr)
        
        # MFCC特征 (音色特征)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        features['mfcc_mean'] = np.mean(mfccs, axis=1).tolist()
        
        # 频谱对比度
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        features['spectral_contrast_mean'] = np.mean(spectral_contrast)
        
        return features
    
    def _calculate_quality_scores(self, y, sr):
        """计算音频质量分数"""
        scores = {}
        
        # 动态范围
        dynamic_range = np.max(y) - np.min(y)
        scores['dynamic_range'] = min(dynamic_range * 10, 10.0)  # 归一化到0-10
        
        # 信噪比估算
        rms = librosa.feature.rms(y=y)[0]
        snr_estimate = 20 * np.log10(np.mean(rms) / (np.std(rms) + 1e-10))
        scores['snr_estimate'] = min(max(snr_estimate / 10, 0), 10.0)  # 归一化到0-10
        
        # 频谱平衡度
        freqs = np.abs(np.fft.fft(y))
        freq_balance = 1.0 - np.std(freqs) / (np.mean(freqs) + 1e-10)
        scores['frequency_balance'] = min(max(freq_balance * 10, 0), 10.0)
        
        # 如果有PESQ，计算感知质量
        if self.has_pesq and sr == 16000:  # PESQ需要16kHz采样率
            try:
                # 对于单通道音频，与自身比较作为参考
                pesq_score = pesq(sr, y, y, 'wb')  # 宽带模式
                scores['pesq_score'] = pesq_score
            except:
                scores['pesq_score'] = None
        else:
            scores['pesq_score'] = None
            
        return scores
    
    def _calculate_overall_score(self, features, scores):
        """计算综合评分"""
        total_score = 0
        count = 0
        
        # 动态范围权重: 30%
        if 'dynamic_range' in scores:
            total_score += scores['dynamic_range'] * 0.3
            count += 0.3
        
        # 信噪比权重: 25% 
        if 'snr_estimate' in scores:
            total_score += scores['snr_estimate'] * 0.25
            count += 0.25
            
        # 频谱平衡权重: 25%
        if 'frequency_balance' in scores:
            total_score += scores['frequency_balance'] * 0.25
            count += 0.25
            
        # PESQ分数权重: 20%
        if scores.get('pesq_score') is not None:
            pesq_normalized = min(scores['pesq_score'] / 4.5 * 10, 10.0)
            total_score += pesq_normalized * 0.2
            count += 0.2
            
        return total_score / count if count > 0 else 5.0
    
    def _generate_recommendations(self, features, scores):
        """生成改进建议"""
        recommendations = []
        
        # 动态范围建议
        if scores.get('dynamic_range', 5) < 3:
            recommendations.append("动态范围较小，建议增强音频的响度变化")
        elif scores.get('dynamic_range', 5) > 8:
            recommendations.append("动态范围很好，音频层次丰富")
            
        # 信噪比建议
        if scores.get('snr_estimate', 5) < 3:
            recommendations.append("音频可能存在噪声问题，建议降噪处理")
        elif scores.get('snr_estimate', 5) > 7:
            recommendations.append("音频信噪比良好，声音清晰")
            
        # 频谱平衡建议
        if scores.get('frequency_balance', 5) < 4:
            recommendations.append("频谱分布不够均衡，建议调整EQ")
        elif scores.get('frequency_balance', 5) > 7:
            recommendations.append("频谱分布均衡，音色自然")
            
        # PESQ建议
        if scores.get('pesq_score'):
            if scores['pesq_score'] < 2.0:
                recommendations.append("感知音质较低，建议检查音频编码质量")
            elif scores['pesq_score'] > 3.5:
                recommendations.append("感知音质优秀")
        
        if not recommendations:
            recommendations.append("音频质量整体良好")
            
        return recommendations


class SimpleACEMusicGen:
    def __init__(self):
        self.api_key = None
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        self.model = "qwen-turbo-latest"
        # 自动从网络下载模型，Mac设置bf16=False
        self.pipeline = ACEStepPipeline(bf16=False)
        # 初始化音频评估器
        self.audio_evaluator = AudioEvaluator()
        
    def setup_api(self, api_key: str):
        self.api_key = api_key
        
    def generate_and_create_music(self, user_idea: str):
        print("第一步：生成音乐参数...")
        
        # 获取音乐参数
        music_params = self._get_music_params(user_idea)
        
        print(f"生成的 Prompt: {music_params['prompt']}")
        print(f"生成的 Lyrics: {music_params['lyrics'][:100]}...")
        
        print("\n第二步：开始生成音乐...")
        
        # 调用ACE-Step生成音乐，下面是调参后适合说唱的参数
        result = self.pipeline(
            prompt=music_params['prompt'],
            lyrics=music_params['lyrics'],
            lora_name_or_path="ACE-Step/ACE-Step-v1-chinese-rap-LoRA",
            lora_weight=1.0,
            audio_duration=120,
            infer_step=60,
            guidance_scale=15,  
            scheduler_type="euler",
            cfg_type="apg", 
            omega_scale=10,
            guidance_interval=0.3,
            guidance_interval_decay=0,
            min_guidance_scale=3,  
            use_erg_tag=True,
            use_erg_lyric=False,
            use_erg_diffusion=True,
            guidance_scale_text=0,  
            guidance_scale_lyric=0  
        )
        
        # 第三步：音频质量评估
        print("\n第三步：分析音频质量...")
        audio_evaluation = self._evaluate_generated_audio(result)
        
        # 将评估结果和原始结果一起返回
        return {
            "ace_step_result": result,
            "audio_evaluation": audio_evaluation
        }
    
    def _evaluate_generated_audio(self, result):
        """评估生成的音频文件"""
        try:
            # 尝试从结果中获取音频文件路径
            audio_path = None
            
            if isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict) and 'audio_path' in result[0]:
                    audio_path = result[0]['audio_path']
            elif isinstance(result, dict) and 'audio_path' in result:
                audio_path = result['audio_path']
            
            # 如果没有找到路径，尝试查找outputs目录中最新的文件
            if not audio_path:
                import os
                import glob
                output_dir = "./outputs"
                if os.path.exists(output_dir):
                    wav_files = glob.glob(os.path.join(output_dir, "*.wav"))
                    if wav_files:
                        # 获取最新的wav文件
                        audio_path = max(wav_files, key=os.path.getctime)
            
            if audio_path and os.path.exists(audio_path):
                print(f"正在分析音频文件: {audio_path}")
                evaluation = self.audio_evaluator.evaluate_audio(audio_path)
                self._display_evaluation_results(evaluation)
                return evaluation
            else:
                print("未找到生成的音频文件，跳过质量评估")
                return {"error": "音频文件未找到"}
                
        except Exception as e:
            print(f"音频评估过程出错: {str(e)}")
            return {"error": f"评估失败: {str(e)}"}
    
    def _display_evaluation_results(self, evaluation):
        """显示评估结果"""
        if 'error' in evaluation:
            print(f"错误: {evaluation['error']}")
            return
            
        # 显示技术评分
        print(f"\n技术评分结果:")
        print(f"综合评分: {evaluation['overall_score']:.1f}/10.0")
        
        if 'analysis_info' in evaluation:
            info = evaluation['analysis_info']
            print(f"音频时长: {info['duration']:.1f}秒")
            print(f"采样率: {info['sample_rate']}Hz")
        
        if 'quality_scores' in evaluation:
            scores = evaluation['quality_scores']
            print(f"\n详细评分:")
            if 'dynamic_range' in scores:
                print(f"   动态范围: {scores['dynamic_range']:.1f}/10.0")
            if 'snr_estimate' in scores:
                print(f"   信噪比: {scores['snr_estimate']:.1f}/10.0")
            if 'frequency_balance' in scores:
                print(f"   频谱平衡: {scores['frequency_balance']:.1f}/10.0")
            if scores.get('pesq_score'):
                print(f"   感知质量: {scores['pesq_score']:.1f}/4.5")
        
        # 获取LLM专业评价
        print(f"\n正在生成AI专业评价...")
        llm_evaluation = self._get_llm_evaluation(evaluation)
        
        print(f"\nAI音乐评价:")
        print(f"{llm_evaluation}")
    
    def _get_llm_evaluation(self, evaluation):
        """使用LLM生成专业音乐评价"""
        if not self.api_key:
            return "未配置API密钥，无法生成AI评价"
        
        # 构建评估数据摘要
        eval_summary = self._build_evaluation_summary(evaluation)
        
        # 构建专业音乐评价提示词
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
    
    def _get_music_params(self, user_idea: str) -> Dict[str, str]:   
        # 构建系统提示
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

        # 构建用户提示  
        user_prompt = f"用户想法: {user_idea}\n\n请为这个想法生成合适的音乐内容。"
        
        return self._call_api(system_prompt, user_prompt)
    
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
    
    def _parse_response(self, content: str) -> Dict[str, str]:
        # 简单的文本解析逻辑
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
        # 根据用户输入关键词判断风格
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


def main():
    generator = SimpleACEMusicGen()
    generator.setup_api("sk-8f735e8d4a944cc7a0d00f9c2062fbde")
    
    print("告诉我你想要什么样的音乐，我会生成参数并直接创建音乐！")
    
    user_input = input("请描述你想要的音乐: ").strip()
    
    if user_input:
        try:
            print("\n" + "="*50)
            result = generator.generate_and_create_music(user_input)
            print(f"\n 音乐生成完成！")
            print(f"音频文件已保存到: ./outputs/ 目录")
            print("="*50 + "\n")
        except Exception as e:
            print(f"生成失败: {e}")
            print("="*50 + "\n")
    else:
        print("未输入音乐描述，程序退出")


if __name__ == "__main__":
    main()
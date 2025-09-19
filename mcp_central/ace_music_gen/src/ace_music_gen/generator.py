"""主要的音乐生成器模块"""

import os
import glob
import sys
from typing import Any, Dict, Optional

# ACE-Step库的导入
try:
    # 尝试从系统安装的ace-step包导入
    from acestep.pipeline_ace_step import ACEStepPipeline
except ImportError:
    try:
        # 尝试从父目录导入（当ace-step在同级目录时）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ace_step_path = os.path.join(current_dir, "..", "..", "..")
        ace_step_path = os.path.abspath(ace_step_path)
        
        if os.path.exists(os.path.join(ace_step_path, "acestep")):
            sys.path.insert(0, ace_step_path)
            from acestep.pipeline_ace_step import ACEStepPipeline
        else:
            raise ImportError("未找到ACE-Step库")
    except ImportError:
        # 如果无法导入，提供一个占位符
        class ACEStepPipeline:
            def __init__(self, **kwargs):
                print("ACEStepPipeline placeholder - 请确保ACE-Step库已正确安装")
                print("请参考README.md了解如何安装ACE-Step库")
            
            def __call__(self, **kwargs):
                return {"audio_path": None}

from .evaluator import AudioEvaluator
from .llm_client import LLMClient


class SimpleACEMusicGen:
    """简单的ACE音乐生成器"""
    
    def __init__(self):
        self.llm_client = LLMClient()
        # 自动从网络下载模型，Mac设置bf16=False
        self.pipeline = ACEStepPipeline(bf16=False)
        # 初始化音频评估器
        self.audio_evaluator = AudioEvaluator()
        # 默认的guidance调度曲线（可通过set_guidance_schedule覆盖）
        self.guidance_schedule = [
            {"position": 0.0, "scale": 10.0},
            {"position": 0.4, "scale": 16.0},
            {"position": 0.75, "scale": 12.0},
            {"position": 1.0, "scale": 9.0},
        ]
        self.candidate_count = 1
        self.audio_duration = 120
        self.enable_text_cache = True
        self.enable_lyric_cache = True
        
    def setup_api(self, api_key: str):
        """设置API密钥"""
        self.llm_client.setup_api(api_key)
        
    def set_guidance_schedule(self, schedule):
        """设置自定义guidance调度曲线"""
        self.guidance_schedule = schedule

    def generate_music_params(self, user_idea: str) -> Dict[str, str]:
        """单独生成歌词和Prompt，供多代理流程使用"""
        return self.llm_client.generate_music_params(user_idea)

    def set_candidate_count(self, count: int):
        """设置候选样本数量"""
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 1
        self.candidate_count = max(1, count)

    def set_audio_duration(self, duration):
        """设置目标音频时长（秒）"""
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = 120.0
        if duration <= 0:
            duration = 120.0
        self.audio_duration = duration

    def set_text_cache_enabled(self, enabled: bool):
        """开关文本Embedding缓存"""
        self.enable_text_cache = bool(enabled)

    def set_lyric_cache_enabled(self, enabled: bool):
        """开关歌词Token缓存"""
        self.enable_lyric_cache = bool(enabled)

    def generate_and_create_music(
        self,
        user_idea: str,
        guidance_schedule=None,
        music_params: Optional[Dict[str, str]] = None,
        candidate_count: Optional[int] = None,
        enable_text_cache: Optional[bool] = None,
        enable_lyric_cache: Optional[bool] = None,
        audio_duration: Optional[float] = None,
    ):
        """生成并创建音乐的完整流程"""
        print("第一步：生成音乐参数...")
        
        # 获取音乐参数
        if music_params is None:
            music_params = self.llm_client.generate_music_params(user_idea)
        
        print(f"生成的 Prompt: {music_params['prompt']}")
        print(f"生成的 Lyrics: {music_params['lyrics'][:100]}...")
        
        print("\n第二步：开始生成音乐...")
        active_guidance_schedule = guidance_schedule or self.guidance_schedule
        if active_guidance_schedule:
            print("使用Guidance调度曲线:")
            for node in active_guidance_schedule:
                position = None
                scale = None
                if isinstance(node, dict):
                    if "position" in node:
                        position = node["position"]
                    elif "progress" in node:
                        position = node["progress"]
                    elif "t" in node:
                        position = node["t"]

                    if "scale" in node:
                        scale = node["scale"]
                    elif "value" in node:
                        scale = node["value"]
                elif isinstance(node, (list, tuple)) and len(node) >= 2:
                    position, scale = node[0], node[1]

                try:
                    if position is not None:
                        position = float(position)
                    if scale is not None:
                        scale = float(scale)
                except (TypeError, ValueError):
                    position = None
                    scale = None

                if position is not None and scale is not None:
                    print(f"  - position={position:.2f}, scale={scale:.2f}")
                else:
                    print(f"  - {node}")

        candidate_reports = []

        def scoring_hook(audio_path=None, track_metadata=None, waveform=None, sample_rate=None, candidate_index=0):
            evaluation = None
            score = 0.0

            if audio_path and os.path.exists(audio_path):
                try:
                    evaluation = self.audio_evaluator.evaluate_audio(audio_path)
                    score = float(evaluation.get("overall_score", 0.0))
                except Exception as exc:
                    evaluation = {"error": f"评估失败: {exc}", "overall_score": 0.0}
                    score = 0.0
            else:
                evaluation = {"error": "音频文件未找到", "overall_score": 0.0}
                score = 0.0

            candidate_reports.append(
                {
                    "index": candidate_index,
                    "audio_path": audio_path,
                    "score": score,
                    "evaluation": evaluation,
                }
            )

            return {"score": score, "evaluation": evaluation}

        audio_duration = audio_duration or self.audio_duration
        pipeline_kwargs: Dict[str, Any] = {
            "prompt": music_params['prompt'],
            "lyrics": music_params['lyrics'],
            "lora_name_or_path": "ACE-Step/ACE-Step-v1-chinese-rap-LoRA",
            "lora_weight": 1.0,
            "audio_duration": audio_duration,
            "infer_step": 60,
            "guidance_scale": 15,
            "scheduler_type": "euler",
            "cfg_type": "apg",
            "omega_scale": 10,
            "guidance_interval": 0.3,
            "guidance_interval_decay": 0,
            "min_guidance_scale": 3,
            "use_erg_tag": True,
            "use_erg_lyric": False,
            "use_erg_diffusion": True,
            "guidance_scale_text": 0,
            "guidance_scale_lyric": 0,
            "return_dict": True,
            "guidance_schedule": active_guidance_schedule,
            "candidate_count": candidate_count or self.candidate_count,
            "scoring_hook": scoring_hook,
            "enable_text_cache": self.enable_text_cache if enable_text_cache is None else bool(enable_text_cache),
            "enable_lyric_cache": self.enable_lyric_cache if enable_lyric_cache is None else bool(enable_lyric_cache),
        }

        result = self.pipeline(**pipeline_kwargs)

        metadata = {}
        if isinstance(result, dict):
            metadata = result.get('metadata', {})

        candidate_scores_meta = metadata.get('candidate_scores', [])
        selected_index = metadata.get('selected_index')
        selected_audio_path = metadata.get('selected_audio_path')

        if candidate_scores_meta:
            print("\n候选结果评分：")
            for entry in candidate_scores_meta:
                idx = entry.get('index')
                score = entry.get('score')
                marker = '★' if idx == selected_index else ' '
                score_str = f"{score:.2f}" if isinstance(score, (int, float)) and score is not None else "N/A"
                print(f"  {marker} 候选 {idx}: 分数 {score_str} 音频: {entry.get('audio_path')}")

        selected_evaluation = None
        for report in candidate_reports:
            if report.get('index') == selected_index:
                selected_evaluation = report.get('evaluation')
                break

        cache_stats = metadata.get('cache_stats', {})
        if cache_stats:
            text_hits = cache_stats.get('text_hits', 0)
            text_total = text_hits + cache_stats.get('text_misses', 0)
            lyric_hits = cache_stats.get('lyric_hits', 0)
            lyric_total = lyric_hits + cache_stats.get('lyric_misses', 0)
            print(
                f"\n缓存统计：文本 {text_hits}/{text_total} 命中，歌词 {lyric_hits}/{lyric_total} 命中"
            )

        if not selected_audio_path:
            # 回退到原逻辑查找音频路径
            if isinstance(result, dict):
                paths = result.get('audio_paths') or []
                if paths:
                    selected_audio_path = paths[0]

        # 第三步：音频质量评估
        print("\n第三步：分析音频质量...")
        if selected_evaluation:
            self._display_evaluation_results(selected_evaluation)
            audio_evaluation = selected_evaluation
        else:
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
            evaluation_from_metadata = None
            metadata = {}
            
            if isinstance(result, dict):
                metadata = result.get('metadata', {})
                selected_audio_path = metadata.get('selected_audio_path')
                if selected_audio_path:
                    audio_path = selected_audio_path
                candidate_scores = metadata.get('candidate_scores', [])
                selected_index = metadata.get('selected_index')
                for candidate in candidate_scores:
                    if candidate.get('index') == selected_index:
                        details = candidate.get('details') or {}
                        possible_eval = details.get('evaluation')
                        if possible_eval:
                            evaluation_from_metadata = possible_eval
                        break
                if 'audio_paths' in result and result['audio_paths']:
                    # 取第一个有效音频路径
                    audio_candidates = [path for path in result['audio_paths'] if path]
                    if audio_candidates:
                        audio_path = audio_candidates[0]
                elif 'metadata' in result and isinstance(result['metadata'], dict):
                    tracks = result['metadata'].get('tracks', [])
                    for track in tracks:
                        path = track.get('audio_path')
                        if path:
                            audio_path = path
                            break
                elif 'audio_path' in result:
                    audio_path = result['audio_path']
            elif isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict) and 'audio_path' in result[0]:
                    audio_path = result[0]['audio_path']
            
            if evaluation_from_metadata:
                if audio_path:
                    print(f"使用缓存评估结果: {audio_path}")
                self._display_evaluation_results(evaluation_from_metadata)
                return evaluation_from_metadata

            # 如果没有找到路径，尝试查找outputs目录中最新的文件
            if not audio_path:
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
        llm_evaluation = self.llm_client.generate_music_evaluation(evaluation)
        
        print(f"\nAI音乐评价:")
        print(f"{llm_evaluation}")


def main():
    """主函数，用于命令行使用"""
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

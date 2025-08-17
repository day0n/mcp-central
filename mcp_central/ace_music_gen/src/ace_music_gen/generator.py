"""主要的音乐生成器模块"""

import os
import glob
import sys
from typing import Dict

# ACE-Step库的导入
try:
    # 尝试从系统安装的ace-step包导入
    from acestep.pipeline_ace_step import ACEStepPipeline
except ImportError:
    try:
        # 尝试从父目录导入（当ace-step在同级目录时）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ace_step_path = os.path.join(current_dir, "..", "..", "..", "..")
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
        
    def setup_api(self, api_key: str):
        """设置API密钥"""
        self.llm_client.setup_api(api_key)
        
    def generate_and_create_music(self, user_idea: str):
        """生成并创建音乐的完整流程"""
        print("第一步：生成音乐参数...")
        
        # 获取音乐参数
        music_params = self.llm_client.generate_music_params(user_idea)
        
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
    generator.setup_api("your key")
    
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
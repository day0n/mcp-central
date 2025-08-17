#!/usr/bin/env python3

from src.ace_music_gen import SimpleACEMusicGen

def main():
    # 创建生成器实例
    generator = SimpleACEMusicGen()
    
    # 设置API密钥
    generator.setup_api("your-key")
    
    
    # 示例：生成一首轻快的音乐
    user_idea = "生成一首轻快的流行音乐"
    
    try:
        print(f"正在生成音乐：{user_idea}")
        result = generator.generate_and_create_music(user_idea)
        
        print("\n生成完成！")
        print("结果已保存到 outputs/ 目录")
        
        if 'audio_evaluation' in result:
            evaluation = result['audio_evaluation']
            if 'overall_score' in evaluation:
                print(f"音频质量评分: {evaluation['overall_score']:.1f}/10.0")
                
    except Exception as e:
        print(f"生成失败: {str(e)}")


if __name__ == "__main__":
    main()
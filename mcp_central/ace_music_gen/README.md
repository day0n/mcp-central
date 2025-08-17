# ACE Music Generator

基于ACE-Step的音乐生成工具包

## 安装

首先安装ACE-Step库

```bash
git clone https://github.com/ACE-Studio/ACE-Step.git
cd ACE-Step
pip install -r requirements.txt
pip install -e .
```

然后安装本项目

```bash
cd ace_music_gen
uv sync
```

## 使用

运行程序

```bash
uv run python main.py
```

或者在代码中使用

```python
from src.ace_music_gen import SimpleACEMusicGen

generator = SimpleACEMusicGen()
generator.setup_api("your_api_key")
result = generator.generate_and_create_music("生成一首轻快的歌")
```

## 项目结构

```
ace_music_gen/
├── src/ace_music_gen/
│   ├── generator.py        # 音乐生成
│   ├── evaluator.py        # 音频评估
│   └── llm_client.py       # LLM客户端
└── main.py                 # 运行入口
```

## 配置

可以设置阿里云API密钥来生成更好的歌词

```python
generator.setup_api("your_dashscope_api_key")
```

## 依赖

- librosa
- numpy
- requests
- pesq

生成的音频文件保存在outputs目录下
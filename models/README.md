# models — 模型目录

放入 Qwen3-TTS-12Hz-1.7B-Base 及 Qwen3-TTS-Tokenizer-12Hz 文件夹。

目录结构示例：
```
models/
├── Qwen3-TTS-12Hz-1.7B-Base/      # 主模型（3.8 GB）
└── Qwen3-TTS-Tokenizer-12Hz/       # tokenizer（需从 modelscope 下载）
```

**下载 tokenizer：**
```bash
pip install modelscope
modelscope download --model Qwen/Qwen3-TTS-Tokenizer-12Hz --local_dir models/Qwen3-TTS-Tokenizer-12Hz
```

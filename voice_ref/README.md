# voice_ref — 参考音频目录

放一个 .wav / .mp3 / .m4a / .ogg / .flac 音频文件作为 TTS 声音克隆的参考。

程序会自动扫描首个找到的音频文件。

**同时需要在 `llm_config.ini` 的 `[tts]` 下配置 `ref_text`，填写该音频对应的文字内容。**

示例：`llm_config.ini`:
```ini
[tts]
enabled = true
model_path = models/Qwen3-TTS-12Hz-1.7B-Base
ref_text =  大家好呀！今天天气真不错，我要给大家介绍一个超厉害的新技术，快来听听吧！
language = Chinese
```

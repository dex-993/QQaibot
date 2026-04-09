# aibot

基于 **NoneBot2** + **NapCatQQ（OneBot v11）** 的 QQ 机器人，支持本地大模型和 OpenClaw Gateway 两种后端，提供私聊/群聊、多轮对话、图片理解和语音回复功能。

---

## 功能特性

- **双后端支持**：本地 OpenAI 兼容接口（LM Studio / Ollama / vLLM 等）或 OpenClaw Gateway
- **私聊 & 群聊**：私聊直接调用模型；群聊仅白名单群内 @ 机器人时响应
- **多轮对话**：内存中按用户/群维度保留上下文，支持按轮数/token/时间自动裁剪
- **图片理解**：发送图片给模型进行多模态理解（需 `backend=local` + 模型支持视觉）
- **语音回复（TTS）**：Qwen3-TTS 将文字合成为语音，支持语音克隆；超时/失败自动降级为文字
- **引用上下文**：引用他人消息时，将发送者和原文一并提交给模型
- **人设记忆**：启动时自动加载 `人设/soul.md` 和 `人设/agent.md` 拼入 system prompt
- **错误守卫**：自动拦截模型复述 HTTP/接口错误文案的回复，避免向用户暴露错误堆栈

## 架构

```
QQ 客户端 ←→ NapCatQQ ←→ NoneBot2（aibot）←→ 本地模型 / OpenClaw Gateway
                    ↑
              OneBot v11 正向 WebSocket
```

## 前置要求

- **Python** 3.10+
- **NapCatQQ**：已安装运行，开启 **OneBot 11 正向 WebSocket**
- **大模型服务**（二选一）：
  - **local**：任意提供 `/v1/chat/completions` 的服务（如 LM Studio、Ollama、vLLM）
  - **openclaw**：OpenClaw Gateway 已启用 `POST /v1/responses`，见 [OpenResponses API 文档](https://docs.openclaw.ai/zh-CN/gateway/openresponses-http-api)
- **TTS（可选）**：[Qwen3-TTS-12Hz-1.7B-Base](https://modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-Base) 及 [Qwen3-TTS-Tokenizer-12Hz](https://modelscope.cn/models/Qwen/Qwen3-TTS-Tokenizer-12Hz)

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd aibot
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
pip install -e .
```

### 3. 配置

复制模板文件：

```bash
copy .env.example .env
copy llm_config.example.ini llm_config.ini
copy group_whitelist.example.ini group_whitelist.ini
```

按需编辑：

- `.env`：NapCat 连接地址（默认 `ws://127.0.0.1:18881`）
- `llm_config.ini`：大模型后端、人设、多轮参数、TTS 配置
- `group_whitelist.ini`：允许机器人响应的群号列表

> 配置文件含密钥和个人信息，**勿将 `llm_config.ini` / `group_whitelist.ini` 提交到公开仓库**（`.gitignore` 已忽略）。

### 4. 启动

启动顺序：**先启动 NapCat** → **再启动大模型服务**（若用 local 后端）→ **运行机器人**：

```bash
python bot.py
```

日志出现 `Uvicorn running on http://127.0.0.1:18080` 和 `OneBot V11 … connected` 表示连接成功。

详细配置说明见 **[USAGE.md](USAGE.md)**。

## 项目结构

| 路径 | 说明 |
|------|------|
| `bot.py` | 入口：加载环境变量、注册适配器、加载插件、启动检查 |
| `openclaw_memory.py` | 启动时读取人设目录（`人设/`）的 soul.md / agent.md |
| `plugins/echo/` | 核心插件：消息处理、白名单、历史、LLM 调用、TTS |
| `llm_config.ini` | 大模型后端与多轮对话配置（含敏感信息，勿上传） |
| `group_whitelist.ini` | 群聊白名单（勿上传） |
| `.env` | NapCat 连接与本机 HTTP 端口配置 |
| `人设/` | 人设文件：soul.md（身份）、agent.md（行为约束） |
| `voice_ref/` | TTS 语音克隆参考音频（勿上传） |
| `models/` | Qwen3-TTS 模型文件（勿上传） |
| `scripts/test_onebot_ws.py` | NapCat WebSocket 连接诊断工具 |

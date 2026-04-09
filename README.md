# aibot - QQ 机器人

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
- **错误守卫**：自动拦截模型复述 HTTP/接口错误文案的回复

---

## 架构

```
QQ 客户端 ←→ NapCatQQ ←→ NoneBot2（aibot）←→ 本地模型 / OpenClaw Gateway
                    ↑
              OneBot v11 正向 WebSocket
```

---

## 前置要求

- **Python** 3.10+
- **NapCatQQ**：已安装运行，开启 **OneBot 11 正向 WebSocket**
- **大模型服务**（二选一）：
  - **local**：任意提供 `/v1/chat/completions` 的服务（LM Studio、Ollama、vLLM 等）
  - **openclaw**：OpenClaw Gateway 已启用 `POST /v1/responses`，见 [OpenResponses API 文档](https://docs.openclaw.ai/zh-CN/gateway/openresponses-http-api)
- **TTS（可选）**：[Qwen3-TTS-12Hz-1.7B-Base](https://modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-Base) 及 [Qwen3-TTS-Tokenizer-12Hz](https://modelscope.cn/models/Qwen/Qwen3-TTS-Tokenizer-12Hz)

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/dex-993/aibot.git
cd aibot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### 2. 配置

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

### 3. 启动顺序

```
第一步：启动 NapCat（确保 QQ 已登录，OneBot 正向 WebSocket 已开启）
第二步：启动大模型服务（若用 backend=local）
第三步：运行机器人
```

```bash
python bot.py
```

日志出现 `Uvicorn running on http://127.0.0.1:18080` 和 `OneBot V11 … connected` 表示连接成功。

---

## 配置详解

### `.env`（环境变量 / NapCat 连接）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DRIVER` | `~fastapi+~websockets` | 固定值。 |
| `ONEBOT_WS_URLS` | `["ws://127.0.0.1:18881"]` | NapCat 正向 WebSocket 地址。 |
| `ONEBOT_ACCESS_TOKEN` | （空） | 若 NapCat 启用了 token，在此填写相同值。 |
| `HOST` | `127.0.0.1` | 本机 HTTP 监听地址。 |
| `PORT` | `18080` | 本机 HTTP 端口（WinError 10048 时改此处）。 |

### `group_whitelist.ini`（群聊白名单）

```ini
[groups]
123456789 = 1
```

- 仅白名单内的群才会响应；格式为 `群号 = 1`
- 修改后**无需重启**即可生效

### `llm_config.ini`（大模型配置）

#### `[llm]` — 通用

| 项 | 默认值 | 说明 |
|----|--------|------|
| `backend` | `local` | `local`（OpenAI 兼容）或 `openclaw`（OpenClaw Gateway） |
| `history_enable` | `true` | 启用多轮对话（内存，非持久化） |
| `history_max_rounds` | `10` | 每会话最多保留的「用户 + 助手」轮次 |
| `history_max_tokens` | `4000` | 历史 token 上限（按字符数 ÷ 4 粗估） |
| `history_ttl_seconds` | `1800` | 会话闲置秒数后清空；`0` = 不按时间清空 |
| `龙虾记忆` | `true` | 仅 `backend=local` 时生效：读取 `人设/soul.md` 和 `人设/agent.md` 拼入 system prompt |
| `group_empty_at_replies` | （5 条） | 仅 @、无正文/图/引用时随机发送的文案；逗号分隔 |

#### `[local]` — 本地模型（LM Studio / Ollama / vLLM）

| 项 | 说明 |
|----|------|
| `base_url` | 服务根地址（如 `http://127.0.0.1:1234/v1`） |
| `api_key` | API 密钥，多数本地服务可填占位值 |
| `model` | 模型 ID，须与服务端注册的名称一致 |
| `supports_vision` | `true`/`false`：是否启用图片理解（需模型支持多模态） |
| `system_prompt` | 系统提示词（人设） |
| `timeout_seconds` | 请求超时秒数（默认 120） |

> **图片理解**：发送顺序为文字在前、图片在后（适配 LM Studio / Qwen Jinja 模板）。多轮中仅最后一条 user 消息保留图片，早期带图轮次会压成纯文字。单条最多 **6 张** 图片。

#### `[openclaw]` — OpenClaw Gateway

| 项 | 说明 |
|----|------|
| `base_url` | Gateway 根地址（如 `http://127.0.0.1:18790`）；不要写 `/v1` |
| `token` | 与 Gateway 认证一致的 token；勿泄露 |
| `subagent_id` | 推荐：子智能体 ID，优先于 `agent_id` |
| `agent_id` | 未配置 `subagent_id` 时使用；二者至少填其一 |
| `instructions` | 随请求传入的系统侧说明 |
| `group_instructions_suffix` | 群聊时在 `instructions` 后追加的内容；描述群聊中的身份与行为规范 |
| `private_allow_qq` | `backend=openclaw` 时允许私聊的 QQ 白名单（逗号分隔）；群聊不受限 |
| `timeout_seconds` | HTTP 请求超时秒数（默认 120） |

> **启用 OpenResponses**：编辑 OpenClaw 配置文件（`~/.openclaw/openclaw.json`），在 `gateway` 下添加：
> ```json
> "http": { "endpoints": { "responses": { "enabled": true } } }
> ```
> 保存后重启 OpenClaw Gateway。

#### `[tts]` — 语音合成（TTS 仅 `backend=local` 时可用）

| 项 | 默认值 | 说明 |
|----|--------|------|
| `enabled` | `true` | 是否启用 TTS |
| `model_path` | `models/Qwen3-TTS-12Hz-1.7B-Base` | Qwen3-TTS 模型路径（必填） |
| `ref_audio` | （空） | 语音克隆参考音频（`.wav/.mp3/.m4a/.ogg/.flac`）；留空使用默认音色 |
| `ref_text` | （空） | `ref_audio` 对应的文字（必填，否则无法克隆） |
| `language` | `Chinese` | 合成语种 |
| `max_duration_seconds` | `60` | 语音最大时长；超出降级为文字。QQ 单条语音上限 60 秒 |
| `prefer_voice` | `true` | `true` = 优先发语音，超时改文字；`false` = 只发文字 |

---

## TTS 模型下载

TTS 为可选功能，不安装则只发文字回复。

### 模型文件 1：Qwen3-TTS Base（约 3.6 GB）

从 [ModelScope](https://modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-Base) 下载，文件夹放入 `models/`，最终路径：

```
E:\aibot\models\Qwen3-TTS-12Hz-1.7B-Base\
```

### 模型文件 2：Qwen3-TTS Tokenizer（几百 MB）

```bash
pip install modelscope
modelscope download --model Qwen/Qwen3-TTS-Tokenizer-12Hz --local_dir E:\aibot\models\Qwen3-TTS-Tokenizer-12Hz
```

### 语音克隆参考音频（可选）

准备 5~30 秒清晰人声录音（.wav/.mp3），放入 `voice_ref/` 目录，在 `[tts]` 中配置 `ref_audio` 路径和对应的 `ref_text`。

> **禁止将含你声音的音频提交到 GitHub**

---

## 使用方式

### 私聊

- 直接发送文字即可调用模型（过长会提示缩短）
- **`backend=openclaw`**：仅 `private_allow_qq` 名单内的 QQ 会收到回复；其余静默
- **`backend=local`**：无 QQ 白名单限制

### 群聊

- 必须同时满足：**群号在白名单** 且 **@ 当前机器人** 且 **有文字或图片**
- 引用机器人自己发出的消息，等同于 @ 机器人
- 仅 @ 无正文，收到随机一条提示语（由 `group_empty_at_replies` 配置）

### 指令

| 场景 | 指令 | 效果 |
|------|------|------|
| 私聊 | `/清空` 或 `/clear` | 清空自己的私聊多轮桶 |
| 群内（需 @） | `/清空` 或 `/clear` | 清空自己在该群的多轮桶 |
| 私聊 | `/清空全部记忆` | 仅 `memory_clear_master_qq` 中的 QQ 可用：清空所有记忆桶 |

### 戳一戳

- 戳机器人收到「别戳啦～看到啦！」

---

## 常见问题

### 端口被占用（WinError 10048）

```bash
netstat -ano | findstr :18080
taskkill /PID <PID> /F
```
或修改 `.env` 中的 `PORT`。

### 群聊无回复

- [ ] 群号已写入 `group_whitelist.ini`
- [ ] 确认 @ 的是**本机器人**，且 @ 后有文字
- [ ] 本地模型：确认 LM Studio/Ollama 服务已启动
- [ ] 日志有 `OneBot V11 … connected`

### NapCat 连接失败

```bash
python scripts/test_onebot_ws.py
```

### 本地模型连接失败

```bash
curl http://127.0.0.1:1234/v1/models
```
确认防火墙未拦截，`base_url` 末尾 `/v1` 不要多写。

### TTS 报「页面文件太小」

显存不足，修改 `plugins/echo/tts.py` 中的 `device = "cuda:0"` 改为 `"cpu"`（会慢但不占显存）。

### TTS 报「SoX could not be found」

从 https://sox.sourceforge.net 下载并加入 PATH；不影响 WAV 生成，但 Silk 格式转换会失败。

---

## 项目结构

```
aibot/
├── bot.py                          # 入口
├── openclaw_memory.py             # 人设记忆加载
├── pyproject.toml                 # 包元数据
├── requirements.txt               # 依赖列表
├── .env.example                   # 环境变量模板
├── llm_config.example.ini         # 大模型配置模板
├── group_whitelist.example.ini     # 群白名单模板
├── plugins/echo/
│   ├── __init__.py                # 消息处理器（私聊/群聊/戳一戳）
│   ├── llm_reply.py               # LLM 调用（local / openclaw 双后端）
│   ├── llm_ini.py                 # 读取 llm_config.ini
│   ├── chat_history.py            # 多轮对话内存管理
│   ├── whitelist.py               # 群白名单加载
│   ├── message_image.py           # 图片解析与压缩
│   ├── quoted_context.py          # 引用消息上下文
│   ├── reply_error_echo_guard.py # 拦截 API 错误复述
│   └── tts.py                     # Qwen3-TTS 语音合成
├── 人设/
│   ├── soul.md                    # 身份人设
│   └── agent.md                   # 行为约束
├── voice_ref/                     # TTS 语音克隆参考音频（勿上传）
├── models/                        # Qwen3-TTS 模型文件（勿上传主模型）
├── scripts/
│   └── test_onebot_ws.py          # NapCat WS 连接诊断工具
├── tests/
│   └── test_reply_error_echo_guard.py
└── logs/
    └── bot.log                    # 运行日志（自动生成）
```

---

## 安全与合规

- **勿**将含 token、QQ 号、群号的配置文件提交到公开仓库；`.gitignore` 已忽略 `llm_config.ini` 和 `group_whitelist.ini`
- 使用非官方 QQ 协议存在**封号与合规风险**，请自行评估
- TTS 参考音频含个人声音特征，勿提交 `voice_ref/` 中的音频文件
- models 目录仅含 Tokenizer 和配置文件；主模型（约 3.6 GB）需自行下载

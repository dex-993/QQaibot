# aibot 使用说明

完整文档。快速开始请看 [README.md](README.md)。

---

## 1. 架构与数据流

```
QQ 客户端 ←→ NapCatQQ ←→ NoneBot2（aibot）←→ 本地模型 / OpenClaw Gateway
                    ↑
              OneBot v11 正向 WebSocket
```

- **NapCat**：登录 QQ，提供 **OneBot v11 正向 WebSocket** 服务。
- **NoneBot2**：作为 **WebSocket 客户端** 连接 NapCat；处理消息后调用大模型。
- **大模型**：由 `llm_config.ini` 选择 `local`（OpenAI 兼容）或 `openclaw`（OpenClaw Gateway）。

---

## 2. 环境要求

- **Python** 3.10+
- **NapCatQQ**：已安装、可登录 QQ，并开启 **OneBot 11 正向 WebSocket**（记下 `ws://` 地址与可选 token）。
- **大模型服务**（按所选后端）：

  | 后端 | 要求 |
  |------|------|
  | `local` | 任意提供 **`/v1/chat/completions`** 的兼容服务（如 Ollama、LM Studio、vLLM）。图片理解需模型支持多模态。 |
  | `openclaw` | OpenClaw **Gateway** 已启用 **`POST /v1/responses`**（OpenResponses），见 [官方文档](https://docs.openclaw.ai/zh-CN/gateway/openresponses-http-api)。 |

- **TTS（可选）**：
  - [Qwen3-TTS-12Hz-1.7B-Base](https://modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-Base)（约 3.8 GB）
  - [Qwen3-TTS-Tokenizer-12Hz](https://modelscope.cn/models/Qwen/Qwen3-TTS-Tokenizer-12Hz)

---

## 3. 安装

在项目根目录执行：

```bash
cd E:\aibot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

> 依赖与 `pyproject.toml` 一致。`pip install -e .` 以可编辑模式安装，便于开发调试。

### 配置文件

```bash
copy .env.example .env
copy llm_config.example.ini llm_config.ini
copy group_whitelist.example.ini group_whitelist.ini
```

> `llm_config.ini` 和 `group_whitelist.ini` 含密钥、个人 QQ/群号等敏感信息，默认已加入 `.gitignore`，**勿提交到公开仓库**。

---

## 4. 配置文件详解

### 4.1 `.env`（环境变量 / NapCat 连接）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DRIVER` | `~fastapi+~websockets` | 固定值，启用 WebSocket 客户端支持。 |
| `ONEBOT_WS_URLS` | `["ws://127.0.0.1:18881"]` | NapCat 正向 WebSocket 地址，须与 NapCat 面板配置一致。 |
| `ONEBOT_ACCESS_TOKEN` | （空） | 若 NapCat 启用了 access token，在此填写相同值。 |
| `HOST` | `127.0.0.1` | 本机 HTTP 服务监听地址。 |
| `PORT` | `18080` | 本机 HTTP 服务端口（与 NapCat WS 无关）。**WinError 10048** 时改此处。 |
| `GROUP_WHITELIST_INI` | `group_whitelist.ini` | 可选，覆盖群白名单 INI 路径。 |
| `LLM_CONFIG_INI` | `llm_config.ini` | 可选，覆盖大模型配置 INI 路径。 |

#### 端口被占用（WinError 10048）

```bash
# 查找占用端口的进程
netstat -ano | findstr :18080
# 结束进程（替换 <PID>）
taskkill /PID <PID> /F
```

或直接改 `.env` 中的 `PORT`。

---

### 4.2 `group_whitelist.ini`（群聊白名单）

```ini
[groups]
# 仅下列群号内，且 @ 机器人才会回复。
# 格式：群号 = 1（等号右侧仅占位，无实际意义）
123456789 = 1
```

- 每个群独占一行，格式为 `群号 = 1`。
- **只有**白名单内的群，机器人才会处理群消息。
- 修改后一般**无需重启**即可生效。

---

### 4.3 `llm_config.ini`（大模型配置）

#### `[llm]` — 通用配置

| 项 | 默认值 | 说明 |
|----|--------|------|
| `backend` | `local` | 大模型后端：`local`（OpenAI 兼容）或 `openclaw`（OpenClaw Gateway）。 |
| `history_enable` | `true` | 是否启用多轮对话（内存，非持久化）。 |
| `history_max_rounds` | `10` | 每会话最多保留多少对「用户 + 助手」轮次，超出从最早一轮裁剪。 |
| `history_max_tokens` | `4000` | 历史总 token 上限（按字符数 ÷ 4 粗估），与 `max_rounds` 同时生效。 |
| `history_ttl_seconds` | `1800` | 会话闲置秒数后清空该桶；`0` = 不按时间清空。 |
| `memory_clear_master_qq` | （空） | 可执行「/清空全部记忆」的 QQ 列表（逗号分隔）；留空关闭该指令。 |
| `龙虾记忆` | `true` | **仅 `backend=local` 时生效**：启动时读取 `人设/soul.md` 和 `人设/agent.md` 拼入 system prompt。 |
| `openclaw_workspace_path` | （空） | 人设根目录；留空默认使用项目内 `人设/`。可填绝对路径。 |
| `openclaw_workspace_max_chars` | `32000` | 人设正文总字符上限，超出截断。 |
| `group_empty_at_replies` | （5 条默认回复） | 群内仅 @、无正文/无图/无引用时随机发送的文案；英文逗号分隔。 |

#### `[local]` — OpenAI 兼容后端

| 项 | 说明 |
|----|------|
| `base_url` | 服务根地址（如 `http://127.0.0.1:1234/v1`），程序会自动补全 `/v1`。 |
| `api_key` | API 密钥，多数本地服务可填占位值。 |
| `model` | 模型 ID，须与服务端注册的名称一致。 |
| `supports_vision` | `true`/`false`：是否启用图片理解（需模型支持多模态）。 |
| `vision_max_long_edge` | 转 JPEG 前将最长边缩到此像素（默认 1280）；`0` = 不限制。 |
| `vision_max_image_bytes` | 单张 JPEG 目标字节上限；超出继续缩小/降质量；`0` = 不限制。 |
| `vision_jpeg_quality` | JPEG 质量 `1`–`100`（默认 `85`）。 |
| `system_prompt` | 系统提示词（人设）；启用「龙虾记忆」时会在其后附加 soul.md / agent.md。 |
| `timeout_seconds` | 请求超时秒数（默认 120）。 |

**图片理解说明**：
- 发送顺序：文字在前、图片在后（适配 LM Studio / Qwen Jinja 模板）。
- 多轮对话中仅**最后一条** user 消息保留图片，早期带图轮次会压成纯文字。
- 单条消息最多 **6 张** 图片。
- 若 `supports_vision=false` 且消息只有图片，机器人**不回复**。

#### `[openclaw]` — OpenClaw Gateway 后端

| 项 | 说明 |
|----|------|
| `base_url` | Gateway 根地址（如 `http://127.0.0.1:18790`）；**不要**写 `/v1` 或 `/v1/responses`。 |
| `token` | 与 Gateway 认证一致（`OPENCLAW_GATEWAY_TOKEN`）；勿泄露。 |
| `subagent_id` | **推荐**：子智能体 ID，优先于 `agent_id`。 |
| `agent_id` | 未配置 `subagent_id` 时使用；二者至少填其一。 |
| `model` | 可留空则为 `openclaw`；或 `openclaw/<agentId>` 格式；**不要**写 `openclaw:xxx`（冒号无效）。 |
| `supports_vision` | 预留，当前 OpenClaw 路径仅处理文字。默认 `false`。 |
| `instructions` | 随请求传入的系统侧说明。 |
| `private_allow_qq` | `backend=openclaw` 时允许私聊走 Gateway 的 QQ 白名单；不在名单则静默。群聊不受限制。 |
| `timeout_seconds` | CLI 超时秒数（默认 120）。 |

#### `[tts]` — 语音合成

| 项 | 默认值 | 说明 |
|----|--------|------|
| `enabled` | `true` | 是否启用 TTS；`false` 则只发文字。 |
| `model_path` | `models/Qwen3-TTS-12Hz-1.7B-Base` | Qwen3-TTS 模型路径（必填）。 |
| `tokenizer_path` | （空） | Tokenizer 路径（若与 model_path 同目录可不填）。 |
| `ref_audio` | （空） | 语音克隆参考音频路径（`.wav/.mp3/.m4a/.ogg/.flac`）；留空使用默认音色。 |
| `ref_text` | （空） | `ref_audio` 对应的文字（必填，否则无法克隆）。 |
| `language` | `Chinese` | 合成语种；留空自动检测。 |
| `max_duration_seconds` | `60` | 语音最大时长；超出则降级为文字。QQ 单条语音上限 60 秒。 |
| `prefer_voice` | `true` | `true` = 优先发语音，超时改文字；`false` = 只发文字。 |

> **TTS 仅 `backend=local` 时可用**，`backend=openclaw` 时自动跳过。

---

## 5. 启动顺序

```
1. 启动 NapCat，确认 QQ 在线、正向 WebSocket 端口正确
2. 启动大模型服务（若用 backend=local）
3. 运行机器人
```

```bash
python bot.py
```

成功标志：
- `Uvicorn running on http://127.0.0.1:18080`
- `OneBot V11 … connected`

---

## 6. 使用方式

### 6.1 私聊

- 直接发送文字即可调用模型（过长会提示缩短）。
- **`backend=openclaw`**：仅 `private_allow_qq` 名单内的 QQ 会收到回复；其余静默。
- **`backend=local`**：无 QQ 白名单限制。

### 6.2 群聊

- **必须同时满足**：群号在白名单 **且** @ 当前机器人（消息中任意位置出现 `at` 段均可）**且** 有文字或图片。
- **引用回复**：引用机器人自己发出的消息，等同于 @ 机器人。
- **仅 @ 无正文**：收到随机一条「空 @ 回复」或默认提示语。

### 6.3 戳一戳

- 戳机器人会触发回复「别戳啦～看到啦！」。
- 群内戳需该群在白名单；私聊戳需在 `private_allow_qq` 名单（`backend=openclaw` 时）。

### 6.4 指令

| 场景 | 指令 | 效果 |
|------|------|------|
| 私聊 | `/清空` 或 `/clear` | 清空自己的私聊多轮桶。 |
| 群内（需 @ 机器人） | `/清空` 或 `/clear` | 清空自己在该群的多轮桶。 |
| 私聊 | `/清空全部记忆` | 仅 `memory_clear_master_qq` 中的 QQ 可用：清空所有用户/群的记忆桶。 |

---

## 7. 多轮对话说明

- **会话键**：私聊 `priv:<QQ>`；群聊 `grp:<群号>:<QQ>`（同群不同用户互不串上下文）。
- **裁剪策略**：`history_max_rounds`（按轮数）+ `history_max_tokens`（按 token 估算）+ `history_ttl_seconds`（按时间）三重限制，先触顶者为准。
- **重启 `python bot.py` 会清空所有内存历史**（未使用数据库）。
- **龙 Claudio 记忆**（`backend=local` + `龙虾记忆=true`）：启动时读取 `人设/soul.md` 和 `人设/agent.md` 拼入 system prompt；若 `backend=openclaw`，龙虾记忆不生效（由 Gateway 侧管理）。

---

## 8. 常见问题

### 8.1 端口被占用（WinError 10048）

修改 `.env` 中的 `PORT`，或结束占用进程：

```bash
netstat -ano | findstr :18080
taskkill /PID <PID> /F
```

### 8.2 群聊无回复

- [ ] 群号已写入 `group_whitelist.ini` 的 `[groups]`。
- [ ] 确认 @ 的是**本机器人**，且 @ 后有文字（仅 @ 无字收到的是空 @ 回复，不是无响应）。
- [ ] 本地模型：确认服务已启动，`base_url` 和 `model` 正确。
- [ ] NapCat 正向 WebSocket 已连接（日志有 `OneBot V11 … connected`）。

### 8.3 本地模型连接失败

```bash
# 测试服务是否可达
curl http://127.0.0.1:1234/v1/models
```

- 确认防火墙未拦截。
- `base_url` 末尾 `/v1` 会自动补全，但不要多写。

### 8.4 OpenClaw 报错

#### 启用 OpenResponses

1. 编辑 OpenClaw 主配置（Windows 通常在 `C:\Users\<用户名>\.openclaw\openclaw.json`）。
2. 在 `gateway` 下添加：

```json
{
  "gateway": {
    "http": {
      "endpoints": {
        "responses": {
          "enabled": true
        }
      }
    }
  }
}
```

3. 保存并重启 OpenClaw Gateway。
4. 测试连通性：

```bash
curl -X POST http://127.0.0.1:18790/v1/responses \
  -H "Authorization: Bearer <你的token>" \
  -H "Content-Type: application/json" \
  -d '{"model":"openclaw","input":"hi"}'
```

#### 常见 HTTP 错误

- **502 Bad Gateway**：网关后上游（模型/API）不可用、未启用 OpenResponses、或智能体配置有误。检查 Gateway 日志。
- **404 Not Found**：`base_url` 末尾误加了 `/v1/responses`，程序会自动追加导致重复路径。
- **`Unknown agent id`**：在 OpenClaw 中运行 `openclaw agents list` 确认正确的 agent ID，填入 `subagent_id` 或 `agent_id`。

### 8.5 TTS 合成失败

- **页面文件太小（os error 1455）**：TTS 模型加载需大量内存，建议关闭其他占用显存的程序，或将 TTS 模型加载到 CPU（修改 `tts.py` 中 `device`）。
- **CUDA kernel error**：GPU 显存不足或驱动问题，尝试重启或切换到 CPU。
- **libsilk not available**：缺少 QQ 语音格式转换库；机器人会自动降级发送 WAV 格式（部分 QQ 版本可能无法播放）。
- **SoX could not be found**：缺少 SoX 工具（Windows 可从 https://sox.sourceforge.net 下载并加入 PATH）；不影响 WAV 生成，但 Silk/AMR 转换会失败。
- **AMR conversion failed**：ffmpeg 版本不兼容；不影响基本 WAV 输出。

### 8.6 模型返回空回复

日志中出现 `Local LLM returned empty content`：
- 模型推理超时或服务不稳定，可适当调高 `timeout_seconds`。
- 部分模型对特定 prompt 格式不响应，尝试更换模型或调整 `system_prompt`。

---

## 9. WebSocket 连接诊断

若 NapCat 连接异常，可使用脚本排查：

```bash
python scripts/test_onebot_ws.py
```

输出包括：
- TCP 端口连通性检测
- WebSocket 握手测试
- 常见子路径探测

---

## 10. 测试

运行单元测试（不连接真实推理服务）：

```bash
python -m unittest tests.test_reply_error_echo_guard -v
```

若要连接真实本地服务测试错误守卫：

```bash
set AIBOT_LIVE_LLM_TEST=1
python -m unittest tests.test_reply_error_echo_guard -v
```

---

## 11. 安全与合规

- **勿**将含真实 token、QQ 号、群号的配置文件提交到公开仓库；`.gitignore` 已忽略 `llm_config.ini` 和 `group_whitelist.ini`。
- 使用非官方 QQ 协议存在**封号与合规风险**，请自行评估，仅限个人学习与可控场景使用。
- TTS 参考音频含个人声音特征，勿提交 `voice_ref/` 中的音频文件。

---

## 12. 项目结构

```
aibot/
├── bot.py                      # 入口
├── openclaw_memory.py          # 人设记忆加载
├── pyproject.toml              # 包元数据
├── requirements.txt             # 依赖列表
├── .env                        # 环境变量（勿上传）
├── .env.example                 # 环境变量模板
├── llm_config.ini              # 大模型配置（勿上传）
├── llm_config.example.ini      # 大模型配置模板
├── group_whitelist.ini         # 群白名单（勿上传）
├── group_whitelist.example.ini # 群白名单模板
├── plugins/echo/
│   ├── __init__.py             # 消息处理器（私聊/群聊/戳一戳）
│   ├── llm_reply.py           # LLM 调用（local / openclaw 双后端）
│   ├── llm_ini.py             # 读取 llm_config.ini
│   ├── chat_history.py        # 多轮对话内存管理
│   ├── whitelist.py           # 群白名单加载
│   ├── message_image.py       # 图片解析与压缩
│   ├── quoted_context.py      # 引用消息上下文
│   ├── reply_error_echo_guard.py  # 拦截 API 错误复述
│   └── tts.py                 # Qwen3-TTS 语音合成
├── 人设/
│   ├── soul.md                # 身份人设（启动时读入 system）
│   └── agent.md               # 行为约束
├── voice_ref/                  # TTS 语音克隆参考音频（勿上传）
├── models/                     # Qwen3-TTS 模型文件（勿上传）
├── scripts/
│   └── test_onebot_ws.py     # NapCat WS 连接诊断工具
├── tests/
│   └── test_reply_error_echo_guard.py  # 单元测试
└── logs/
    └── bot.log                # 运行日志（自动生成）
```

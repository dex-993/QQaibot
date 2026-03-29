# aibot 使用说明

基于 **NoneBot2** + **NapCatQQ（OneBot v11）** 的 QQ 机器人：私聊与群聊中根据配置调用 **本地 OpenAI 兼容大模型** 或 **OpenClaw Gateway**，并支持内存中的多轮对话。

---

## 1. 架构与数据流

```
QQ 客户端 ↔ NapCatQQ ↔ NoneBot2（本仓库）↔ 本地模型 / OpenClaw Gateway
```

- **NapCat**：登录 QQ，提供 **OneBot v11 正向 WebSocket** 服务。
- **NoneBot2**：作为 **WebSocket 客户端** 连接 NapCat；处理消息后发 HTTP 请求到大模型。
- **大模型**：由 `llm_config.ini` 选择 `local` 或 `openclaw`。

---

## 2. 环境要求

- **Python** 3.10+
- **NapCatQQ**：已安装、可登录 QQ，并开启 **OneBot 11 正向 WebSocket**（记下 `ws://` 地址与可选 token）。
- **大模型服务**（按所选后端）  
  - **local**：任意提供 **`/v1/chat/completions`** 的兼容服务（如 Ollama、LM Studio、vLLM）。  
  - **openclaw**：OpenClaw **Gateway** 已启用 **`POST /v1/responses`**（OpenResponses），见 [官方文档](https://docs.openclaw.ai/zh-CN/gateway/openresponses-http-api)。

---

## 3. 安装

在项目根目录（含 `pyproject.toml`）执行：

```bash
cd E:\aibot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

依赖列表与 `pyproject.toml` 一致，见根目录 [`requirements.txt`](requirements.txt)。

复制环境变量模板并编辑：

```bash
copy .env.example .env
copy llm_config.example.ini llm_config.ini
copy group_whitelist.example.ini group_whitelist.ini
```

（`llm_config.ini`、`group_whitelist.ini` 含密钥与个人 QQ/群号，默认已加入 `.gitignore`；仓库内只保留对应的 `*.example.ini` 模板。）

---

## 4. 配置文件说明

### 4.1 `.env`（环境与 NapCat 连接）

| 变量 | 说明 |
|------|------|
| `DRIVER` | 固定为 `~fastapi+~websockets`（正向 WS 需要 WebSocket 客户端）。 |
| `ONEBOT_WS_URLS` | JSON 数组，如 `["ws://127.0.0.1:18881"]`，与 NapCat 面板一致。 |
| `ONEBOT_ACCESS_TOKEN` | 若 NapCat 启用了 token，填写相同值；否则留空。 |
| `HOST` / `PORT` | 本机 **HTTP** 服务（Uvicorn），与 QQ 连接无关。`PORT` 若报 **WinError 10048**，改为未占用端口（如 `18080`）。 |
| `GROUP_WHITELIST_INI` | 可选，覆盖默认的群白名单 INI 路径。 |
| `LLM_CONFIG_INI` | 可选，覆盖默认的 `llm_config.ini` 路径。 |

### 4.2 `group_whitelist.ini`（群聊范围）

- 节名 **`[groups]`**。
- 每一行：`群号 = 1`（等号右侧仅占位）。
- **只有**白名单内的群，机器人才会处理「需 @ 机器人」的群消息逻辑。
- 修改后一般**无需**重启即可生效（每次会重新读文件）。

### 4.3 `llm_config.ini`（大模型与多轮对话）

#### `[llm]`

| 项 | 说明 |
|----|------|
| `backend` | `local` 或 `openclaw`。 |
| `history_enable` | 是否启用多轮对话（内存）。 |
| `history_max_rounds` | 最多保留多少轮「用户 + 助手」对。 |
| `history_max_tokens` | 历史估算 token 上限（约按字符长度 ÷ 4）。 |
| `history_ttl_seconds` | 某会话多久无消息则清空该桶；`0` 表示不按时间清。 |
| `memory_clear_master_qq` | 见下文「指令」中的 **清空全部记忆**；留空则关闭。 |
| `龙虾记忆` | **是否使用工作区记忆**：仅 **`backend=local`** 时生效；`true` 表示每次**启动本应用**读取人设目录 **`soul.md` / `agent.md`**，拼入本地模型 `system`（**不读取** `USER.md`）。 |
| `openclaw_workspace_memory` | （可选）与 **`龙虾记忆`** 二选一；若两项都写，**以 `龙虾记忆` 为准**。 |
| `openclaw_workspace_path` | 人设/工作区根目录。**留空**时优先使用项目内 **[`人设`](人设/)** 目录；若不存在再回退到 `~/.openclaw/workspace`。须为已存在的目录。 |
| `openclaw_workspace_max_chars` | 工作区正文总字符上限（默认 `32000`），超出则截断。 |

载入范围：仅根目录下的 **`soul.md`** 与 **`agent.md`**（**不读取** `USER.md`）。默认根目录为项目内 **`人设/`**。

#### `[local]`（OpenAI 兼容）

| 项 | 说明 |
|----|------|
| `base_url` | 如 `http://127.0.0.1:1234/v1`；若漏写 `/v1`，程序会自动补全。 |
| `api_key` | 按本地服务要求填写（如 LM Studio 常用占位即可）。 |
| `model` | 模型名，与服务端一致。 |
| `supports_vision` | **`true` / `false`**：是否启用**图片理解**（仅 **`backend=local`**）。需使用支持视觉的模型，默认 **`false`**。 |
| `vision_max_long_edge` | **整数**：转 JPEG **前**将 **最长边** 压到不超过该像素（等比）。**未写**时默认 **`1280`**，减轻本地视觉后端对超大分辨率的 **HTTP 400**。**`0`** = 不限制边长。 |
| `vision_max_image_bytes` | **整数**：单张图转 **JPEG 后** 的目标最大字节数；超过则**继续缩小/降质量**。**`0`** = 不限制字节（仍会先应用 `vision_max_long_edge`，除非其为 **0**）。 |
| `vision_jpeg_quality` | **`1`–`100`**（默认 **`85`**）：JPEG 质量；不限制字节时也会用该质量做一次编码。 |
| `system_prompt` | **人设**（系统提示词）。本地请求在启用 **`龙虾记忆`** 时会把 **`soul.md` / `agent.md`** 一并拼入 `system`（**含带图**）；另附简短多模态回复约定，避免模型默认只「描述画面」。 |
| `timeout_seconds` | 请求超时秒数。 |

#### `[openclaw]`

| 项 | 说明 |
|----|------|
| `base_url` | Gateway 根地址，**仅** `http://127.0.0.1:端口`（**不要**写 `/v1` 或 `/v1/responses`，否则会变成重复路径导致 502/404）。 |
| `token` | 与 Gateway 认证一致（如 `OPENCLAW_GATEWAY_TOKEN`）。 |
| `subagent_id` | **推荐**：子智能体 id；优先于 `agent_id`，且不再默认使用 `main`。 |
| `agent_id` | 未配置 `subagent_id` 时使用；二者至少填其一。 |
| `model` | 可留空则为 **`openclaw`**（智能体由 `x-openclaw-agent-id` 指定）；或显式写 **`openclaw/main`** 这类 **`openclaw/<agentId>`** 格式，**不要**写 `openclaw:xxx`（冒号无效）。 |
| `supports_vision` | 预留；**OpenClaw 路径当前不按图理解**（仅发文字）。默认 **`false`**。 |
| `instructions` | 合并为系统侧说明。 |
| `private_allow_qq` | **仅 `backend=openclaw` 时**：允许 **私聊** 走 Gateway 的 QQ 列表（逗号分隔）。不在名单内则**不请求、不回复私聊**。名单为空则**无人**可走 OpenClaw 私聊。 |
| `timeout_seconds` | 请求超时秒数。 |

**说明**：群聊走 OpenClaw 时**不受** `private_allow_qq` 限制（该字段仅约束私聊）。

**图片**：`backend=local` 且 `supports_vision=true` 时：`system` = **`system_prompt`** +（若启用 **`龙虾记忆`**）**工作区 soul/agent** + 多模态回复约定；图片经 **Pillow**：先 **`vision_max_long_edge`**（默认 1280）再 **`vision_max_image_bytes`**。若仍 **400**，可把边长改为 **`1024`** 或把字节上限再降，并减少同条消息里的张数。多模态 **`content` 顺序为「文在前、图在后」**（适配 LM Studio / Qwen Jinja）；若用户**只发图、无文字**，程序会附带一句占位 user 文本。**多轮**里仅**最后一条** user 保留图，更早带图轮次在请求里会压成纯文字。**单条最多 6 张**；单张下载上限约 **200MB**。若 **`supports_vision=false`** 且**只有图**，机器人**不回复**。`backend=openclaw` 不按图理解。

**引用 / 回复**：若客户端通过 NoneBot 成功解析出 **`event.reply`**（依赖 NapCat **`get_msg`**），会把 **被引消息的发送者（群名片/昵称、QQ）**、**被引正文** 写入 user 文字；**被引消息里的图**（本地 vision 开启时）与**本条里的图**合并传入模型（**先引用图、再本条图**，合计仍受 **6 张** 上限）。`backend=openclaw` 或**未开 vision** 时仍可看到引用**文字**，但**看不到被引图**。

---

## 5. 启动顺序

1. 启动 **NapCat**，确认 QQ 在线、正向 WebSocket 端口正确。  
2. 启动 **大模型**（local 或 OpenClaw Gateway）。  
3. 在项目目录执行：

```bash
python bot.py
```

日志中出现 **OneBot V11 … connected** 表示已与 NapCat 建立连接。

---

## 6. 使用方式（QQ 侧）

### 6.1 私聊

- 直接发文字即可调用大模型（过长会提示缩短）。  
- **`backend=openclaw`**：仅 `private_allow_qq` 中的 QQ 会收到模型回复；其余 QQ **静默**（不调 Gateway）。  
- **`backend=local`**：无 QQ 白名单限制。

### 6.2 群聊

- 仅当 **群号在白名单**（`group_whitelist.ini`）且 **@ 当前机器人**（或与 @ 等价的「引用」），且 **有文字或带图** 时，才会调用模型。  
- **与「仅 @」一致**：整段消息里 **任意位置** 出现指向本机器人的 **`at` 段** 都算（NTQQ 常见 **`[回复][@机器人][正文]`**，NoneBot 默认只处理首尾 @，`to_me` 可能为 False，本仓库会扫全段）。  
- **`event.reply`**：若引用原消息的发送者是 **本机器人**，也视为在叫你（**回复你的消息** 与 **@ 你** 同一套后续逻辑：抽 `plaintext`、调模型等）。

### 6.3 指令

| 场景 | 指令 | 作用 |
|------|------|------|
| 私聊 | `/清空` 或 `/clear` | 清空**自己**的私聊多轮桶。 |
| 群内（需 @ 机器人） | `/清空` 或 `/clear` | 清空**你在该群**的多轮桶。 |
| 私聊 | `/清空全部记忆` | 若你的 QQ 在 `memory_clear_master_qq` 中：清空**所有人/群**的多轮桶；否则提示无权；名单留空则该指令**关闭**（他人发送不回复）。 |

---

## 7. 多轮对话说明

- **私聊**会话键：`priv:<QQ>`。  
- **群聊**会话键：`grp:<群号>:<QQ>`（同群不同用户互不串上下文）。  
- 数据仅存于 **当前 Python 进程内存**；**重启 `python bot.py` 后全部丢失**（未使用数据库）。

---

## 8. 常见问题

### 8.1 端口被占用（WinError 10048）

修改 `.env` 中的 **`PORT`**，或结束占用该端口的进程：

```text
netstat -ano | findstr :18080
taskkill /PID <PID> /F
```

### 8.2 群聊无回复

- 确认群号已写入 `group_whitelist.ini` 的 `[groups]`。  
- 确认 @ 的是**本机器人**，且 @ 后带有文字。  
- 本地模型：确认服务已启动，`base_url` 与 `model` 正确。

### 8.3 本地模型连接失败

- 浏览器或 curl 测试：`http://地址/v1/models` 或实际提供的健康检查接口。  
- 确认防火墙未拦截。

### 8.4 OpenClaw 报错

#### 如何打开 OpenResponses（`POST /v1/responses`）

1. 编辑 OpenClaw 主配置文件（官方文档称全量在 **`~/.openclaw/openclaw.json`**；Windows 一般为 **`C:\Users\<你的用户名>\.openclaw\openclaw.json`**，若用过 `OPENCLAW_CONFIG_PATH` 则以该路径为准）。  
2. 在 **`gateway`** 下合并 **`http.endpoints.responses`**，将 **`enabled`** 设为 **`true`**（勿与现有 `gateway` 结构冲突，应在同一 `gateway` 对象内嵌套）：

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

若你已有 `gateway.http`，只需在其中的 `endpoints` 下增加或覆盖 `responses` 段即可。  
3. **保存后重启 OpenClaw Gateway**（停掉再执行你平时的 `openclaw gateway` 启动方式）。  
4. 用浏览器或 curl 对 **`http://<网关地址>:<端口>/v1/responses`** 发 `POST`（需带 `Authorization: Bearer <token>`）做连通性测试。

官方说明见：[OpenResponses API（OpenClaw 文档）](https://docs.openclaw.ai/zh-CN/gateway/openresponses-http-api)。

- 检查 `token`、`subagent_id` / `agent_id` 与网关配置一致。  
- **HTTP 502**：多为「网关能收到请求，但上游失败」——例如智能体依赖的 **OpenAI/Anthropic/本地 Ollama** 等未启动、Key 无效、或代理超时。请在 OpenClaw / Gateway 日志里看同一时间点的报错；确认 `base_url` 指向的确实是 **Gateway 根地址**（请求路径为 `{base_url}/v1/responses`）。  
- 若机器人回复里已带网关返回的简短 `message`，可据此继续排查。

---

## 9. 安全与合规

- **勿**将真实 `token`、Cookie 提交到公开仓库；`.env` 已建议加入 `.gitignore`。  
- 使用非官方 QQ 协议存在**封号与合规风险**，请自行评估，仅限个人学习与可控场景使用。

---

## 10. 项目结构（简要）

| 路径 | 说明 |
|------|------|
| `bot.py` | 入口：加载环境变量、注册 OneBot v11、加载插件。 |
| `plugins/echo/` | 消息处理、白名单、历史、LLM 调用。 |
| `group_whitelist.ini` | 群号白名单。 |
| `llm_config.ini` | 大模型后端与多轮参数。 |
| `.env` | NapCat 连接与本机 HTTP 端口。 |

更简要的说明可同时参考仓库根目录 [`README.md`](README.md)。

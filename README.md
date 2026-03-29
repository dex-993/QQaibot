# NoneBot2 ↔ NapCat（正向 WebSocket）

完整使用说明见 **[USAGE.md](USAGE.md)**（安装、配置项、指令、排错等）。

## 配置

- 默认在 [`.env`](.env) 中连接 `ws://127.0.0.1:18881`（与 NapCat 面板中的 OneBot 11 **正向 WebSocket** 监听地址一致）。
- 若 NapCat 要求路径（例如自定义 `ws` 路径），请把 `ONEBOT_WS_URLS` 改成完整地址，如 `["ws://127.0.0.1:18881/xxx"]`。
- 驱动为 `~fastapi+~websockets`，以支持 WebSocket **客户端**连接。
- **端口占用（WinError 10048）**：`.env` 里 **`PORT`** 为本机 HTTP 监听端口（与 NapCat WS 无关）。若被占用，改 `PORT`（默认已用较少冲突的 `18080`），或结束占用端口的进程：`netstat -ano | findstr :8081` 后 `taskkill /PID <pid> /F`。

## 运行

```bash
pip install -r requirements.txt
pip install -e .
python bot.py
```

（若只需依赖、不装可编辑包，可只执行 `pip install -r requirements.txt`。）

顺序：**先启动 NapCat 并登录 QQ**；若使用 **本地模型** 或 **OpenClaw Gateway**，请先启动对应服务，再运行本仓库。

- **私聊**：发文字 → 按 [`llm_config.ini`](llm_config.ini) 调用模型。**`backend=openclaw` 时**，仅 [`[openclaw] private_allow_qq`](llm_config.ini) 名单内的 QQ 会请求 Gateway；其他人私聊**不调 OpenClaw、也不回复**。**`backend=local` 时**私聊无此限制。
- **群聊**：仅当群号在 [`group_whitelist.ini`](group_whitelist.ini) 的 `[groups]` 中，且 **@ 机器人** 时回复（默认白名单含 `1095070178`）。

### 大模型切换（`llm_config.ini`）

- **`[llm]` → `backend`**：`openclaw` 或 `local`。
- **`[openclaw]`**：`base_url`、`token`、`instructions` 等。需在 OpenClaw 中启用 OpenResponses 端点，见 [OpenResponses API](https://docs.openclaw.ai/zh-CN/gateway/openresponses-http-api)。
  - **`subagent_id`（推荐）**：填写子智能体 id 后，请求使用 **`x-openclaw-agent-id: <subagent_id>`**；**`model`** 须为 **`openclaw`** 或 **`openclaw/<agentId>`**（斜杠），留空时程序发 **`openclaw`**。
  - 未填 `subagent_id` 时使用 **`agent_id`**；二者至少填一个。`model` 可留空以自动拼接。
  - **`private_allow_qq`**：`backend=openclaw` 时仅这些 QQ 的**私聊**会发到 Gateway；名单为空则**无人**可走 OpenClaw 私聊。
- **`[local]`**：`base_url`、`api_key`、`model`、`supports_vision`、`vision_max_long_edge`（默认 1280，**0**=不限制）、`vision_max_image_bytes`、`vision_jpeg_quality`、`system_prompt`（人设）等；带图时若启用「龙虾记忆」仍会合并 `soul.md`/`agent.md`，并附加多模态回复约定。

可选环境变量 **`LLM_CONFIG_INI`** 指定其它 INI 路径（相对路径相对项目根目录）。

### 多轮对话（内存）

在 [`llm_config.ini`](llm_config.ini) 的 **`[llm]`** 中：`history_enable`、`history_max_rounds`（用户+助手对数）、`history_max_tokens`（按字符粗估 token）、`history_ttl_seconds`（闲置秒数后清空该会话桶，0 表示不按时间清）。

- **私聊**桶：`priv:<QQ>`；**群聊**桶：`grp:<群号>:<QQ>`（同群不同人互不串）。
- 私聊或群内 @ 机器人发 **`/清空`** 或 **`/clear`** 可清空对应桶。
- 私聊发 **`/清空全部记忆`**：仅当 [`memory_clear_master_qq`](llm_config.ini) 非空且你在名单中时，会清空**所有用户/群**的对话桶；留空则关闭（防误触）。
- **重启 `python bot.py` 也会清空全部内存历史**（未接数据库）。
- **`backend=local`** 且 `[llm] 龙虾记忆=true`：启动时读取 **[`人设`](人设/)** 下 **`soul.md` / `agent.md`**（排除 `USER.md`）并入 `system`；默认目录为项目内 `人设/`，也可用 `openclaw_workspace_path` 指向其它路径（也可用英文键 `openclaw_workspace_memory`，以 `龙虾记忆` 为准），详见 [USAGE.md](USAGE.md)。

### 群聊没回复时排查

- 群号是否在 [`group_whitelist.ini`](group_whitelist.ini) 的 `[groups]` 里（与 QQ 里显示的群号一致）。
- 是否 **@ 了当前登录的机器人**，且 **@ 后面有文字**（仅 @ 无字会收到提示，不会调模型）。
- 本地模型：`[local]` 的 `base_url` 需指向 OpenAI 兼容根路径，代码会自动补全 **`/v1`**；模型服务需已启动。

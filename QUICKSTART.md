# 从零开始：Windows 完整部署指南

> 本指南面向**零基础用户**，一步一步把机器人从什么都没有跑起来。涵盖 NapCat 安装、LLM 服务配置、TTS 模型下载、以及机器人启动全部流程。

---

## 一、整体架构（先搞懂是什么）

```
你的 QQ 账号 ←→ NapCat（模拟 QQ 协议）←→ aibot（机器人程序）←→ 大模型（生成回复）
```

- **NapCat**：一个软件，用你的 QQ 账号登录，让机器人能收发消息
- **aibot**：本项目，收到消息后调用大模型，生成回复
- **大模型**：生成对话内容，可以是本地部署的模型（推荐）或远程 API
- **TTS**：把文字转成语音，用你提供的参考音频克隆声音

---

## 二、前置准备

### 2.1 安装 Python

1. 打开 https://www.python.org/downloads/windows/
2. 下载 **Python 3.10 或更高版本**（推荐 3.12）
3. 运行安装程序，**务必勾选** `Add Python to PATH`
4. 验证：打开命令提示符（Win+R → 输入 `cmd` → 回车），输入：

```bash
python --version
```

看到类似 `Python 3.12.x` 即为成功。

### 2.2 下载 NapCatQQ

NapCatQQ 是一个 QQ 客户端，可以让你的 QQ 账号以机器人身份登录。

1. 打开 https://github.com/NapNeko/NapCatQQ/releases
2. 下载最新版本的 `NapCat-QQ[x.x.x].exe`（或 `NapCatQQ-Desktop-x.x.x.zip`）
3. 双击运行，按提示完成安装

> 如果 GitHub 下载慢，可以去 Gitee 镜像或使用代理。

### 2.3 安装 LLM 服务（本地模型，推荐 LM Studio）

用本地模型不需要任何 API key，完全免费，推荐小白使用。

#### 方法 A：LM Studio（最简单，推荐）

1. 打开 https://lmstudio.ai/download
2. 下载 Windows 版本并安装
3. 启动 LM Studio，左侧搜索并下载一个中文模型，比如 `Qwen2.5-7B` 或 `Qwen2.5-14B`（根据你的显存选，7B 约需 6GB 显存，14B 约需 12GB）
4. 点击右上角 **🔗** 图标，切换到 "Server" 标签
5. 点击 **Start Server**，确保显示 `Running on http://127.0.0.1:1234`

> 默认端口是 1234，如果改过记住它，后面配置要用。

#### 方法 B：Ollama（更轻量）

1. 打开 https://ollama.com/download
2. 下载并安装
3. 打开命令行，运行：

```bash
# 下载模型（以 Qwen2.5 为例）
ollama pull qwen2.5:7b

# 启动服务（端口默认 11434）
ollama serve
```

> 本指南以 LM Studio 为例，端口 `1234`。Ollama 用户请将后文的 `1234` 替换为 `11434`。

---

## 三、克隆并安装项目

### 3.1 下载本项目

如果你已经从 GitHub 下载了 zip 文件，解压到 `E:\aibot`（或任意路径，但路径里**不要有中文和空格**）。

如果你要通过 Git 克隆：

```bash
git clone https://github.com/dex-993/aibot.git
cd aibot
```

### 3.2 创建 Python 虚拟环境

```bash
# 进入项目目录
cd E:\aibot

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
.venv\Scripts\activate
```

激活后命令行前面会出现 `(.venv)` 字样。

### 3.3 安装依赖

```bash
pip install -r requirements.txt
pip install -e .
```

如果安装 `qwen-tts` 时报错，尝试单独安装：

```bash
pip install qwen-tts soundfile
```

### 3.4 复制配置文件

```bash
copy .env.example .env
copy llm_config.example.ini llm_config.ini
copy group_whitelist.example.ini group_whitelist.ini
```

---

## 四、配置 NapCatQQ（连接机器人）

### 4.1 登录 QQ

1. 启动 NapCat，输入账号密码登录
2. 登录成功后，找到设置页面

### 4.2 开启 OneBot 正向 WebSocket

这一步是为了让 aibot 能收到消息。

1. 在 NapCat 设置中找到 **OneBot 设置** 或 **正向 WebSocket**
2. 开启正向 WebSocket，监听地址填写：`ws://127.0.0.1:18881`
3. 如果 NapCat 启用了 access token（密码保护），复制这个 token 备用
4. **记住所填的端口号 `18881`，后面要用**

### 4.3 测试连接（可选）

```bash
# 确保 NapCat 已启动并登录，然后在 aibot 目录运行：
python scripts/test_onebot_ws.py
```

看到 `TCP connect 127.0.0.1:18881 -> OK` 即为成功。

---

## 五、配置 aibot

### 5.1 编辑 `.env`

用记事本打开项目根目录的 `.env`，内容如下：

```ini
DRIVER=~fastapi+~websockets
ONEBOT_WS_URLS=["ws://127.0.0.1:18881"]
ONEBOT_ACCESS_TOKEN=
HOST=127.0.0.1
PORT=18080
```

- `ONEBOT_WS_URLS`：填第 4.2 步中 NapCat 的监听地址
- `ONEBOT_ACCESS_TOKEN`：如果 NapCat 开启了 token，填入；没开就留空
- `PORT`：本机 HTTP 端口，一般不用改

### 5.2 编辑 `llm_config.ini`

用记事本打开 `llm_config.ini`，修改以下部分：

#### 如果使用 LM Studio（推荐）

找到 `[local]` 部分：

```ini
[local]
base_url = http://127.0.0.1:1234/v1
api_key = lm-studio
model = qwen2.5-7b-instruct   # 改成你在 LM Studio 下载的模型名称
supports_vision = false         # 如果模型支持图片理解改为 true
...
```

找到顶部的 `[llm]` 部分，确认：

```ini
backend = local    # 必须是 local，不是 openclaw
龙虾记忆 = true   # 启动时加载人设文件
```

#### 如果使用 OpenClaw

```ini
backend = openclaw

[openclaw]
base_url = http://127.0.0.1:18790
token = 你的OPENCLAW_GATEWAY_TOKEN
agent_id = main
private_allow_qq = 你的QQ号   # 填你的 QQ 号才能私聊
```

> **注意**：`openclaw` 后端还需要额外配置 OpenClaw Gateway，较为复杂，建议新手先用 `local`（LM Studio）。

### 5.3 配置群白名单 `group_whitelist.ini`

打开 `group_whitelist.ini`，填入允许机器人响应的群号：

```ini
[groups]
123456789 = 1
```

- 群号怎么查：在群里点击右上角群资料，往下滑找到"群号"
- **每行一个群号**，`= 1` 只是格式占位符，没有实际意义

### 5.4 配置人设（可选）

人设决定机器人的性格。打开 `人设/soul.md` 和 `人设/agent.md` 查看和修改。

---

## 六、配置 TTS 语音合成（可选）

TTS 可以让机器人的回复用语音发送，而不是文字。需要额外下载模型。

### 6.1 下载 TTS 模型

需要下载两个模型文件：

#### 模型 1：Qwen3-TTS Base（约 3.8 GB）

1. 打开 https://modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-Base
2. 点击"下载模型"（需要注册 modelscope 账号）
3. 下载后把文件夹放到项目目录的 `models/` 下，最终路径类似：
   ```
   E:\aibot\models\Qwen3-TTS-12Hz-1.7B-Base\
   ```

#### 模型 2：Qwen3-TTS Tokenizer（约 几百 MB）

```bash
pip install modelscope
modelscope download --model Qwen/Qwen3-TTS-Tokenizer-12Hz --local_dir E:\aibot\models\Qwen3-TTS-Tokenizer-12Hz
```

### 6.2 准备语音克隆参考音频（可选）

让机器人用**你的声音**说话：

1. 准备一个 5~30 秒的清晰人声录音（.wav 或 .mp3 格式），内容是一段连贯的中文语句
2. 建议内容：简单自我介绍或一段故事，保持自然语速
3. 将音频文件放入 `voice_ref/` 目录，比如 `voice_ref/my_voice.wav`
4. **禁止将含你声音的音频提交到 GitHub**

### 6.3 配置 TTS

编辑 `llm_config.ini` 中的 `[tts]` 部分：

```ini
[tts]
enabled = true
model_path = models/Qwen3-TTS-12Hz-1.7B-Base
ref_text = 大家好呀！今天天气真不错，我要给大家介绍一个超厉害的新技术，快来听听吧！
language = Chinese
max_duration_seconds = 60
prefer_voice = true
```

- `ref_text`：填入参考音频对应的文字（**必须和音频内容一致**，否则克隆效果差）
- 如果你放了参考音频，取消 `ref_audio` 的注释并填路径；不填则使用默认音色

### 6.4 安装 TTS 依赖

```bash
pip install qwen-tts soundfile numpy scipy
```

如果 GPU 显存不够（报 `页面文件太小` 错误），可以在 `plugins/echo/tts.py` 里把：

```python
device = "cuda:0" if torch.cuda.is_available() else "cpu"
```

改成 `"cpu"`，用 CPU 运行（会慢很多，但不吃显存）。

---

## 七、启动机器人

### 7.1 启动顺序（必须按这个顺序！）

```
第一步：启动 NapCat（确保 QQ 已登录）
第二步：启动 LM Studio（或 Ollama）—— 如果用 local 后端
第三步：启动 aibot
```

### 7.2 运行机器人

```bash
# 确保虚拟环境已激活（前面有 .venv）
.venv\Scripts\activate

# 运行
python bot.py
```

### 7.3 验证是否成功

看到以下输出说明启动成功：

```
Uvicorn running on http://127.0.0.1:18080
OneBot V11 ... connected
[龙虾记忆] loaded 2 file(s) from ...
```

如果 TTS 配置正确，还会看到：

```
[TTS] 使用 voice_ref/xxx.wav，ref_text=...
Qwen3-TTS loaded successfully
```

### 7.4 测试

- **私聊**：给机器人发一条消息，它应该回复你
- **群聊**：在白名单群里 @ 机器人，它应该回复

如果没反应，去 `logs/bot.log` 看日志排查。

---

## 八、常见问题排查

### 机器人完全没反应

1. NapCat 在线吗？NapCat 要保持运行且 QQ 账号已登录
2. 日志有没有 `OneBot V11 ... connected`？没有说明连接失败，检查 `.env` 的 `ONEBOT_WS_URLS` 端口是否和 NapCat 一致
3. `.env` 里 `ONEBOT_ACCESS_TOKEN` 是否和 NapCat 设置的 token 一致

### 提示模型连接失败

- LM Studio 的 Server 页面有没有点 "Start Server"？
- 端口对不对？（默认 `1234`，`.env` 里的 `ONEBOT_WS_URLS` 是 `18881`，不是一回事）
- 浏览器访问 http://127.0.0.1:1234/v1/models 看能不能打开

### 群聊无回复

- 群号填对了吗？（`.ini` 里的群号要和 QQ 显示的完全一致）
- @ 机器人的时候有没有带文字？（只有 @ 没有文字会收到提示语，不是无响应）
- 机器人有没有被踢出群？

### TTS 报 "页面文件太小"

显存不够，修改 `plugins/echo/tts.py`，找到：

```python
device = "cuda:0" if torch.cuda.is_available() else "cpu"
```

把 `"cuda:0"` 改成 `"cpu"`。

### 语音是默认音色而不是我的声音

- `ref_audio` 路径填对了吗？（用正斜杠或双反斜杠：`voice_ref/my.wav` 或 `voice_ref\\my.wav`）
- `ref_text` 和音频内容完全一致吗？
- 参考音频质量够吗？（建议 5~30 秒清晰人声，无背景音乐）

### 语音发出去但对方听不到

这是正常现象！WAV 格式部分 QQ 版本不支持播放。要完美支持需要安装 SoX 和 ffmpeg（较复杂），不影响文字回复功能。

---

## 九、日常使用

### 重新启动机器人

每次重启机器人：
1. 先按 `Ctrl+C` 停止旧进程
2. 确认 NapCat 和 LM Studio 还在运行
3. 重新运行 `python bot.py`

### 修改配置后需要重启吗？

- `.env`：需要重启
- `llm_config.ini` 大部分配置：**不需要重启**，下次请求自动生效
- `group_whitelist.ini`：**不需要重启**，下次消息自动生效
- `人设/soul.md` / `人设/agent.md`：需要重启机器人

### 清空对话记忆

- 私聊发送 `/清空` — 清空你和机器人的对话历史
- 群聊 @ 机器人发送 `/清空` — 清空你在该群的历史

---

## 十、一图总结启动流程

```
安装 Python
    ↓
安装并配置 NapCatQQ（开启正向 WebSocket，记录端口 18881）
    ↓
安装 LM Studio（下载模型，启动 Server，端口 1234）
    ↓
克隆本项目，安装依赖，复制配置文件
    ↓
配置 .env（NapCat 地址）、llm_config.ini（LLM 地址）、group_whitelist.ini（群号）
    ↓
下载 Qwen3-TTS 模型到 models/（可选）
    ↓
先启动 NapCat → 再启动 LM Studio → 最后 python bot.py
    ↓
开始聊天！
```

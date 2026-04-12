"""NoneBot2 入口：OneBot v11 正向 WebSocket 连接 NapCat。"""

from dotenv import load_dotenv
import logging
from pathlib import Path

load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# 配置根日志：控制台 + 文件
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.handlers.clear()

fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s | %(message)s", datefmt="%m-%d %H:%M:%S")

# 文件 handler（UTF-8，避免 gbk 问题）
fh = logging.FileHandler(_LOG_DIR / "bot.log", encoding="utf-8")
fh.setFormatter(fmt)
fh.setLevel(logging.INFO)
_root_logger.addHandler(fh)

# 控制台 handler
ch = logging.StreamHandler()
ch.setFormatter(fmt)
ch.setLevel(logging.INFO)
_root_logger.addHandler(ch)

logger = logging.getLogger("aibot")

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

import openclaw_memory  # noqa: E402 — 须在 load_plugins 前执行，避免重复加载 echo

openclaw_memory.refresh_at_startup()

nonebot.load_plugins("plugins")


@driver.on_startup
def _check_tts():
    from plugins.echo.tts import _validate_voice_ref
    ok, msg = _validate_voice_ref()
    logger.info("[TTS] %s", msg)


if __name__ == "__main__":
    nonebot.run()


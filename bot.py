"""NoneBot2 入口：OneBot v11 正向 WebSocket 连接 NapCat。"""

from dotenv import load_dotenv

load_dotenv()

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

import openclaw_memory  # noqa: E402 — 须在 load_plugins 前执行，避免重复加载 echo

openclaw_memory.refresh_at_startup()

nonebot.load_plugins("plugins")


if __name__ == "__main__":
    nonebot.run()

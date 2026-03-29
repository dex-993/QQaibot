"""从 INI 读取群聊白名单（群号）。"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

# 项目根目录（.../plugins/echo -> 上两级）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def whitelist_ini_path() -> Path:
    raw = os.getenv("GROUP_WHITELIST_INI", "group_whitelist.ini")
    p = Path(raw)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p


def load_group_ids() -> set[int]:
    """读取 [groups] 下所有键名为数字的群号。文件不存在或节为空则返回空集合。"""
    path = whitelist_ini_path()
    if not path.is_file():
        return set()
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section("groups"):
        return set()
    out: set[int] = set()
    for key in cfg["groups"]:
        k = str(key).strip()
        if k.isdigit():
            out.add(int(k))
        elif k.startswith("-") and k[1:].isdigit():
            out.add(int(k))
    return out

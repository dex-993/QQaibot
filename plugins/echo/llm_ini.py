"""读取 llm_config.ini：后端选择与 OpenClaw / 本地参数。"""

from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def llm_ini_path() -> Path:
    raw = os.getenv("LLM_CONFIG_INI", "llm_config.ini")
    p = Path(raw)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p


def load_llm_config() -> configparser.ConfigParser:
    path = llm_ini_path()
    cfg = configparser.ConfigParser()
    if path.is_file():
        cfg.read(path, encoding="utf-8")
    return cfg


def get_backend() -> str:
    cfg = load_llm_config()
    if not cfg.has_section("llm"):
        return "local"
    v = (cfg.get("llm", "backend", fallback="local") or "local").strip().lower()
    if v in ("openclaw", "local"):
        return v
    return "local"


def section_dict(section: str) -> dict[str, str]:
    cfg = load_llm_config()
    if not cfg.has_section(section):
        return {}
    return {k: v.strip() if isinstance(v, str) else v for k, v in cfg.items(section)}


def openclaw_private_allow_qq_ids() -> set[str]:
    """OpenClaw 私聊白名单：仅这些 QQ 号会请求 Gateway。逗号分隔，支持中文逗号。"""
    raw = (section_dict("openclaw").get("private_allow_qq") or "").strip()
    if not raw:
        return set()
    normalized = raw.replace("，", ",")
    return {x.strip() for x in normalized.split(",") if x.strip()}


def openclaw_private_allowed(user_id: str) -> bool:
    allowed = openclaw_private_allow_qq_ids()
    if not allowed:
        return False
    return str(user_id).strip() in allowed


def memory_clear_master_qq_ids() -> set[str]:
    """私聊 /清空全部记忆 的白名单；空集合表示关闭该指令。"""
    raw = (section_dict("llm").get("memory_clear_master_qq") or "").strip()
    if not raw:
        return set()
    normalized = raw.replace("，", ",")
    return {x.strip() for x in normalized.split(",") if x.strip()}


def get_group_empty_at_replies() -> list[str]:
    """群聊仅 @、无正文无图无引用时的回复列表；英文逗号分隔，每次随机一条。

    未配置或解析后为空时返回空列表，由调用方使用兜底文案。
    """
    raw = (section_dict("llm").get("group_empty_at_replies") or "").strip()
    if not raw:
        return []
    parts = [x.strip() for x in raw.split(",")]
    return [x for x in parts if x]


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


def _truthy(raw: str | None, default: bool = False) -> bool:
    s = (raw or "").strip().lower()
    if not s:
        return default
    return s in ("1", "true", "yes", "on")


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


def get_history_config() -> dict[str, Any]:
    d = section_dict("llm")
    try:
        max_rounds = int(d.get("history_max_rounds", "10"))
    except ValueError:
        max_rounds = 10
    try:
        max_tokens = int(d.get("history_max_tokens", "4000"))
    except ValueError:
        max_tokens = 4000
    try:
        ttl = int(d.get("history_ttl_seconds", "0"))
    except ValueError:
        ttl = 0
    if max_rounds < 1:
        max_rounds = 10
    if max_tokens < 200:
        max_tokens = 200
    return {
        "enable": _truthy(d.get("history_enable"), True),
        "max_rounds": max_rounds,
        "max_tokens": max_tokens,
        "ttl": ttl,
    }


def model_supports_vision() -> bool:
    """当前 `backend` 对应小节是否声明模型支持视觉（图片）输入。

    供后续多模态消息逻辑读取；未配置或为空时视为不支持。
    """
    sec = "openclaw" if get_backend() == "openclaw" else "local"
    d = section_dict(sec)
    return _truthy(d.get("supports_vision"), False)


def get_local_vision_image_limits() -> dict[str, int]:
    """`[local]` 单张图：最长边、JPEG 字节上限与质量。

    `vision_max_long_edge` 未写时默认 **1280**（本地视觉后端常因像素过大返回 400，与文件体积无关）。
    显式填 **0** 表示不限制最长边。
    """
    d = section_dict("local")
    raw = (d.get("vision_max_image_bytes") or "").strip()
    try:
        max_bytes = int(raw) if raw else 0
    except ValueError:
        max_bytes = 0
    if max_bytes < 0:
        max_bytes = 0
    edge_raw = (d.get("vision_max_long_edge") or "").strip()
    if not edge_raw:
        max_long_edge = 1280
    else:
        try:
            max_long_edge = int(edge_raw)
        except ValueError:
            max_long_edge = 1280
    if max_long_edge < 0:
        max_long_edge = 0
    try:
        q = int((d.get("vision_jpeg_quality") or "85").strip() or "85")
    except ValueError:
        q = 85
    q = max(1, min(q, 100))
    return {
        "max_bytes": max_bytes,
        "jpeg_quality": q,
        "max_long_edge": max_long_edge,
    }

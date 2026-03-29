"""应用启动时从人设目录读取 soul.md、agent.md（作本地模型 system 补充），排除 USER.md。"""

from __future__ import annotations

import configparser
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent
# 默认人设目录（相对项目根）：内含 soul.md、agent.md
_PERSONA_DIR = _PROJECT_ROOT / "人设"

_BUNDLE_CACHE: str = ""
_BUNDLE_LOADED: bool = False


def _llm_ini_path() -> Path:
    raw = os.getenv("LLM_CONFIG_INI", "llm_config.ini")
    p = Path(raw)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p


def _truthy(raw: str | None) -> bool:
    s = (raw or "").strip().lower()
    return s in ("1", "true", "yes", "on")


def _workspace_root_from_config(section: dict[str, str]) -> Path | None:
    raw = (section.get("openclaw_workspace_path") or "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        return p if p.is_dir() else None
    if _PERSONA_DIR.is_dir():
        return _PERSONA_DIR
    fallback = Path.home() / ".openclaw" / "workspace"
    return fallback if fallback.is_dir() else None


def _skip_file(name: str) -> bool:
    return name.lower() == "user.md"


def _collect_markdown_files(root: Path) -> list[Path]:
    """只载入根目录下的 soul.md、agent.md（小写文件名）。"""
    names = ("soul.md", "agent.md")
    files: list[Path] = []
    for name in names:
        p = root / name
        if not p.is_file() or _skip_file(p.name):
            continue
        files.append(p)
    return files


def _read_files(root: Path, paths: list[Path], max_chars: int) -> str:
    parts: list[str] = []
    total = 0
    for p in paths:
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            rel = str(p)
        try:
            text = p.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as e:
            logger.warning("skip reading %s: %s", p, e)
            continue
        block = f"### 文件: {rel}\n{text}"
        if total + len(block) + 1 > max_chars:
            remain = max_chars - total - 50
            if remain > 100:
                block = f"### 文件: {rel}\n{text[:remain]}\n…[该文件已截断]"
            else:
                block = f"### 文件: {rel}\n…[已达总长度上限，省略]"
            parts.append(block)
            parts.append("\n[OpenClaw 工作区内容已达 openclaw_workspace_max_chars，后续文件未载入]")
            break
        parts.append(block)
        total += len(block) + 1
    return "\n\n".join(parts)


def _build_bundle() -> str:
    path = _llm_ini_path()
    cfg = configparser.ConfigParser()
    if not path.is_file():
        return ""
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section("llm"):
        return ""
    sec = {k: v.strip() if isinstance(v, str) else v for k, v in cfg.items("llm")}
    # 「龙虾记忆」与 openclaw_workspace_memory 二选一；若都写以「龙虾记忆」为准
    lobster = (sec.get("龙虾记忆") or "").strip()
    legacy = (sec.get("openclaw_workspace_memory") or "").strip()
    flag_raw = lobster if lobster else legacy
    if not _truthy(flag_raw):
        logger.info("龙虾记忆（OpenClaw 工作区）: 未启用")
        return ""

    backend = (sec.get("backend") or "local").strip().lower()
    if backend != "local":
        logger.info(
            "openclaw workspace_memory: skipped (only applies when [llm] backend=local)",
        )
        return ""

    try:
        max_chars = int(sec.get("openclaw_workspace_max_chars", "32000"))
    except ValueError:
        max_chars = 32000
    max_chars = max(2000, min(max_chars, 200000))

    root = _workspace_root_from_config(sec)
    if root is None:
        raw_path = (sec.get("openclaw_workspace_path") or "").strip()
        if raw_path:
            logger.warning(
                "openclaw workspace_memory: path not a directory: %s",
                raw_path,
            )
        else:
            logger.warning(
                "openclaw workspace_memory: no persona dir (%s) and no ~/.openclaw/workspace; set openclaw_workspace_path",
                _PERSONA_DIR,
            )
        return ""

    md_files = _collect_markdown_files(root)
    if not md_files:
        logger.info("openclaw workspace_memory: no markdown found under %s", root)
        return ""

    body = _read_files(root, md_files, max_chars)
    logger.info(
        "openclaw workspace_memory: loaded %d file(s) from %s",
        len(md_files),
        root,
    )
    return body


def refresh_at_startup() -> None:
    """在 bot 启动时调用一次：读取工作区并缓存。"""
    global _BUNDLE_CACHE, _BUNDLE_LOADED
    _BUNDLE_LOADED = True
    _BUNDLE_CACHE = _build_bundle()


def get_workspace_bundle() -> str:
    """供本地模型合并进 system；若未调用 refresh_at_startup 则此处懒加载。"""
    global _BUNDLE_CACHE, _BUNDLE_LOADED
    if not _BUNDLE_LOADED:
        _BUNDLE_LOADED = True
        _BUNDLE_CACHE = _build_bundle()
    return _BUNDLE_CACHE

"""多轮对话上下文：内存存储，按 priv:QQ 或 grp:群:QQ 分桶。"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from .llm_ini import get_history_config

ChatScope = Literal["private", "group"]


@dataclass
class _Session:
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)


_sessions: dict[str, _Session] = {}
_locks: dict[str, asyncio.Lock] = {}


def history_key(scope: ChatScope, user_id: str, group_id: str | None) -> str | None:
    uid = str(user_id).strip()
    if scope == "private":
        return f"priv:{uid}"
    if scope == "group" and group_id is not None:
        return f"grp:{group_id}:{uid}"
    return None


def _lock_for(key: str) -> asyncio.Lock:
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


def _approx_tokens_text(s: str) -> int:
    return max(1, len(s) // 4)


def _approx_tokens_multimodal_list(content: list[Any]) -> int:
    """多模态不要用 repr（会把 data: base64 整段算进去），否则单条带图就会被判成天量 token，
    _trim_tokens 会删掉整条 user，LM Studio 只剩 system → Jinja「No user query found」。
    """
    n = 0
    for x in content:
        if not isinstance(x, dict):
            n += 200
            continue
        t = x.get("type")
        if t == "text":
            n += _approx_tokens_text(str(x.get("text", "")))
        elif t == "image_url":
            n += 900
        else:
            n += 100
    return max(1, n)


def _approx_tokens_content(content: object) -> int:
    if isinstance(content, str):
        return _approx_tokens_text(content)
    if isinstance(content, list):
        return _approx_tokens_multimodal_list(content)
    return 1


def _approx_tokens_messages(msgs: list[dict[str, Any]]) -> int:
    return sum(_approx_tokens_content(m.get("content")) for m in msgs)


def _trim_rounds(msgs: list[dict[str, Any]], max_rounds: int) -> None:
    if max_rounds <= 0:
        return
    cap = max_rounds * 2
    if len(msgs) <= cap:
        return
    del msgs[: len(msgs) - cap]


def _trim_tokens(msgs: list[dict[str, Any]], max_tokens: int) -> None:
    if max_tokens <= 0:
        return
    while msgs and _approx_tokens_messages(msgs) > max_tokens:
        if len(msgs) >= 2:
            del msgs[:2]
        else:
            del msgs[:1]


def _touch_session(sess: _Session, ttl: int) -> None:
    now = time.time()
    if ttl > 0 and now - sess.last_active > ttl:
        sess.messages.clear()
    sess.last_active = now


def clear_session(key: str | None) -> None:
    if not key:
        return
    if key in _sessions:
        _sessions[key].messages.clear()
        _sessions[key].last_active = time.time()


def clear_all_sessions() -> None:
    """清空所有多轮对话桶（仅当前 python 进程内生效；重启 bot 也会清空）。"""
    for sess in list(_sessions.values()):
        sess.messages.clear()
    _sessions.clear()
    _locks.clear()


def _apply_limits(msgs: list[dict[str, Any]], max_rounds: int, max_tokens: int) -> None:
    _trim_rounds(msgs, max_rounds)
    _trim_tokens(msgs, max_tokens)


class HistorySession:
    """在 async with 内对某一 key 串行更新历史。"""

    def __init__(self, key: str | None) -> None:
        self.key = key
        self._lock: asyncio.Lock | None = None
        self._sess: _Session | None = None
        self._cfg = get_history_config()

    async def __aenter__(self) -> HistorySession:
        if not self.key or not self._cfg["enable"]:
            return self
        self._lock = _lock_for(self.key)
        await self._lock.acquire()
        if self.key not in _sessions:
            _sessions[self.key] = _Session()
        self._sess = _sessions[self.key]
        _touch_session(self._sess, self._cfg["ttl"])
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._lock:
            self._lock.release()

    @property
    def active(self) -> bool:
        return bool(self.key and self._cfg["enable"] and self._sess is not None)

    def append_user(self, text: str) -> None:
        if not self.active or self._sess is None:
            return
        self._sess.messages.append({"role": "user", "content": text})
        _apply_limits(
            self._sess.messages,
            self._cfg["max_rounds"],
            self._cfg["max_tokens"],
        )

    def append_user_multimodal(self, content: list[dict[str, Any]]) -> None:
        """OpenAI 兼容多模态 user（text + image_url）。"""
        if not self.active or self._sess is None:
            return
        self._sess.messages.append({"role": "user", "content": content})
        _apply_limits(
            self._sess.messages,
            self._cfg["max_rounds"],
            self._cfg["max_tokens"],
        )

    def rollback_user(self) -> None:
        if not self.active or self._sess is None:
            return
        if self._sess.messages and self._sess.messages[-1].get("role") == "user":
            self._sess.messages.pop()

    def append_assistant(self, text: str) -> None:
        if not self.active or self._sess is None:
            return
        self._sess.messages.append({"role": "assistant", "content": text})
        _apply_limits(
            self._sess.messages,
            self._cfg["max_rounds"],
            self._cfg["max_tokens"],
        )

    def snapshot_for_api(self) -> list[dict[str, Any]]:
        if not self.active or self._sess is None:
            return []
        return [dict(m) for m in self._sess.messages]

"""LM Studio previous_response_id 存储，供 /清空 命令清空 session。"""

from __future__ import annotations

from typing import Literal

# 类型别名
ChatScope = Literal["private", "group"]

# LM Studio native API response_id 存储（每个 session key 对应一个 response_id）
_lm_response_ids: dict[str, str] = {}

# Hermes X-Hermes-Session-Id 存储（每个 session key 对应一个 session id）
_hermes_session_ids: dict[str, str] = {}

# TTL tracking: session key -> last active timestamp
_session_last_active: dict[str, float] = {}


def history_key(scope: Literal["private", "group"], user_id: str, group_id: str | None) -> str:
    """构建 session key，格式与 llm_reply.py 中的 local_key 一致。"""
    uid = str(user_id).strip()
    if scope == "private":
        return f"local:priv:{uid}"
    if scope == "group" and group_id is not None:
        return f"local:group:{group_id}:{uid}"
    return f"local:priv:{uid}"


def hermes_history_key(scope: Literal["private", "group"], user_id: str, group_id: str | None) -> str:
    """构建 Hermes session key（供 X-Hermes-Session-Id 使用）。

    与 OpenClaw 保持一致：
    - 私聊：每 QQ 号一个 session
    - 群聊：每群一个 session（全员共享上下文）
    """
    uid = str(user_id).strip()
    if scope == "private":
        return f"hermes:priv:{uid}"
    if scope == "group" and group_id is not None:
        return f"hermes:group:{group_id}"
    return f"hermes:priv:{uid}"


def clear_local_response_id(session_key: str) -> None:
    """清除指定 session 的 response_id。"""
    _lm_response_ids.pop(session_key, None)
    _session_last_active.pop(session_key, None)


def clear_local_all_response_ids() -> None:
    """清除所有 session 的 response_id。"""
    _lm_response_ids.clear()
    _session_last_active.clear()


def clear_session(key: str) -> None:
    """清空指定 session（供 /清空 命令调用）。"""
    clear_local_response_id(key)
    _hermes_session_ids.pop(key, None)


def clear_session_by_scope(scope: Literal["private", "group"], user_id: str, group_id: str | None) -> None:
    """清空 local 和 hermes 两条 session 记录（供 /清空 命令调用）。"""
    lk = history_key(scope, user_id, group_id)
    hk = hermes_history_key(scope, user_id, group_id)
    clear_local_response_id(lk)
    _hermes_session_ids.pop(hk, None)


def clear_all_sessions() -> None:
    """清空所有 session（供 /清空全部记忆 命令调用）。"""
    clear_local_all_response_ids()
    _hermes_session_ids.clear()

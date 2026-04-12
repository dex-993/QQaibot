"""根据 llm_config.ini 调用 OpenClaw（OpenResponses）或本地 OpenAI 兼容接口；支持多轮上下文。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

import openclaw_memory

from .chat_history import ChatScope, _hermes_session_ids, _lm_response_ids, hermes_history_key
from .llm_ini import get_backend, section_dict
from .reply_error_echo_guard import assistant_text_looks_like_api_error_echo

logger = logging.getLogger(__name__)


# 仅发图、无附言时占位；勿引导模型「默认描述画面」，以免压过 soul/agent 里的聊天人设
_DEFAULT_VISION_USER_TEXT = (
    "（本条只有图片、没有文字）请按 system 里的人设像平常一样自然接话；"
    "需要时可带过图里的信息，不要默认写一篇「图片里有什么」的说明文。"
)
_VISION_SYSTEM_SUFFIX = (
    "\n\n【多模态】用户消息里可能含图片：请始终沿用你的人设与语气来回复；"
    "结合对方的文字（若有）和图片来答。除非对方明确要求你描述、讲解或辨认画面内容，"
    "否则以对话接续为主，不要把整段回复写成纯画面说明。"
)


def _extract_openresponses_text(data: Any) -> str:
    """从 OpenResponses JSON 中尽量取出助手文本。"""
    if not isinstance(data, dict):
        return ""
    err = data.get("error")
    if isinstance(err, dict) and err.get("message"):
        return f"（OpenClaw：{err['message']}）"

    out = data.get("output")
    if isinstance(out, list):
        parts: list[str] = []
        for item in out:
            if not isinstance(item, dict):
                continue
            for c in item.get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "output_text" and c.get("text"):
                    parts.append(str(c["text"]))
                elif c.get("text"):
                    parts.append(str(c["text"]))
        if parts:
            return "\n".join(parts).strip()

    def walk(o: Any, depth: int = 0) -> str | None:
        if depth > 25:
            return None
        if isinstance(o, dict):
            if o.get("type") == "output_text" and o.get("text"):
                return str(o["text"])
            for v in o.values():
                r = walk(v, depth + 1)
                if r:
                    return r
        elif isinstance(o, list):
            for x in o:
                r = walk(x, depth + 1)
                if r:
                    return r
        return None

    found = walk(data.get("output"))
    if found:
        return found.strip()
    return ""



def _openclaw_resolve_agent(oc: dict[str, str]) -> str | None:
    sub = (oc.get("subagent_id") or "").strip()
    aid = (oc.get("agent_id") or "").strip()
    if sub:
        return sub
    if aid:
        return aid
    return None


def _openclaw_session_key(
    chat_scope: ChatScope,
    user_id: str,
    group_id: str | None,
    agent_id: str,
) -> str:
    """构建显式 session key，供 x-openclaw-session-key header 使用。

    格式必须为 agent:{agentId}:qqbot:group:{groupId} 或 agent:{agentId}:qqbot:c2c:{userId}
    """
    prefix = f"agent:{agent_id}:qqbot"
    if chat_scope == "private":
        return f"{prefix}:c2c:{user_id}"
    if group_id is not None:
        return f"{prefix}:group:{group_id}"
    return f"agent:{agent_id}:qqbot:c2c:{user_id}"


async def _call_openclaw(
    *,
    chat_scope: ChatScope,
    user_id: str,
    group_id: str | None,
    input_payload: str | list[Any],
    oc: dict[str, str],
    agent_id: str,
    instructions: str,
    timeout: float,
) -> tuple[bool, str]:
    base_url = _normalize_openclaw_base_url(oc.get("base_url") or "http://127.0.0.1:18790")
    token = (oc.get("token") or "").strip()
    session_key = _openclaw_session_key(chat_scope, user_id, group_id, agent_id)
    url = f"{base_url}/v1/responses"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-openclaw-session-key": session_key,
    }

    logger.info(
        "[OpenClaw] POST %s session_key=%s agent=%s",
        url, session_key, agent_id,
    )

    body: dict[str, Any] = {
        "model": "openclaw",
    }
    if instructions:
        body["instructions"] = instructions
    if isinstance(input_payload, str):
        body["input"] = input_payload
    elif isinstance(input_payload, list):
        body["input"] = input_payload
    else:
        body["input"] = str(input_payload)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
    except Exception:
        logger.exception("OpenClaw HTTP request failed")
        return False, ""

    if resp.status_code != 200:
        try:
            err_body = resp.json()
        except Exception:
            err_body = {"raw": resp.text[:500]}
        detail = ""
        if isinstance(err_body, dict):
            e = err_body.get("error", {})
            if isinstance(e, dict):
                detail = e.get("message", "")
            elif isinstance(e, str):
                detail = e
            elif err_body.get("message"):
                detail = str(err_body["message"])
        logger.warning("OpenClaw HTTP %s: %s", resp.status_code, detail or err_body)
        return False, ""

    try:
        data = resp.json()
    except Exception:
        logger.warning("OpenClaw response not JSON: %s", resp.text[:500])
        return False, ""

    text = _extract_openresponses_text(data)
    if not text:
        logger.warning("OpenClaw: no text in response: %s", str(data)[:500])
        return False, ""

    if assistant_text_looks_like_api_error_echo(text):
        logger.warning("OpenClaw reply looks like API error echo (suppressed): %s", text[:500])
        return False, ""

    return True, text


def _normalize_openclaw_base_url(url: str) -> str:
    """OpenClaw 只填 Gateway 根地址；自动去掉误粘贴的 /v1/responses、/v1 等后缀。"""
    u = url.strip().rstrip("/")
    for suffix in ("/v1/responses", "/v1/chat/completions"):
        if u.lower().endswith(suffix):
            u = u[: -len(suffix)].rstrip("/")
    if u.lower().endswith("/v1"):
        u = u[:-3].rstrip("/")
    return u


def _normalize_lm_native_url(url: str) -> str:
    """LM Studio native API URL：去掉 /v1 后缀，拼上 /api/v1/chat。"""
    u = url.strip().rstrip("/")
    for suffix in ("/v1", "/v1/chat/completions"):
        if u.lower().endswith(suffix):
            u = u[: -len(suffix)].rstrip("/")
    return f"{u}/api/v1/chat"


def _build_multimodal_user_content(
    user_text: str,
    image_data_uris: list[str],
) -> list[dict[str, Any]]:
    """先文后图：与 LM Studio 文档里 `add_user_message(text, images=...)` 一致。

    Qwen 系在 LM Studio 里用 Jinja 拼 prompt 时，常把**首段** user text 当 query；
    「图在前、文在后」会导致首轮就报 *No user query found*（与是否多轮无关）。
    """
    t = user_text.strip()
    query = t if t else _DEFAULT_VISION_USER_TEXT
    parts: list[dict[str, Any]] = [{"type": "text", "text": query}]
    for uri in image_data_uris:
        parts.append({"type": "image_url", "image_url": {"url": uri}})
    return parts


async def _call_local(
    input_payload: list[dict[str, Any]],
    system_prompt: str,
    session_key: str,
) -> tuple[bool, str]:
    loc = section_dict("local")
    base_url = _normalize_lm_native_url(
        (loc.get("base_url") or "http://127.0.0.1:1234").strip(),
    )
    api_key = (loc.get("api_key") or "lm-studio").strip()
    model = (loc.get("model") or "").strip()
    timeout = float(loc.get("timeout_seconds") or "120")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    previous_id = _lm_response_ids.get(session_key, "")
    # LM Studio /api/v1/chat input 格式：扁平数组，每个 item 是 {"type": "text", "content": "..."} 或 {"type": "image", "data_url": "..."}
    message_content: list[dict[str, Any]] = []
    for item in input_payload:
        if isinstance(item, dict) and item.get("type") == "text":
            message_content.append({"type": "text", "content": item.get("text", "")})
        elif isinstance(item, dict) and item.get("type") == "image_url":
            url = item.get("image_url", {})
            if isinstance(url, dict):
                data_url = url.get("url", "")
            else:
                data_url = str(url)
            message_content.append({"type": "image", "data_url": data_url})

    body: dict[str, Any] = {
        "model": model,
        "input": message_content,
    }
    if system_prompt:
        body["system_prompt"] = system_prompt
    if previous_id:
        body["previous_response_id"] = previous_id

    logger.info("[Local] POST %s previous_id=%s", base_url, previous_id or "(none)")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(base_url, headers=headers, json=body)
    except Exception:
        logger.exception("Local LLM HTTP request failed")
        return False, ""

    if resp.status_code != 200:
        logger.warning(
            "Local LLM HTTP %s: %s",
            resp.status_code,
            resp.text[:500],
        )
        return False, ""

    try:
        data = resp.json()
    except Exception:
        logger.warning("Local LLM response not JSON: %s", resp.text[:500])
        return False, ""

    # 提取文本回复
    text = ""
    output = data if isinstance(data, dict) else {}
    for item in output.get("output", []):
        if isinstance(item, dict) and item.get("type") == "message":
            content = item.get("content")
            # content 可能是字符串或列表；字符串直接取，列表才遍历
            if isinstance(content, str) and content.strip():
                text = content.strip()
                break
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        t = (c.get("text") or "").strip()
                        if t:
                            text = t
                            break
                if text:
                    break

    if not text:
        logger.warning("Local LLM returned empty content")
        return False, ""

    if assistant_text_looks_like_api_error_echo(text):
        logger.warning(
            "Local LLM reply looks like API/HTTP error echo (suppressed): %s",
            text[:500],
        )
        return False, ""

    # 保存 response_id 供下次调用
    resp_id = (data.get("response_id") or "") if isinstance(data, dict) else ""
    if resp_id:
        _lm_response_ids[session_key] = resp_id

    return True, text


def _hermes_flatten_user_content(content: object) -> str:
    """Hermes 仅走文本：多模态 user content 只取 text 段。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for x in content:
            if isinstance(x, dict) and x.get("type") == "text":
                texts.append(str(x.get("text", "")))
        return "\n".join(texts) or "（本条含图片，暂不按图理解）"
    return ""


async def _call_hermes(
    messages: list[dict[str, Any]],
    session_key: str,
    timeout: float,
) -> tuple[bool, str]:
    """调用 Hermes Agent 的 OpenAI 兼容 /v1/chat/completions 接口。"""
    hm = section_dict("hermes")
    base_url = (hm.get("base_url") or "http://192.168.115.128:8642").strip().rstrip("/")
    api_key = (hm.get("api_key") or "").strip()
    model = (hm.get("model") or "").strip()
    url = f"{base_url}/v1/chat/completions"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # X-Hermes-Session-Id：多轮上下文由服务端维护
    session_id = _hermes_session_ids.get(session_key, "")
    if session_id:
        headers["X-Hermes-Session-Id"] = session_id

    body: dict[str, Any] = {"stream": False}
    if model:
        body["model"] = model
    body["messages"] = messages

    logger.info("[Hermes] POST %s session_id=%s", url, session_id or "(new)")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
    except Exception:
        logger.exception("Hermes HTTP request failed")
        return False, ""

    if resp.status_code != 200:
        logger.warning("Hermes HTTP %s: %s", resp.status_code, resp.text[:500])
        return False, ""

    try:
        data = resp.json()
    except Exception:
        logger.warning("Hermes response not JSON: %s", resp.text[:500])
        return False, ""

    # 提取 assistant 回复
    text = ""
    choices = data.get("choices") if isinstance(data, dict) else []
    if isinstance(choices, list) and choices:
        first = choices[0]
        msg = first.get("message") if isinstance(first, dict) else {}
        if isinstance(msg, dict):
            text = (msg.get("content") or "").strip()

    if not text:
        logger.warning("Hermes returned empty content: %s", str(data)[:500])
        return False, ""

    if assistant_text_looks_like_api_error_echo(text):
        logger.warning("Hermes reply looks like API error echo (suppressed): %s", text[:500])
        return False, ""

    # 保存 session id 供下次请求
    new_session = resp.headers.get("X-Hermes-Session-Id") or ""
    if new_session:
        _hermes_session_ids[session_key] = new_session

    return True, text


def _openclaw_flatten_user_content(content: object) -> str:
    """OpenClaw 仅走文本：多模态 user 只取 text 段。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for x in content:
            if isinstance(x, dict) and x.get("type") == "text":
                texts.append(str(x.get("text", "")))
        return "\n".join(texts) or "（本条含图片，OpenClaw 路径暂不按图理解）"
    return ""


def _prepend_sender_label(
    content: object,
    sender_label: str,
) -> object:
    """把发送者身份标签拼到消息内容最前面。"""
    if isinstance(content, str):
        return f"{sender_label}\n{content}"
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                item["text"] = f"{sender_label}\n{item.get('text', '')}"
                return content
        if content:
            first = dict(content[0]) if content else {}
            if isinstance(first, dict):
                ct = first.get("content", "")
                first["content"] = f"{sender_label}\n{ct}"
                return [first] + list(content[1:])
    return content


async def reply_with_configured_llm(
    user_text: str,
    user_id: str,
    *,
    chat_scope: ChatScope = "private",
    group_id: str | None = None,
    image_data_uris: list[str] | None = None,
    sender_label: str = "",
) -> str:
    """按 backend 路由，多轮上下文由各后端自行维护（OpenClaw/Hermes=session key，LM Studio=response_id）。"""

    uris = [u for u in (image_data_uris or []) if u]
    backend = get_backend()

    if backend == "openclaw":
        oc = section_dict("openclaw")

        resolved = _openclaw_resolve_agent(oc)
        if resolved is None:
            logger.error(
                "OpenClaw: subagent_id and agent_id both missing (user_id=%s)",
                user_id,
            )
            return ""

        agent_id = resolved
        timeout = float(oc.get("timeout_seconds") or "120")

        base_instr = (oc.get("instructions") or "").strip()
        if chat_scope == "group":
            group_suffix = (oc.get("group_instructions_suffix") or "").strip()
            instr = base_instr
            if group_suffix:
                instr = (base_instr + "\n\n" + group_suffix) if base_instr else group_suffix
        else:
            instr = base_instr

        # 只需发当前消息，上下文由 OpenClaw session 维护
        current_text = _openclaw_flatten_user_content(
            _prepend_sender_label(user_text, sender_label) if sender_label else user_text
        )
        ok, reply = await _call_openclaw(
            chat_scope=chat_scope,
            user_id=user_id,
            group_id=group_id,
            input_payload=current_text,
            oc=oc,
            agent_id=agent_id,
            instructions=instr,
            timeout=timeout,
        )
    elif backend == "hermes":
        hm = section_dict("hermes")
        base_system = (hm.get("system_prompt") or "你是一个友好的聊天助手。").strip()
        if chat_scope == "group":
            group_suffix = (hm.get("group_system_suffix") or "").strip()
            if group_suffix:
                base_system = (base_system + "\n\n" + group_suffix) if base_system else group_suffix
        timeout = float(hm.get("timeout_seconds") or "120")

        # 提取用户文本（图片暂不支持）
        user_raw = _hermes_flatten_user_content(
            _prepend_sender_label(user_text, sender_label) if sender_label else user_text
        )
        messages: list[dict[str, str]] = [{"role": "user", "content": user_raw}]
        hermes_key = hermes_history_key(chat_scope, user_id, group_id)
        ok, reply = await _call_hermes(messages, session_key=hermes_key, timeout=timeout)
    else:
        loc = section_dict("local")
        base_system = (loc.get("system_prompt") or "你是一个友好的聊天助手。").strip()
        ocw = openclaw_memory.get_workspace_bundle()
        if ocw:
            base_system = (
                f"{base_system}\n\n---\n【工作区记忆（soul.md / agent.md，已排除 USER.md）】\n"
                f"{ocw}"
            )
        if uris:
            base_system = base_system + _VISION_SYSTEM_SUFFIX
        input_payload: list[dict[str, Any]] = []
        if uris:
            raw_content = _build_multimodal_user_content(user_text, uris)
        else:
            raw_content = [{"type": "text", "text": user_text}]
        # 群聊时标注发送者身份，让模型知道"谁在说话"
        labeled = _prepend_sender_label(raw_content, sender_label) if sender_label else raw_content
        if isinstance(labeled, list):
            input_payload = labeled
        else:
            input_payload = [{"type": "text", "text": str(labeled)}]
        local_key = f"local:{chat_scope}:{user_id}" + (f":{group_id}" if group_id else "")
        ok, reply = await _call_local(input_payload, base_system, session_key=local_key)

    text_out = (reply or "").strip() if ok else ""
    if not text_out and ok:
        logger.warning(
            "LLM returned empty reply after success (user_id=%s scope=%s)",
            user_id,
            chat_scope,
        )

    return text_out

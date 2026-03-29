"""把 QQ「引用/回复」链中的信息并入发给模型的 user prompt（文字 + 可选图片）。"""

from __future__ import annotations

from nonebot.adapters.onebot.v11.event import Reply

_QUOTED_TEXT_MAX = 3500


def quoted_reply_to_text_prefix(reply: Reply | None) -> str:
    """将被引消息的发送者与正文写入前缀（不含图片；图片由 resolve_images_from_message 另行传入）。"""
    if reply is None:
        return ""
    sender = reply.sender
    uid = getattr(sender, "user_id", None)
    nick = (getattr(sender, "nickname", None) or "").strip()
    card = (getattr(sender, "card", None) or "").strip()
    name = card or nick or (str(uid) if uid is not None else "未知")
    try:
        qtext = reply.message.extract_plain_text().strip()
    except Exception:
        qtext = ""
    if len(qtext) > _QUOTED_TEXT_MAX:
        qtext = qtext[:_QUOTED_TEXT_MAX] + "\n…[引用正文已截断]"
    head = f"【被引用消息】发送者：{name}（QQ {uid}）"
    if qtext:
        body = f"正文：{qtext}"
    else:
        body = "正文：（该条无可见文字；若同步传了多张图，靠前的图为被引用消息中的图，靠后的图为你本条消息中的图）"
    return f"{head}\n{body}\n——\n"


def build_user_prompt_with_quote(prefix: str, user_plain: str) -> str:
    """prefix 来自 quoted_reply_to_text_prefix；user_plain 为本条 get_plaintext。"""
    tail = user_plain.strip() if user_plain.strip() else "（本条未另附文字）"
    if prefix:
        return f"{prefix}【用户本条】\n{tail}"
    return tail

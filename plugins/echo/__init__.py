"""NapCat ↔ NoneBot；群聊白名单 + @ / 引用机器人；回复由 llm_config.ini 选择 OpenClaw 或本地模型。"""

import logging
import random

from nonebot import on_message, on_notice
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
    PokeNotifyEvent,
    PrivateMessageEvent,
)
from nonebot.rule import Rule

from .chat_history import clear_all_sessions, clear_session, history_key
from .llm_ini import (
    get_backend,
    get_group_empty_at_replies,
    memory_clear_master_qq_ids,
    model_supports_vision,
    openclaw_private_allowed,
)
from .message_image import (
    merge_vision_image_uris,
    message_has_image,
    resolve_images_from_message,
)
from .llm_reply import reply_with_configured_llm
from .quoted_context import build_user_prompt_with_quote, quoted_reply_to_text_prefix
from .tts import cleanup_temp_file, synthesize_speech, tts_is_available
from .whitelist import load_group_ids

logger = logging.getLogger(__name__)


def _private_only() -> Rule:
    async def _check(event: MessageEvent) -> bool:
        return isinstance(event, PrivateMessageEvent)

    return Rule(_check)


def _group_whitelist_only() -> Rule:
    """群聊：仅白名单群进入处理器；是否 @ / 回复机器人等在 handler 里二次判断。"""

    async def _check(event: MessageEvent) -> bool:
        if not isinstance(event, GroupMessageEvent):
            return False
        try:
            gid = int(event.group_id)
        except (TypeError, ValueError):
            return False
        return gid in load_group_ids()

    return Rule(_check)


def _poke_only() -> Rule:
    async def _check(event) -> bool:
        return isinstance(event, PokeNotifyEvent)

    return Rule(_check)


def _has_at_bot(event: GroupMessageEvent, self_id: str) -> bool:
    """扫描整条 message 中的 at（NoneBot 默认只认首尾 @，中间 @ 不会置 to_me）。"""
    for seg in event.message:
        if seg.type != "at":
            continue
        qq = seg.data.get("qq")
        if qq is None or str(qq) == "all":
            continue
        if str(qq) == self_id:
            return True
    return False


def _reply_to_bot_message(bot: Bot, event: GroupMessageEvent) -> bool:
    """本条是否引用/回复的是机器人自己发的消息。"""
    rep = getattr(event, "reply", None)
    if rep is None:
        return False
    uid = getattr(rep.sender, "user_id", None)
    return uid is not None and str(uid) == str(bot.self_id)


def _is_addressed_to_bot(bot: Bot, event: GroupMessageEvent) -> bool:
    """是否视为群内在叫你：与「仅 @」一致覆盖「回复 + @」等 NTQQ 形态。

    - ``is_tome()``：含 NoneBot 对「引用机器人消息」等置位。
    - ``event.reply``：引用原消息的发送者为本机器人时，与 @ 你等价（回复+仅引用你，无单独 at 段时）。
    - 全段扫描 ``at``：形如 ``[reply][@机器人][正文]`` 时 to_me 常为 False，必须与纯 @ 一样能触发。
    """
    self_id = str(bot.self_id)
    if event.is_tome():
        return True
    rep = getattr(event, "reply", None)
    if rep is not None:
        uid = getattr(rep.sender, "user_id", None)
        if uid is not None and str(uid) == self_id:
            return True
    return _has_at_bot(event, self_id)


def _group_empty_prompt_no_text_no_image(
    bot: Bot,
    event: GroupMessageEvent,
    text_plain: str,
    has_img: bool,
) -> bool:
    """群聊：本条无纯文字、无图；且为「仅 @」或「仅回复机器人」（视同 reply+@ 的空触发）。"""
    if text_plain or has_img:
        return False
    rep = getattr(event, "reply", None)
    if rep is None:
        return True
    return _reply_to_bot_message(bot, event)


_priv = on_message(rule=_private_only(), priority=10, block=False)


@_priv.handle()
async def _(bot: Bot, event: PrivateMessageEvent) -> None:
    text_plain = event.get_plaintext().strip()
    has_img = message_has_image(event)
    rep = getattr(event, "reply", None)
    if not text_plain and not has_img and rep is None:
        return
    if text_plain.lower() in ("/清空", "/clear"):
        clear_session(history_key("private", str(event.user_id), None))
        await bot.send(event, "已清空你的私聊对话记忆。")
        return
    if text_plain == "/清空全部记忆":
        masters = memory_clear_master_qq_ids()
        uid = str(event.user_id)
        if masters and uid in masters:
            clear_all_sessions()
            await bot.send(event, "已清空所有会话的多轮记忆（内存）。")
        elif masters:
            logger.warning(
                "Rejected /清空全部记忆: user_id=%s not in memory_clear_master_qq",
                uid,
            )
        return
    prefix = quoted_reply_to_text_prefix(rep)
    quoted_uris: list[str] = []
    if rep is not None and model_supports_vision() and get_backend() == "local":
        quoted_uris = await resolve_images_from_message(bot, rep.message)
    curr_uris: list[str] = []
    if has_img and model_supports_vision() and get_backend() == "local":
        curr_uris = await resolve_images_from_message(bot, event.message)
    merged_uris = merge_vision_image_uris(quoted_uris, curr_uris)
    full_text = build_user_prompt_with_quote(prefix, text_plain)

    if has_img and not model_supports_vision() and not text_plain.strip():
        return
    if has_img and get_backend() != "local" and not text_plain.strip():
        return
    if has_img and model_supports_vision() and get_backend() == "local":
        if not curr_uris and not quoted_uris and not text_plain.strip():
            logger.warning(
                "Private message: vision enabled but no image URIs resolved (user_id=%s)",
                event.user_id,
            )
            return
    if len(full_text) > 8000:
        logger.warning(
            "Private message too long: %d chars (user_id=%s)",
            len(full_text),
            event.user_id,
        )
        return
    if get_backend() == "openclaw" and not openclaw_private_allowed(str(event.user_id)):
        return

    reply = await reply_with_configured_llm(
        full_text,
        str(event.user_id),
        chat_scope="private",
        group_id=None,
        image_data_uris=merged_uris or None,
        sender_label=f"【私聊消息 | 发送者：{event.sender.nickname or str(event.user_id)}（QQ {event.user_id}）】",
    )
    if not (reply or "").strip():
        return

    # TTS：优先发语音，超时/失败降级为文字
    if tts_is_available():
        audio_path, is_silk = await synthesize_speech(reply)
        if audio_path:
            try:
                await bot.send(event, MessageSegment.record(file=audio_path))
                cleanup_temp_file(audio_path)
                return
            except Exception:
                cleanup_temp_file(audio_path)
                logger.warning("voice send failed, falling back to text")
    await bot.send(event, reply)


_grp = on_message(rule=_group_whitelist_only(), priority=10, block=False)


@_grp.handle()
async def _(bot: Bot, event: GroupMessageEvent) -> None:
    if not _is_addressed_to_bot(bot, event):
        return
    text_plain = event.get_plaintext().strip()
    has_img = message_has_image(event)
    rep = getattr(event, "reply", None)
    if _group_empty_prompt_no_text_no_image(bot, event, text_plain, has_img):
        lines = get_group_empty_at_replies()
        msg = (
            random.choice(lines)
            if lines
            else "请 @ 我之后输入要聊的内容（仅 @ 没有文字时我不会调用模型）。"
        )
        await bot.send(event, MessageSegment.reply(event.message_id) + msg)
        return
    if text_plain.lower() in ("/清空", "/clear"):
        clear_session(
            history_key("group", str(event.user_id), str(event.group_id)),
        )
        await bot.send(event, MessageSegment.reply(event.message_id) + "已清空你在本群的对话记忆。")
        return
    prefix = quoted_reply_to_text_prefix(rep)
    quoted_uris: list[str] = []
    if rep is not None and model_supports_vision() and get_backend() == "local":
        quoted_uris = await resolve_images_from_message(bot, rep.message)
    curr_uris: list[str] = []
    if has_img and model_supports_vision() and get_backend() == "local":
        curr_uris = await resolve_images_from_message(bot, event.message)
    merged_uris = merge_vision_image_uris(quoted_uris, curr_uris)
    full_text = build_user_prompt_with_quote(prefix, text_plain)

    if has_img and not model_supports_vision() and not text_plain.strip():
        return
    if has_img and get_backend() != "local" and not text_plain.strip():
        return
    if has_img and model_supports_vision() and get_backend() == "local":
        if not curr_uris and not quoted_uris and not text_plain.strip():
            logger.warning(
                "Group message: vision enabled but no image URIs resolved "
                "(group_id=%s user_id=%s)",
                event.group_id,
                event.user_id,
            )
            return
    if len(full_text) > 8000:
        logger.warning(
            "Group message too long: %d chars (group_id=%s user_id=%s)",
            len(full_text),
            event.group_id,
            event.user_id,
        )
        return
    reply = await reply_with_configured_llm(
        full_text,
        str(event.user_id),
        chat_scope="group",
        group_id=str(event.group_id),
        image_data_uris=merged_uris or None,
        sender_label=f"【群消息 | 发送者：{event.sender.card or event.sender.nickname or str(event.user_id)}（QQ {event.user_id}）】",
    )
    if not (reply or "").strip():
        return

    # TTS：优先发语音，超时/失败降级为文字
    if tts_is_available():
        logger.info("[TTS] synthesizing voice (len=%d)", len(reply))
        audio_path, is_silk = await synthesize_speech(reply)
        if audio_path:
            try:
                # 语音不走 reply 段，直接发语音
                await bot.send(event, MessageSegment.record(file=audio_path))
                cleanup_temp_file(audio_path)
                return
            except Exception:
                cleanup_temp_file(audio_path)
                logger.warning("group voice send failed, falling back to text")
        else:
            logger.info("[TTS] synthesize returned empty, sending text")
    else:
        logger.info("[TTS] not available, sending text")
    await bot.send(event, MessageSegment.reply(event.message_id) + reply)


_poke = on_notice(rule=_poke_only(), priority=10, block=False)


@_poke.handle()
async def _(bot: Bot, event: PokeNotifyEvent) -> None:
    if not event.is_tome():
        return
    if event.group_id is not None:
        try:
            gid = int(event.group_id)
        except (TypeError, ValueError):
            return
        if gid not in load_group_ids():
            return
    elif get_backend() == "openclaw" and not openclaw_private_allowed(
        str(event.user_id),
    ):
        return
    await bot.send(event, "别戳啦～看到啦！")

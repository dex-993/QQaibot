"""从 OneBot 消息中解析图片，压缩后转为 JPEG data URI，供本地 vision 模型使用。"""

from __future__ import annotations

import base64
import logging
from io import BytesIO

import httpx
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent
from PIL import Image, ImageOps

from .llm_ini import get_local_vision_image_limits

logger = logging.getLogger(__name__)

MAX_IMAGES_PER_MESSAGE = 6
# 下载原图单张上限（与 vision_max_image_bytes 无关，防止异常链接撑爆内存）
_RAW_FETCH_MAX_BYTES = 200 * 1024 * 1024


def message_has_image(event: MessageEvent) -> bool:
    return any(seg.type == "image" for seg in event.message)


def _decode_data_uri_to_bytes(uri: str) -> bytes | None:
    if not uri.startswith("data:"):
        return None
    try:
        header, rest = uri.split(",", 1)
        if ";base64" not in header:
            return None
        return base64.b64decode(rest)
    except Exception:
        return None


def _to_rgb(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode == "RGB":
        return im
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        return bg
    if im.mode == "P":
        return _to_rgb(im.convert("RGBA"))
    return im.convert("RGB")


def compress_image_to_fit(
    raw: bytes,
    max_bytes: int,
    quality: int,
    *,
    max_long_edge: int = 0,
) -> bytes | None:
    """将任意常见格式压成 JPEG。

    `max_long_edge>0`：先按比例缩小使 **max(宽,高) ≤ max_long_edge**（缓解本地视觉栈对超大分辨率的 400）。
    `max_bytes<=0`：不限制体积（仅转码）；`>0` 则尽量压到该字节数以下。
    """
    try:
        im = Image.open(BytesIO(raw))
    except Exception as e:
        logger.warning("PIL cannot open image: %s", e)
        return None
    if getattr(im, "n_frames", 1) > 1:
        im.seek(0)
    im.load()
    im = _to_rgb(im)
    w0, h0 = im.size
    if w0 < 1 or h0 < 1:
        return None

    if max_long_edge > 0:
        m = max(w0, h0)
        if m > max_long_edge:
            scale = max_long_edge / m
            nw = max(1, int(w0 * scale))
            nh = max(1, int(h0 * scale))
            im = im.resize((nw, nh), Image.Resampling.LANCZOS)
            w0, h0 = im.size

    if max_bytes <= 0:
        buf = BytesIO()
        q = min(95, max(1, quality))
        im.save(buf, format="JPEG", quality=q, optimize=True)
        return buf.getvalue()

    q0 = min(95, max(40, quality))
    last: bytes | None = None
    for q in range(q0, 35, -8):
        scale = 1.0
        for _ in range(32):
            w = max(1, int(w0 * scale))
            h = max(1, int(h0 * scale))
            cur = im if scale >= 0.999 else im.resize((w, h), Image.Resampling.LANCZOS)
            buf = BytesIO()
            cur.save(buf, format="JPEG", quality=q, optimize=True)
            jpeg = buf.getvalue()
            last = jpeg
            if len(jpeg) <= max_bytes:
                return jpeg
            if min(w, h) <= 24:
                break
            scale *= 0.82

    if last is not None and len(last) > max_bytes:
        logger.warning(
            "image still %d bytes after resize (max_bytes=%d), sending best effort",
            len(last),
            max_bytes,
        )
    return last


async def _fetch_url_bytes(url: str) -> bytes | None:
    if url.startswith("data:"):
        return _decode_data_uri_to_bytes(url)
    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            body = r.content
            if len(body) > _RAW_FETCH_MAX_BYTES:
                logger.warning("downloaded image too large (%d bytes), skip", len(body))
                return None
            return body
    except Exception as e:
        logger.warning("fetch image url failed: %s", e)
        return None


def _base64_cq_to_bytes(file_field: str) -> bytes | None:
    raw = file_field.strip()
    if not raw.startswith("base64://"):
        return None
    raw = raw[len("base64://") :]
    if not raw:
        return None
    try:
        return base64.b64decode(raw)
    except Exception:
        return None


def _bytes_to_jpeg_data_uri(jpeg: bytes) -> str:
    b64 = base64.b64encode(jpeg).decode()
    return f"data:image/jpeg;base64,{b64}"


async def _resolve_segment_to_jpeg_uri(
    bot: Bot,
    data: dict[str, str],
    max_bytes: int,
    jpeg_quality: int,
    max_long_edge: int,
) -> str | None:
    url = (data.get("url") or "").strip()
    file = (data.get("file") or "").strip()
    raw: bytes | None = None

    if url.startswith(("http://", "https://")):
        raw = await _fetch_url_bytes(url)
    elif file.startswith(("http://", "https://")):
        raw = await _fetch_url_bytes(file)
    elif file.startswith("base64://"):
        raw = _base64_cq_to_bytes(file)
    elif file:
        try:
            ret = await bot.call_api("get_image", file=file)
        except Exception as e:
            logger.warning("get_image failed file=%s: %s", file[:80], e)
            ret = None
        if isinstance(ret, dict):
            u = (ret.get("url") or "").strip()
            b64 = (ret.get("base64") or ret.get("data") or "").strip()
            if u.startswith(("http://", "https://")):
                raw = await _fetch_url_bytes(u)
            elif b64:
                try:
                    raw = base64.b64decode(b64)
                except Exception:
                    raw = None
    if raw is None:
        return None
    jpeg = compress_image_to_fit(
        raw,
        max_bytes,
        jpeg_quality,
        max_long_edge=max_long_edge,
    )
    if not jpeg:
        return None
    return _bytes_to_jpeg_data_uri(jpeg)


async def resolve_message_images(bot: Bot, event: MessageEvent) -> list[str]:
    """返回若干 JPEG `data:image/jpeg;base64,...`，受 `vision_max_*` 约束。"""
    return await resolve_images_from_message(bot, event.message)


def merge_vision_image_uris(quoted: list[str], current: list[str]) -> list[str]:
    """先被引用消息中的图，再本条消息中的图；总额不超过 MAX_IMAGES_PER_MESSAGE。"""
    out: list[str] = []
    for u in quoted:
        if len(out) >= MAX_IMAGES_PER_MESSAGE:
            break
        if u:
            out.append(u)
    for u in current:
        if len(out) >= MAX_IMAGES_PER_MESSAGE:
            break
        if u:
            out.append(u)
    return out


async def resolve_images_from_message(bot: Bot, message: Message) -> list[str]:
    """解析任意 Message 中的图片段（用于 event.reply.message）。"""
    cfg = get_local_vision_image_limits()
    max_b = cfg["max_bytes"]
    q = cfg["jpeg_quality"]
    edge = cfg["max_long_edge"]
    out: list[str] = []
    for seg in message:
        if seg.type != "image":
            continue
        if len(out) >= MAX_IMAGES_PER_MESSAGE:
            break
        uri = await _resolve_segment_to_jpeg_uri(bot, seg.data or {}, max_b, q, edge)
        if uri:
            out.append(uri)
    return out

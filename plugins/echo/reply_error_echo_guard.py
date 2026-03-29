"""识别助手回复是否像在复述 HTTP/API 错误正文（非真实 HTTP 头）。

本地栈在 **HTTP 200** 时仍可能把错误信息写在 `content` 里；用户要求不向 QQ 发送这类内容。"""
from __future__ import annotations

import re
from typing import Pattern

# 子串/短语：典型网关或 OpenAI 兼容错误复述（大小写不敏感）
_PHRASES: tuple[str, ...] = (
    "bad request",
    "request entity too large",
    "uri too long",
    "unsupported media type",
    "unprocessable entity",
    "too many requests",
    "internal server error",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "request timeout",
    "invalid request",
    "malformed request",
    "invalid json",
    "failed to parse",
    "error code",
    "status code",
    "http status",
    "api error",
    "openai api",
    "request failed",
    "connection refused",
    "connection reset",
    "请求失败",
    "错误代码",
    "状态码",
    "无效请求",
)

# 正则：更贴近整句错误行，减少口语误杀
_COMPILED: list[Pattern[str]] = [
    re.compile(r"HTTP/\d+\.\d+\s+[45]\d\d\b", re.IGNORECASE),
    re.compile(r"\b[45]\d\d\s+(Bad Request|Unauthorized|Forbidden|Not Found)\b", re.IGNORECASE),
    re.compile(r"\b(err(or)?_?code|status)\s*[:=]\s*[45]\d\d\b", re.IGNORECASE),
    re.compile(r"\binvalid_request_error\b", re.IGNORECASE),
    re.compile(r'["\']error["\']\s*:\s*\{', re.IGNORECASE),
    re.compile(r"\bmissing required|required field|must be (a )?valid\b", re.IGNORECASE),
]


def assistant_text_looks_like_api_error_echo(text: str) -> bool:
    """若正文像在复述 4xx/5xx 或常见 API 报错骨架，返回 True（应丢弃回复、只打日志）。"""
    if not text or not str(text).strip():
        return False
    s = str(text).strip()
    low = s.lower()

    for p in _PHRASES:
        if p in low:
            return True

    for rx in _COMPILED:
        if rx.search(s):
            return True

    return False

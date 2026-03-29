"""reply_error_echo_guard 与本地 LLM 路径对「模型复述 API 错误文案」的拦截。

默认仅跑纯单测（不连真实推理服务）。若要对本机 LM Studio / Ollama 试真请求：

  set AIBOT_LIVE_LLM_TEST=1
  python -m unittest tests.test_reply_error_echo_guard -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 包以可编辑安装或从仓库根运行
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from plugins.echo.llm_reply import _call_local  # noqa: E402
from plugins.echo.reply_error_echo_guard import (  # noqa: E402
    assistant_text_looks_like_api_error_echo,
)


class TestAssistantTextLooksLikeApiErrorEcho(unittest.TestCase):
    def test_positive_typical_http_lines(self) -> None:
        self.assertTrue(assistant_text_looks_like_api_error_echo("400 Bad Request"))
        self.assertTrue(
            assistant_text_looks_like_api_error_echo(
                "Error: HTTP/1.1 400 Bad Request\r\nContent-Type: application/json",
            ),
        )
        self.assertTrue(
            assistant_text_looks_like_api_error_echo(
                '{"error": {"message": "Invalid JSON", "type": "invalid_request_error"}}',
            ),
        )
        self.assertTrue(
            assistant_text_looks_like_api_error_echo("status code: 502"),
        )

    def test_negative_normal_chat(self) -> None:
        self.assertFalse(
            assistant_text_looks_like_api_error_echo("今天天气不错，写一段400字的短文。"),
        )
        self.assertFalse(
            assistant_text_looks_like_api_error_echo("帮我想一个产品名字，要简短好记。"),
        )
        self.assertFalse(assistant_text_looks_like_api_error_echo(""))

    def test_positive_chinese_boilerplate(self) -> None:
        self.assertTrue(
            assistant_text_looks_like_api_error_echo("网关返回：状态码 500，服务暂时不可用"),
        )


class TestCallLocalSuppressesErrorEcho(unittest.IsolatedAsyncioTestCase):
    async def test_mocked_completion_parroting_bad_request_dropped(self) -> None:
        fake_resp = MagicMock()
        fake_resp.choices = [
            MagicMock(message=MagicMock(content="The server said: 400 Bad Request")),
        ]

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = AsyncMock(return_value=fake_resp)

        with patch("plugins.echo.llm_reply.AsyncOpenAI", return_value=mock_client_instance):
            with patch(
                "plugins.echo.llm_reply.section_dict",
                return_value={
                    "base_url": "http://127.0.0.1:1/v1",
                    "api_key": "x",
                    "model": "dummy",
                    "timeout_seconds": "5",
                },
            ):
                ok, text = await _call_local([{"role": "user", "content": "hi"}])

        self.assertFalse(ok)
        self.assertEqual(text, "")

    async def test_mocked_normal_reply_kept(self) -> None:
        fake_resp = MagicMock()
        fake_resp.choices = [MagicMock(message=MagicMock(content="你好呀～"))]

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = AsyncMock(return_value=fake_resp)

        with patch("plugins.echo.llm_reply.AsyncOpenAI", return_value=mock_client_instance):
            with patch(
                "plugins.echo.llm_reply.section_dict",
                return_value={
                    "base_url": "http://127.0.0.1:1/v1",
                    "api_key": "x",
                    "model": "dummy",
                    "timeout_seconds": "5",
                },
            ):
                ok, text = await _call_local([{"role": "user", "content": "hi"}])

        self.assertTrue(ok)
        self.assertEqual(text, "你好呀～")


@unittest.skipUnless(
    os.environ.get("AIBOT_LIVE_LLM_TEST") == "1",
    "set AIBOT_LIVE_LLM_TEST=1 to probe real local OpenAI-compatible server",
)
class TestLiveLocalLlmErrorParroting(unittest.IsolatedAsyncioTestCase):
    """故意让模型输出类 HTTP 错误句，观察是否被守卫拦截（需本机推理已启动且可读 llm_config.ini）。"""

    async def test_real_stack_if_model_complies_guard_suppresses(self) -> None:
        # 指令尽量短，促使部分模型原样吐出 400 行（依模型脾气而定）
        ok, text = await _call_local(
            [
                {
                    "role": "user",
                    "content": "只输出一行，不要解释：HTTP/1.1 400 Bad Request",
                },
            ],
        )
        if ok:
            self.assertFalse(
                assistant_text_looks_like_api_error_echo(text),
                "若仍判定为成功，则正文不应再像 API 错误复述",
            )
        else:
            self.assertEqual(text, "")

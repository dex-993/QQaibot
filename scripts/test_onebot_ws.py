"""测试与 NapCat 正向 WebSocket 的握手（与 NoneBot 使用方式一致）。"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _tcp_probe(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True, "ok"
    except OSError as e:
        return False, str(e)
    finally:
        s.close()


async def _try_ws(uri: str, headers: list[tuple[str, str]]) -> None:
    import websockets

    print(f"  WebSocket: {uri}")
    try:
        async with websockets.connect(
            uri,
            additional_headers=headers or None,
            open_timeout=15.0,
        ) as ws:
            print("  -> handshake OK")
            try:
                first = await asyncio.wait_for(ws.recv(), timeout=5.0)
                preview = first[:300] + ("..." if len(first) > 300 else "")
                print(f"  -> first frame: {preview!r}")
            except asyncio.TimeoutError:
                print("  -> no data in 5s (may still be OK)")
    except Exception as e:
        print(f"  -> FAIL: {type(e).__name__}: {e}")


async def main() -> None:
    load_dotenv(_PROJECT_ROOT / ".env")
    raw = os.getenv("ONEBOT_WS_URLS", '["ws://127.0.0.1:18881"]')
    try:
        urls = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[error] ONEBOT_WS_URLS is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(urls, list) or not urls:
        print("[error] ONEBOT_WS_URLS must be a non-empty JSON array", file=sys.stderr)
        sys.exit(1)

    token = (os.getenv("ONEBOT_ACCESS_TOKEN") or "").strip()
    headers: list[tuple[str, str]] = []
    if token:
        headers.append(("Authorization", f"Bearer {token}"))
        print("[info] Using ONEBOT_ACCESS_TOKEN (Bearer header)")
    else:
        print("[info] ONEBOT_ACCESS_TOKEN empty (match NapCat with no token)")

    host, port = "127.0.0.1", 18881
    for u in urls:
        if "127.0.0.1" in u or "localhost" in u:
            # 从 URL 粗取端口用于 TCP 探测
            try:
                from urllib.parse import urlparse

                p = urlparse(u)
                if p.port:
                    port = p.port
                host = p.hostname or host
            except Exception:
                pass
            break

    ok, tcp_msg = _tcp_probe(host, port)
    print(f"\nTCP connect {host}:{port} -> {'OK' if ok else 'FAIL'} ({tcp_msg})\n")
    if not ok:
        print(
            "[hint] Nothing is accepting TCP on this port. Start NapCat first, "
            "or fix host/port to match the NapCat forward-WS listener.",
        )
        sys.exit(2)

    # Same URLs as .env
    for u in urls:
        await _try_ws(u, headers)

    # Optional alternate paths if root fails (compare with NapCat UI path)
    base = urls[0].rstrip("/")
    alts = [f"{base}/", f"{base}/ws", f"{base}/onebot/v11/ws"]
    print("\n[optional] try common sub-paths (only if root URL fails and UI shows a path)")
    for alt in alts:
        if alt.rstrip("/") == urls[0].rstrip("/"):
            continue
        await _try_ws(alt, headers)


if __name__ == "__main__":
    asyncio.run(main())

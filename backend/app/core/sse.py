"""SSE 协议工具（对话流等）；不使用 ApiResult 包裹每一帧。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, Literal

from starlette.responses import StreamingResponse

SseEventName = Literal["meta", "delta", "tool_call", "error", "done"]

SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

PING_INTERVAL_SEC = 15


def format_sse(event: SseEventName | str, data: Mapping[str, Any] | None = None) -> str:
    """编码一帧 SSE；data 为 JSON 对象。"""
    payload = json.dumps(data or {}, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def format_sse_ping() -> str:
    """注释行心跳，约每 15s 发送一次。"""
    return ": ping\n\n"


def format_sse_error(*, code: str, message: str, **extra: Any) -> str:
    """错误帧：至少含 code / message，与 REST 失败语义一致。"""
    body: dict[str, Any] = {"code": code, "message": message}
    body.update(extra)
    return format_sse("error", body)


def sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    """构造 text/event-stream 响应。"""
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )

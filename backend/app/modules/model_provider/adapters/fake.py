"""假适配器：本地联调 / 无密钥时产出固定流式 token。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.modules.model_provider.adapters.base import (
    ChatRequest,
    ChatResponse,
    StreamDelta,
)


class FakeLLMAdapter:
    """不访问外网的占位 Adapter。"""

    provider = "fake"

    def _build_reply(self, request: ChatRequest) -> str:
        last_user = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                last_user = msg.content
                break
        return f"[fake:{request.model}] 收到：{last_user[:200]}"

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        # 根据最后一条用户消息拼一段可预期回复，便于前端联调
        reply = self._build_reply(request)
        for ch in reply:
            await asyncio.sleep(0.01)
            yield StreamDelta(text=ch)
        yield StreamDelta(text="", finish_reason="stop")

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            content=self._build_reply(request),
            finish_reason="stop",
        )

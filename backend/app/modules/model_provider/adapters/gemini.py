"""Gemini：走 Google OpenAI 兼容端点。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.modules.model_provider.adapters.base import (
    ChatRequest,
    ChatResponse,
    StreamDelta,
)
from app.modules.model_provider.constants import DEFAULT_BASE_URLS
from app.modules.model_provider.internal.openai_compat import (
    auth_headers_for_bearer,
    chat_completions,
    stream_chat_completions,
)


class GeminiAdapter:
    """Gemini OpenAI Compatibility。"""

    provider = "gemini"

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        base = request.base_url or DEFAULT_BASE_URLS["gemini"]
        headers = auth_headers_for_bearer(request.api_key)
        async for delta in stream_chat_completions(
            provider=self.provider,
            request=request,
            base_url=base,
            headers=headers,
        ):
            yield delta

    async def chat(self, request: ChatRequest) -> ChatResponse:
        base = request.base_url or DEFAULT_BASE_URLS["gemini"]
        headers = auth_headers_for_bearer(request.api_key)
        return await chat_completions(
            provider=self.provider,
            request=request,
            base_url=base,
            headers=headers,
        )

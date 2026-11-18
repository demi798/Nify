"""Ollama：本地 OpenAI 兼容 /v1。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.modules.model_provider.adapters.base import ChatRequest, StreamDelta
from app.modules.model_provider.constants import DEFAULT_BASE_URLS
from app.modules.model_provider.internal.openai_compat import (
    auth_headers_for_bearer,
    stream_chat_completions,
)


class OllamaAdapter:
    """本机 Ollama。"""

    provider = "ollama"

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        base = request.base_url or DEFAULT_BASE_URLS["ollama"]
        # Ollama 通常忽略 api_key
        headers = auth_headers_for_bearer(request.api_key or "ollama")
        async for delta in stream_chat_completions(
            provider=self.provider,
            request=request,
            base_url=base,
            headers=headers,
        ):
            yield delta

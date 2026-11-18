"""OpenAI 兼容端点适配器（任意 /v1/chat/completions 兼容服务）。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.model_provider.adapters.base import ChatRequest, StreamDelta
from app.modules.model_provider.internal.openai_compat import (
    auth_headers_for_bearer,
    stream_chat_completions,
)


class OpenAICompatibleAdapter:
    """通用 OpenAI 兼容 API（需自定义 Base URL）。"""

    provider = "openai_compatible"

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        base = (request.base_url or "").strip()
        if not base:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                "OpenAI 兼容类型必须配置 Base URL",
            )
        headers = auth_headers_for_bearer(request.api_key or "")
        async for delta in stream_chat_completions(
            provider=self.provider,
            request=request,
            base_url=base,
            headers=headers,
        ):
            yield delta

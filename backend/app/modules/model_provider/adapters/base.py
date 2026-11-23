"""LLM Adapter 协议：只做厂商协议与错误映射，不重试、不熔断。

类型定义在 app.shared.llm（跨模块契约）；本文件再导出供本模块 adapters 使用。
"""

from __future__ import annotations

from app.shared.llm import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMAdapter,
    StreamDelta,
    chat_from_stream,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "LLMAdapter",
    "StreamDelta",
    "chat_from_stream",
]

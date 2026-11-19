"""LLM Adapter 协议：只做厂商协议与错误映射，不重试、不熔断。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ChatMessage:
    """上游对话消息。"""

    role: str
    content: str


@dataclass(slots=True)
class StreamDelta:
    """流式增量；text 为空表示仅心跳或控制。"""

    text: str = ""
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatRequest:
    """Adapter 入参（原生参数，不含业务权限）。"""

    model: str
    messages: list[ChatMessage]
    api_key: str
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatResponse:
    """非流式完整回复（Adapter / Gateway 出参）。"""

    content: str
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingRequest:
    """Embedding 入参（原生参数，不含业务权限）。"""

    model: str
    inputs: list[str]
    api_key: str
    base_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingResponse:
    """Embedding 出参；vectors 已按请求 index 对齐。"""

    vectors: list[list[float]]
    model: str | None = None
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class LLMAdapter(Protocol):
    """厂商适配器协议。"""

    provider: str

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        """流式对话（async generator）；异常应映射为 AppError(C*)。"""
        ...

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """非流式对话；异常应映射为 AppError(C*)。"""
        ...


async def chat_from_stream(adapter: LLMAdapter, request: ChatRequest) -> ChatResponse:
    """将 stream_chat 拼成 ChatResponse（无原生非流式时的兜底）。"""
    parts: list[str] = []
    finish: str | None = None
    async for delta in adapter.stream_chat(request):
        if delta.text:
            parts.append(delta.text)
        if delta.finish_reason:
            finish = delta.finish_reason
    return ChatResponse(
        content="".join(parts),
        finish_reason=finish or "stop",
    )

"""厂商 adapters；只做协议与错误映射。"""

from app.modules.model_provider.adapters.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMAdapter,
    StreamDelta,
    chat_from_stream,
)
from app.modules.model_provider.adapters.claude import ClaudeAdapter
from app.modules.model_provider.adapters.fake import FakeLLMAdapter
from app.modules.model_provider.adapters.gemini import GeminiAdapter
from app.modules.model_provider.adapters.ollama import OllamaAdapter
from app.modules.model_provider.adapters.openai_adapter import OpenAIAdapter
from app.modules.model_provider.adapters.openai_compatible import (
    OpenAICompatibleAdapter,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ClaudeAdapter",
    "FakeLLMAdapter",
    "GeminiAdapter",
    "LLMAdapter",
    "OllamaAdapter",
    "OpenAIAdapter",
    "OpenAICompatibleAdapter",
    "StreamDelta",
    "chat_from_stream",
]


def register_default_adapters() -> None:
    """向 LLMGateway 注册一期 adapters。"""
    from app.modules.model_provider.internal.gateway import get_llm_gateway

    gw = get_llm_gateway()
    for adapter in (
        FakeLLMAdapter(),
        OpenAIAdapter(),
        OpenAICompatibleAdapter(),
        ClaudeAdapter(),
        GeminiAdapter(),
        OllamaAdapter(),
    ):
        gw.register_adapter(adapter)

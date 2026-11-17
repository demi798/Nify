"""模型厂商 adapters（协议转换与错误映射；不重试、不熔断）。"""

from app.modules.model_provider.adapters.base import (
    ChatMessage,
    ChatRequest,
    LLMAdapter,
    StreamDelta,
)
from app.modules.model_provider.adapters.fake import FakeLLMAdapter

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "FakeLLMAdapter",
    "LLMAdapter",
    "StreamDelta",
]

"""model_provider 常量与默认值。"""

from __future__ import annotations

# 一期支持的供应商类型
PROVIDER_TYPES: frozenset[str] = frozenset(
    {"openai", "openai_compatible", "claude", "gemini", "ollama"}
)

# 鉴权方案
AUTH_SCHEMES: frozenset[str] = frozenset({"api_key", "api_key_header", "none"})

# 健康状态（连通性）
HEALTH_STATUS_UNKNOWN = "UNKNOWN"
HEALTH_STATUS_UP = "UP"
HEALTH_STATUS_DEGRADED = "DEGRADED"
HEALTH_STATUS_DOWN = "DOWN"
HEALTH_STATUSES: frozenset[str] = frozenset(
    {
        HEALTH_STATUS_UNKNOWN,
        HEALTH_STATUS_UP,
        HEALTH_STATUS_DEGRADED,
        HEALTH_STATUS_DOWN,
    }
)
# 连续失败达到阈值则标记 DOWN；未达阈值记 DEGRADED
HEALTH_FAIL_THRESHOLD = 3

# 模型目录状态
MODEL_STATUSES: frozenset[str] = frozenset(
    {"available", "deprecated", "unavailable"}
)

MODALITIES: frozenset[str] = frozenset({"chat", "embedding"})

# 各类型默认 Base URL（可被库内 base_url 覆盖）
DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    # 兼容类型无统一默认地址，创建时必须填写 base_url
    "openai_compatible": "",
    "claude": "https://api.anthropic.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "ollama": "http://127.0.0.1:11434/v1",
}

# 各类型默认鉴权方案
DEFAULT_AUTH_SCHEMES: dict[str, str] = {
    "openai": "api_key",
    "openai_compatible": "api_key",
    "claude": "api_key_header",
    "gemini": "api_key",
    "ollama": "none",
}

# 新建 Provider 时预置的默认模型
DEFAULT_MODELS: dict[str, tuple[str, str]] = {
    # provider_type -> (model_key, display_name)
    "openai": ("gpt-4o-mini", "GPT-4o mini"),
    "openai_compatible": ("gpt-4o-mini", "Compatible Chat Model"),
    "claude": ("claude-sonnet-4-20250514", "Claude Sonnet 4"),
    "gemini": ("gemini-2.0-flash", "Gemini 2.0 Flash"),
    "ollama": ("llama3.2", "Llama 3.2"),
}

ANTHROPIC_VERSION = "2023-06-01"

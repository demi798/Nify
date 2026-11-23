"""agent 模块常量。"""

from __future__ import annotations

# 生成参数默认值与边界
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048
DEFAULT_MAX_CONTEXT_TURNS = 20

TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 2.0
MAX_TOKENS_MIN = 1
MAX_TOKENS_MAX = 128_000
MAX_CONTEXT_TURNS_MIN = 1
MAX_CONTEXT_TURNS_MAX = 200

# 列表缓存键前缀（进程内）
LIST_CACHE_PREFIX = "agent:list:"

# 单 Agent 最多绑定 MCP 工具数（防止 tools 参数过长影响 LLM）
MAX_TOOL_BINDINGS = 10

"""conversation 模块常量。"""

from __future__ import annotations

# 消息 role / status（与 CLAUDE.md §4.9 对齐）
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"
ROLE_TOOL = "tool"
ROLES: frozenset[str] = frozenset(
    {ROLE_USER, ROLE_ASSISTANT, ROLE_SYSTEM, ROLE_TOOL}
)

STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUSES: frozenset[str] = frozenset(
    {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED}
)

DEFAULT_CONVERSATION_TITLE = "新对话"
CONTENT_MAX_LENGTH = 32_000
TITLE_MAX_LENGTH = 128

# SSE 心跳间隔（秒）
SSE_PING_INTERVAL_SEC = 15

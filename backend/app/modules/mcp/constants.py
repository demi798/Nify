"""mcp 模块常量。"""

from __future__ import annotations

NAME_MAX_LENGTH = 128
ENDPOINT_MAX_LENGTH = 512
TRANSPORT_MAX_LENGTH = 32

# 传输类型（与 DDL / CLAUDE 注释一致）
TRANSPORT_HTTP = "http"
TRANSPORT_SSE = "sse"
TRANSPORT_STDIO = "stdio"

TRANSPORTS: frozenset[str] = frozenset(
    {
        TRANSPORT_HTTP,
        TRANSPORT_SSE,
        TRANSPORT_STDIO,
    }
)

# 连通性状态（对齐 Provider health 语义，便于前端复用 Tag）
TEST_STATUS_UP = "UP"
TEST_STATUS_DOWN = "DOWN"
TEST_STATUS_UNKNOWN = "UNKNOWN"

TEST_STATUSES: frozenset[str] = frozenset(
    {
        TEST_STATUS_UP,
        TEST_STATUS_DOWN,
        TEST_STATUS_UNKNOWN,
    }
)

# 连通性探测超时（秒）
CONNECT_TIMEOUT_SECONDS = 15.0

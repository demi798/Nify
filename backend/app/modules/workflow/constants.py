"""workflow 模块常量。"""

from __future__ import annotations

# 节点类型（一期简版）
NODE_TYPE_START = "start"
NODE_TYPE_END = "end"
NODE_TYPE_LLM = "llm"
NODE_TYPE_KNOWLEDGE = "knowledge"
NODE_TYPE_CONDITION = "condition"
NODE_TYPE_TOOL = "tool"

NODE_TYPES: frozenset[str] = frozenset(
    {
        NODE_TYPE_START,
        NODE_TYPE_END,
        NODE_TYPE_LLM,
        NODE_TYPE_KNOWLEDGE,
        NODE_TYPE_CONDITION,
        NODE_TYPE_TOOL,
    }
)

NAME_MAX_LENGTH = 128
DESCRIPTION_MAX_LENGTH = 512
NODE_KEY_MAX_LENGTH = 64
EDGE_KEY_MAX_LENGTH = 64

# 运行状态（与 workflow_runs.status / CLAUDE 枚举一致）
RUN_STATUS_PENDING = "pending"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCEEDED = "succeeded"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"

RUN_STATUSES: frozenset[str] = frozenset(
    {
        RUN_STATUS_PENDING,
        RUN_STATUS_RUNNING,
        RUN_STATUS_SUCCEEDED,
        RUN_STATUS_FAILED,
        RUN_STATUS_CANCELLED,
    }
)

ERROR_MESSAGE_MAX_LENGTH = 512

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

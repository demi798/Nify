"""节点类型 → Handler 注册表。"""

from __future__ import annotations

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.workflow.constants import (
    NODE_TYPE_CONDITION,
    NODE_TYPE_END,
    NODE_TYPE_KNOWLEDGE,
    NODE_TYPE_LLM,
    NODE_TYPE_START,
    NODE_TYPE_TOOL,
)
from app.modules.workflow.internal.nodes.base import NodeHandler
from app.modules.workflow.internal.nodes.condition import ConditionNodeHandler
from app.modules.workflow.internal.nodes.end import EndNodeHandler
from app.modules.workflow.internal.nodes.knowledge import KnowledgeNodeHandler
from app.modules.workflow.internal.nodes.llm import LlmNodeHandler
from app.modules.workflow.internal.nodes.start import StartNodeHandler
from app.modules.workflow.internal.nodes.tool import ToolNodeHandler

_HANDLERS: dict[str, NodeHandler] = {
    NODE_TYPE_START: StartNodeHandler(),
    NODE_TYPE_END: EndNodeHandler(),
    NODE_TYPE_LLM: LlmNodeHandler(),
    NODE_TYPE_KNOWLEDGE: KnowledgeNodeHandler(),
    NODE_TYPE_CONDITION: ConditionNodeHandler(),
    NODE_TYPE_TOOL: ToolNodeHandler(),
}


def get_node_handler(node_type: str) -> NodeHandler:
    key = (node_type or "").strip().lower()
    handler = _HANDLERS.get(key)
    if handler is None:
        raise AppError(ErrorCode.BAD_REQUEST, f"不支持的节点类型：{node_type}")
    return handler

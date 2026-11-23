"""开始节点：透传 sys 输入到节点输出。"""

from __future__ import annotations

from app.modules.workflow.internal.engine.context import RunContext
from app.modules.workflow.internal.engine.graph import RuntimeNode
from app.modules.workflow.internal.nodes.base import NodeResult


class StartNodeHandler:
    """start：把 query 等写入本节点 output，供下游引用。"""

    async def execute(
        self, *, node: RuntimeNode, ctx: RunContext
    ) -> NodeResult:
        return NodeResult(
            output={
                "query": ctx.pool.get_sys("query"),
                "conversation_id": ctx.pool.get_sys("conversation_id"),
            }
        )

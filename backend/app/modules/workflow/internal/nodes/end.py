"""结束节点：汇总最终答复 text。"""

from __future__ import annotations

from app.modules.workflow.internal.engine.context import RunContext
from app.modules.workflow.internal.engine.graph import RuntimeNode
from app.modules.workflow.internal.nodes.base import NodeResult


class EndNodeHandler:
    """end：优先 last_text（llm/knowledge），否则回退 sys.query。"""

    async def execute(
        self, *, node: RuntimeNode, ctx: RunContext
    ) -> NodeResult:
        text = ctx.pool.last_text
        if not text:
            query = ctx.pool.get_sys("query")
            text = str(query) if query is not None else ""
        return NodeResult(output={"text": text})

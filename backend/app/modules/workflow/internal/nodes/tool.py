"""工具节点：一期 MCP invoke 未实现，明确失败。"""

from __future__ import annotations

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.workflow.internal.engine.context import RunContext
from app.modules.workflow.internal.engine.graph import RuntimeNode
from app.modules.workflow.internal.nodes.base import NodeResult


class ToolNodeHandler:
    """tool：MCP 暂无 invoke，禁止假成功。"""

    async def execute(
        self, *, node: RuntimeNode, ctx: RunContext
    ) -> NodeResult:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "工具节点暂未实现（MCP invoke 未就绪）",
        )

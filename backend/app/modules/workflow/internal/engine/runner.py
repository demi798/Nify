"""GraphRunner：进程内 async DAG 顺序执行（fail-fast）。"""

from __future__ import annotations

import logging
from typing import Any

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.workflow.constants import NODE_TYPE_CONDITION, NODE_TYPE_END
from app.modules.workflow.internal.engine.context import RunContext
from app.modules.workflow.internal.engine.graph import RuntimeGraph
from app.modules.workflow.internal.nodes.registry import get_node_handler

logger = logging.getLogger(__name__)


class GraphRunner:
    """从 start 沿出边执行至 end；一期不做并行分支合并。"""

    async def run(
        self, *, graph: RuntimeGraph, ctx: RunContext
    ) -> dict[str, Any]:
        """执行图；返回 end 节点 output（约定含 text）。

        CancelledError 向上抛出由 service 标 cancelled；
        AppError 向上抛出由 service 标 failed。
        """
        current = graph.start_key
        visited: set[str] = set()
        end_output: dict[str, Any] = {}

        while current:
            if current in visited:
                raise AppError(
                    ErrorCode.BAD_REQUEST,
                    f"工作流执行出现环路或重复访问：{current}",
                )
            visited.add(current)

            node = graph.nodes.get(current)
            if node is None:
                raise AppError(
                    ErrorCode.DATA_INCONSISTENT,
                    f"运行时找不到节点：{current}",
                )

            handler = get_node_handler(node.node_type)
            logger.info(
                "workflow node start key=%s type=%s",
                node.key,
                node.node_type,
            )
            result = await handler.execute(node=node, ctx=ctx)
            ctx.pool.set_node_output(node.key, result.output)

            if node.node_type == NODE_TYPE_END:
                end_output = dict(result.output or {})
                break

            handle = (
                result.next_handle
                if node.node_type == NODE_TYPE_CONDITION
                else None
            )
            nexts = graph.successors(node.key, handle=handle)
            if not nexts:
                raise AppError(
                    ErrorCode.BAD_REQUEST,
                    f"节点 {node.key} 没有可走的出边"
                    + (f"（handle={handle}）" if handle else ""),
                )
            # 一期 fail-fast 单路径：取第一条出边
            current = nexts[0]

        if not end_output and current not in graph.end_keys:
            # 未到达 end
            raise AppError(ErrorCode.BAD_REQUEST, "工作流未到达 end 节点")
        return end_output or {"text": ctx.pool.last_text or ""}

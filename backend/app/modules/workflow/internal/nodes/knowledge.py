"""知识库检索节点：调用 KnowledgeService.retrieve。"""

from __future__ import annotations

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.workflow.internal.engine.context import RunContext
from app.modules.workflow.internal.engine.graph import RuntimeNode
from app.modules.workflow.internal.nodes.base import NodeResult
from app.modules.workflow.node_config import KnowledgeNodeConfig


class KnowledgeNodeHandler:
    """knowledge：按 knowledge_base_ids / top_k 检索。"""

    async def execute(
        self, *, node: RuntimeNode, ctx: RunContext
    ) -> NodeResult:
        cfg = node.config
        if not isinstance(cfg, KnowledgeNodeConfig):
            raise AppError(ErrorCode.BAD_REQUEST, "knowledge 节点配置无效")
        if not cfg.knowledge_base_ids:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                "knowledge 节点缺少 knowledge_base_ids",
            )

        query = str(ctx.pool.get_sys("query") or "")
        hits = await ctx.knowledge.retrieve(
            workspace_id=ctx.workspace_id,
            query=query,
            knowledge_base_ids=list(cfg.knowledge_base_ids),
            top_k=int(cfg.top_k),
        )
        chunks = [
            {
                "content": h.content,
                "score": h.score,
                "knowledge_base_id": h.knowledge_base_id,
                "document_id": h.document_id,
                "chunk_id": h.chunk_id,
                "milvus_pk": h.milvus_pk,
            }
            for h in hits
        ]
        # 拼接摘要供 end / llm 使用
        text_parts = [
            f"[{i}] {c['content']}"
            for i, c in enumerate(chunks, start=1)
            if c.get("content")
        ]
        text = "\n".join(text_parts)
        return NodeResult(output={"chunks": chunks, "text": text})

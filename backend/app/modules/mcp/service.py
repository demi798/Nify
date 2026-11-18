"""mcp 用例（一期：供 Agent 工具多选拉取启用中的服务）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.mcp.models import McpServer
from app.modules.mcp.schemas import McpServerOptionOut


class McpService:
    """MCP 服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_enabled_options(
        self, *, workspace_id: str
    ) -> list[McpServerOptionOut]:
        """返回工作区已启用且未软删的 MCP 服务（供 Agent 绑定）。"""
        stmt = (
            select(McpServer)
            .where(
                McpServer.workspace_id == workspace_id,
                McpServer.is_enabled.is_(True),
            )
            .order_by(McpServer.created_at.asc(), McpServer.id.asc())
        )
        rows = list((await self._session.scalars(stmt)).all())
        return [
            McpServerOptionOut(
                id=row.id,
                name=row.name,
                transport=row.transport,
                is_enabled=bool(row.is_enabled),
            )
            for row in rows
        ]

"""mcp 依赖组装。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.mcp.service import McpService


async def get_mcp_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> McpService:
    return McpService(session)

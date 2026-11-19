"""knowledge 依赖组装。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.knowledge.service import KnowledgeService


async def get_knowledge_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> KnowledgeService:
    return KnowledgeService(session)

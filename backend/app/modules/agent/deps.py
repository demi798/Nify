"""agent 依赖组装。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.agent.service import AgentService
from app.modules.model_provider.deps import get_model_provider_service
from app.modules.model_provider.service import ModelProviderService


async def get_agent_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    model_provider_service: Annotated[
        ModelProviderService, Depends(get_model_provider_service)
    ],
) -> AgentService:
    return AgentService(session, model_provider_service=model_provider_service)

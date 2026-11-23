"""conversation 依赖组装。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.agent.deps import get_agent_service
from app.modules.agent.service import AgentService
from app.modules.conversation.service import ConversationService
from app.modules.mcp.deps import get_mcp_service
from app.modules.mcp.service import McpService
from app.modules.model_provider.deps import get_model_provider_service
from app.modules.model_provider.service import ModelProviderService


async def get_conversation_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    model_provider_service: Annotated[
        ModelProviderService, Depends(get_model_provider_service)
    ],
    mcp_service: Annotated[McpService, Depends(get_mcp_service)],
) -> ConversationService:
    return ConversationService(
        session,
        agent_service=agent_service,
        model_provider_service=model_provider_service,
        mcp_service=mcp_service,
    )

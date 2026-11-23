"""workflow 依赖组装。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.agent.deps import get_agent_service
from app.modules.agent.service import AgentService
from app.modules.knowledge.deps import get_knowledge_service
from app.modules.knowledge.service import KnowledgeService
from app.modules.model_provider.deps import get_model_provider_service
from app.modules.model_provider.service import ModelProviderService
from app.modules.workflow.service import WorkflowService


async def get_workflow_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    knowledge_service: Annotated[
        KnowledgeService, Depends(get_knowledge_service)
    ],
    model_provider_service: Annotated[
        ModelProviderService, Depends(get_model_provider_service)
    ],
) -> WorkflowService:
    return WorkflowService(
        session,
        agent_service=agent_service,
        knowledge_service=knowledge_service,
        model_provider_service=model_provider_service,
    )

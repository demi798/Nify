"""RunContext：单次运行上下文（服务依赖注入）。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.service import AgentService
from app.modules.knowledge.service import KnowledgeService
from app.modules.model_provider.service import ModelProviderService
from app.modules.workflow.internal.engine.pool import VariablePool


@dataclass
class RunContext:
    """GraphRunner / NodeHandler 共享上下文。

    conversation 日后可调用 WorkflowService.run_workflow；本引擎不直接依赖 conversation。
    """

    session: AsyncSession
    workspace_id: str
    user_id: str
    pool: VariablePool
    agents: AgentService
    knowledge: KnowledgeService
    providers: ModelProviderService

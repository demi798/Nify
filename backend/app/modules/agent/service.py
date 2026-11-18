"""agent 用例：CRUD（跨模块仅调 ModelProviderService 公开方法）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import new_uuid, soft_delete
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.pagination import (
    CursorPage,
    CursorParams,
    build_cursor_page,
    decode_cursor,
)
from app.core.rules import reject_if, require_non_blank, require_uuid
from app.modules.agent.constants import (
    DEFAULT_MAX_CONTEXT_TURNS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
)
from app.modules.agent.internal.list_cache import invalidate_agent_list
from app.modules.agent.models import Agent, AgentToolBinding
from app.modules.agent.schemas import (
    AgentCreate,
    AgentDetailOut,
    AgentListItemOut,
    AgentUpdate,
)
from app.modules.model_provider.schemas import EnabledModelBinding
from app.modules.model_provider.service import ModelProviderService


class AgentService:
    """Agent 配置服务。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        model_provider_service: ModelProviderService,
    ) -> None:
        self._session = session
        self._model_provider = model_provider_service

    async def list_agents_page(
        self, *, workspace_id: str, params: CursorParams
    ) -> CursorPage[AgentListItemOut]:
        """工作区 Agent 游标分页列表。"""
        limit = params.limit
        stmt = select(Agent).where(Agent.workspace_id == workspace_id)
        if params.cursor:
            cursor_at, cursor_id = decode_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    Agent.created_at < cursor_at,
                    and_(
                        Agent.created_at == cursor_at,
                        Agent.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(Agent.created_at.desc(), Agent.id.desc()).limit(
            limit + 1
        )
        rows = list((await self._session.scalars(stmt)).all())
        items = [self._to_list_item(a) for a in rows]
        return build_cursor_page(
            items,
            limit,
            created_at_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    async def get_agent(
        self, *, workspace_id: str, agent_id: str
    ) -> AgentDetailOut:
        """详情：含 system_prompt 与 tool_ids。"""
        agent = await self._get_agent_entity(workspace_id, agent_id)
        tool_ids = await self._load_tool_ids(agent.id)
        return self._to_detail_out(agent, tool_ids=tool_ids)

    async def create_agent(
        self,
        *,
        workspace_id: str,
        user_id: str,
        body: AgentCreate,
    ) -> AgentDetailOut:
        """创建 Agent。

        Python/Nify 适配：
        1. name 唯一性（同工作区存活名）
        2. 跨模块校验 model_config_id → ``ModelProviderService.get_enabled_model_binding``
        3. 同一请求 session 内 ``flush`` 写入 agent + 批量 agent_tool_bindings
           （禁止 service ``commit``；事务由 ``get_session`` 统一提交）
        4. 清除工作区 Agent 列表缓存
        5. 返回 ``AgentDetailOut``
        """
        name = require_non_blank(body.name, field="name")
        await self._assert_name_unique(workspace_id=workspace_id, name=name)

        binding = await self._model_provider.get_enabled_model_binding(
            workspace_id=workspace_id,
            model_id=body.model_config_id,
        )

        tool_ids = self._normalize_tool_ids(body.tool_ids)
        config = self._build_config(
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            max_context_turns=body.max_context_turns,
        )

        agent = Agent(
            id=new_uuid(),
            workspace_id=workspace_id,
            name=name,
            description=body.description,
            system_prompt=body.system_prompt,
            model_provider_id=binding.provider_id,
            model_name=binding.model_key,
            model_config_id=binding.model_id,
            knowledge_base_ids=[],
            mcp_server_ids=list(tool_ids),
            config=config,
            is_enabled=bool(body.is_enabled),
            created_by=user_id,
            deleted_at=None,
        )
        self._session.add(agent)
        await self._session.flush()

        await self._insert_tool_bindings(
            workspace_id=workspace_id,
            agent_id=agent.id,
            tool_ids=tool_ids,
        )
        await self._session.flush()

        invalidate_agent_list(workspace_id)
        return self._to_detail_out(agent, tool_ids=tool_ids, binding=binding)

    async def update_agent(
        self,
        *,
        workspace_id: str,
        agent_id: str,
        body: AgentUpdate,
    ) -> AgentDetailOut:
        """部分更新 Agent；改模型再走跨模块校验；改工具则整表替换绑定。"""
        agent = await self._get_agent_entity(workspace_id, agent_id)
        changes = body.changed_fields()
        binding: EnabledModelBinding | None = None

        if "name" in changes and changes["name"] is not None:
            name = require_non_blank(changes["name"], field="name")
            if name != agent.name:
                await self._assert_name_unique(
                    workspace_id=workspace_id,
                    name=name,
                    exclude_id=agent.id,
                )
            agent.name = name

        if "description" in changes:
            agent.description = changes["description"]

        if "system_prompt" in changes:
            agent.system_prompt = changes["system_prompt"]

        if "is_enabled" in changes and changes["is_enabled"] is not None:
            agent.is_enabled = bool(changes["is_enabled"])

        if "model_config_id" in changes and changes["model_config_id"]:
            new_model_id = str(changes["model_config_id"])
            # 未更换模型时跳过健康态再校验，避免仅改文案也被 DOWN 拦住
            if new_model_id != agent.model_config_id:
                binding = await self._model_provider.get_enabled_model_binding(
                    workspace_id=workspace_id,
                    model_id=new_model_id,
                )
                agent.model_config_id = binding.model_id
                agent.model_provider_id = binding.provider_id
                agent.model_name = binding.model_key

        # config 局部合并
        temperature, max_tokens, max_context_turns = self._read_config(agent.config)
        if "temperature" in changes and changes["temperature"] is not None:
            temperature = float(changes["temperature"])
        if "max_tokens" in changes and changes["max_tokens"] is not None:
            max_tokens = int(changes["max_tokens"])
        if "max_context_turns" in changes and changes["max_context_turns"] is not None:
            max_context_turns = int(changes["max_context_turns"])
        if any(
            k in changes for k in ("temperature", "max_tokens", "max_context_turns")
        ):
            agent.config = self._build_config(
                temperature=temperature,
                max_tokens=max_tokens,
                max_context_turns=max_context_turns,
            )

        tool_ids = await self._load_tool_ids(agent.id)
        if "tool_ids" in changes and changes["tool_ids"] is not None:
            tool_ids = self._normalize_tool_ids(list(changes["tool_ids"]))
            await self._replace_tool_bindings(
                workspace_id=workspace_id,
                agent_id=agent.id,
                tool_ids=tool_ids,
            )
            agent.mcp_server_ids = list(tool_ids)

        await self._session.flush()
        invalidate_agent_list(workspace_id)
        return self._to_detail_out(agent, tool_ids=tool_ids, binding=binding)

    async def delete_agent(self, *, workspace_id: str, agent_id: str) -> None:
        """软删除 Agent（deleted_at）；绑定行保留供审计，列表不可见。"""
        agent = await self._get_agent_entity(workspace_id, agent_id)
        soft_delete(agent)
        await self._session.flush()
        invalidate_agent_list(workspace_id)

    # ---------- 内部 ----------

    async def _get_agent_entity(self, workspace_id: str, agent_id: str) -> Agent:
        agent_id = require_uuid(agent_id, field="id")
        agent = await self._session.get(Agent, agent_id)
        if agent is None:
            raise AppError(ErrorCode.NOT_FOUND, "Agent 不存在")
        if agent.workspace_id != workspace_id:
            raise AppError(ErrorCode.FORBIDDEN, "资源不属于当前工作区")
        return agent

    async def _assert_name_unique(
        self,
        *,
        workspace_id: str,
        name: str,
        exclude_id: str | None = None,
    ) -> None:
        """同工作区存活 Agent 名称唯一（软删过滤器已排除 deleted_at）。"""
        stmt = select(Agent.id).where(
            Agent.workspace_id == workspace_id,
            Agent.name == name,
        )
        if exclude_id:
            stmt = stmt.where(Agent.id != exclude_id)
        exists = await self._session.scalar(stmt)
        reject_if(exists is not None, code=ErrorCode.CONFLICT, message="Agent 名称已存在")

    def _normalize_tool_ids(self, tool_ids: list[str]) -> list[str]:
        """校验 UUID 格式并去重；mcp 模块未就绪时仅弱校验格式。"""
        out: list[str] = []
        seen: set[str] = set()
        for raw in tool_ids or []:
            tid = require_uuid(raw, field="tool_ids")
            if tid in seen:
                continue
            seen.add(tid)
            out.append(tid)
        return out

    async def _load_tool_ids(self, agent_id: str) -> list[str]:
        rows = list(
            (
                await self._session.scalars(
                    select(AgentToolBinding.mcp_server_id)
                    .where(AgentToolBinding.agent_id == agent_id)
                    .order_by(AgentToolBinding.created_at.asc(), AgentToolBinding.id.asc())
                )
            ).all()
        )
        return [str(x) for x in rows]

    async def _insert_tool_bindings(
        self,
        *,
        workspace_id: str,
        agent_id: str,
        tool_ids: list[str],
    ) -> None:
        """批量 INSERT agent_tool_bindings。"""
        if not tool_ids:
            return
        for mcp_server_id in tool_ids:
            self._session.add(
                AgentToolBinding(
                    id=new_uuid(),
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    mcp_server_id=mcp_server_id,
                )
            )

    async def _replace_tool_bindings(
        self,
        *,
        workspace_id: str,
        agent_id: str,
        tool_ids: list[str],
    ) -> None:
        """先删后插，整表替换工具绑定。"""
        await self._session.execute(
            delete(AgentToolBinding).where(AgentToolBinding.agent_id == agent_id)
        )
        await self._insert_tool_bindings(
            workspace_id=workspace_id,
            agent_id=agent_id,
            tool_ids=tool_ids,
        )

    @staticmethod
    def _build_config(
        *,
        temperature: float,
        max_tokens: int,
        max_context_turns: int,
    ) -> dict[str, Any]:
        return {
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "max_context_turns": int(max_context_turns),
        }

    @staticmethod
    def _read_config(config: dict[str, Any] | None) -> tuple[float, int, int]:
        raw = config or {}
        temperature = float(raw.get("temperature", DEFAULT_TEMPERATURE))
        max_tokens = int(raw.get("max_tokens", DEFAULT_MAX_TOKENS))
        max_context_turns = int(raw.get("max_context_turns", DEFAULT_MAX_CONTEXT_TURNS))
        return temperature, max_tokens, max_context_turns

    def _to_list_item(self, agent: Agent) -> AgentListItemOut:
        temperature, _, _ = self._read_config(agent.config)
        tool_count = len(agent.mcp_server_ids or [])
        return AgentListItemOut(
            id=agent.id,
            workspace_id=agent.workspace_id,
            name=agent.name,
            description=agent.description,
            model_config_id=agent.model_config_id,
            model_provider_id=agent.model_provider_id,
            model_name=agent.model_name,
            temperature=temperature,
            tool_count=tool_count,
            is_enabled=bool(agent.is_enabled),
            created_by=agent.created_by,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    def _to_detail_out(
        self,
        agent: Agent,
        *,
        tool_ids: list[str],
        binding: EnabledModelBinding | None = None,
    ) -> AgentDetailOut:
        temperature, max_tokens, max_context_turns = self._read_config(agent.config)
        kb_ids = [str(x) for x in (agent.knowledge_base_ids or [])]
        return AgentDetailOut(
            id=agent.id,
            workspace_id=agent.workspace_id,
            name=agent.name,
            description=agent.description,
            system_prompt=agent.system_prompt,
            model_config_id=agent.model_config_id,
            model_provider_id=agent.model_provider_id,
            model_name=agent.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            max_context_turns=max_context_turns,
            tool_ids=list(tool_ids),
            knowledge_base_ids=kb_ids,
            is_enabled=bool(agent.is_enabled),
            created_by=agent.created_by,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            provider_name=binding.provider_name if binding else None,
            model_display_name=binding.display_name if binding else None,
        )

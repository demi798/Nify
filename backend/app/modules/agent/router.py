"""agent 路由：/api/v1/agents。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentWorkspace, get_current_workspace, get_path_uuid
from app.core.pagination import CursorPage, CursorParams, get_cursor_params
from app.core.response import ApiResult
from app.modules.agent.deps import get_agent_service
from app.modules.agent.schemas import (
    AgentCreate,
    AgentDetailOut,
    AgentListItemOut,
    AgentToolsReplace,
    AgentUpdate,
)
from app.modules.agent.service import AgentService

router = APIRouter(
    prefix="/api/v1/agents",
    tags=["agents"],
)


@router.get("", response_model=ApiResult[CursorPage[AgentListItemOut]])
async def list_agents(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[AgentListItemOut]]:
    """列表：游标分页。"""
    return ApiResult.ok(
        await svc.list_agents_page(
            workspace_id=ws.workspace_id, params=params
        )
    )


@router.post(
    "",
    response_model=ApiResult[AgentDetailOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    body: AgentCreate,
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResult[AgentDetailOut]:
    """创建 Agent。"""
    return ApiResult.ok(
        await svc.create_agent(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            body=body,
        )
    )


@router.get("/{id}", response_model=ApiResult[AgentDetailOut])
async def get_agent(
    agent_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResult[AgentDetailOut]:
    """详情。"""
    return ApiResult.ok(
        await svc.get_agent(workspace_id=ws.workspace_id, agent_id=agent_id)
    )


@router.put("/{id}", response_model=ApiResult[AgentDetailOut])
async def update_agent(
    body: AgentUpdate,
    agent_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResult[AgentDetailOut]:
    """更新 Agent（PUT；部分字段）。"""
    return ApiResult.ok(
        await svc.update_agent(
            workspace_id=ws.workspace_id,
            agent_id=agent_id,
            body=body,
        )
    )


@router.put("/{id}/tools", response_model=ApiResult[AgentDetailOut])
async def replace_agent_tools(
    body: AgentToolsReplace,
    agent_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResult[AgentDetailOut]:
    """全量替换工具绑定（toolIds = mcp_server_id 数组；最多 10 个）。"""
    return ApiResult.ok(
        await svc.replace_agent_tools(
            workspace_id=ws.workspace_id,
            agent_id=agent_id,
            body=body,
        )
    )


@router.delete("/{id}", response_model=ApiResult[None])
async def delete_agent(
    agent_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[AgentService, Depends(get_agent_service)],
) -> ApiResult[None]:
    """软删除 Agent。"""
    await svc.delete_agent(workspace_id=ws.workspace_id, agent_id=agent_id)
    return ApiResult.ok(None)

"""mcp 路由：/api/v1/mcp-servers（一期：选项列表）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentWorkspace, get_current_workspace
from app.core.response import ApiResult
from app.modules.mcp.deps import get_mcp_service
from app.modules.mcp.schemas import McpServerOptionOut
from app.modules.mcp.service import McpService

router = APIRouter(
    prefix="/api/v1/mcp-servers",
    tags=["mcp-servers"],
)


@router.get("", response_model=ApiResult[list[McpServerOptionOut]])
async def list_mcp_server_options(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
) -> ApiResult[list[McpServerOptionOut]]:
    """启用中的 MCP 服务列表（Agent 工具多选）。"""
    return ApiResult.ok(
        await svc.list_enabled_options(workspace_id=ws.workspace_id)
    )

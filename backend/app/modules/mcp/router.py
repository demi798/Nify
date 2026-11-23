"""mcp 路由：/api/v1/mcp（CLAUDE.md 模块表）。

- POST   /                         创建
- GET    /                         游标分页列表
- GET    /options                  启用中选项（Agent 多选）
- GET    /{id}                     详情（含工具列表）
- PUT    /{id}                     更新
- DELETE /{id}                     软删（有 Agent 绑定则拒绝）
- POST   /{id}/test                连通性测试
- POST   /{id}/debug               调试调用工具
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentWorkspace, get_current_workspace, get_path_uuid
from app.core.pagination import CursorPage, CursorParams, get_cursor_params
from app.core.response import ApiResult
from app.modules.mcp.deps import get_mcp_service
from app.modules.mcp.schemas import (
    McpServerCreate,
    McpServerDebugIn,
    McpServerDebugOut,
    McpServerDetailOut,
    McpServerListItemOut,
    McpServerOptionOut,
    McpServerTestOut,
    McpServerUpdate,
)
from app.modules.mcp.service import McpService

router = APIRouter(
    prefix="/api/v1/mcp",
    tags=["mcp"],
)


@router.get("", response_model=ApiResult[CursorPage[McpServerListItemOut]])
async def list_mcp_servers(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[McpServerListItemOut]]:
    """MCP Server 列表（游标分页）。"""
    return ApiResult.ok(
        await svc.list_servers_page(
            workspace_id=ws.workspace_id, params=params
        )
    )


@router.post(
    "",
    response_model=ApiResult[McpServerDetailOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp_server(
    body: McpServerCreate,
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
) -> ApiResult[McpServerDetailOut]:
    """创建 MCP Server。"""
    return ApiResult.ok(
        await svc.create_server(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            body=body,
        )
    )


@router.get(
    "/options",
    response_model=ApiResult[list[McpServerOptionOut]],
)
async def list_mcp_server_options(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
) -> ApiResult[list[McpServerOptionOut]]:
    """启用中的 MCP 服务选项（Agent 工具多选）。"""
    return ApiResult.ok(
        await svc.list_enabled_options(workspace_id=ws.workspace_id)
    )


@router.get("/{id}", response_model=ApiResult[McpServerDetailOut])
async def get_mcp_server(
    server_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
) -> ApiResult[McpServerDetailOut]:
    """详情：含远端工具列表（拉取失败时 tools 为空并带 tools_error）。"""
    return ApiResult.ok(
        await svc.get_server(
            workspace_id=ws.workspace_id, server_id=server_id
        )
    )


@router.put("/{id}", response_model=ApiResult[McpServerDetailOut])
async def update_mcp_server(
    body: McpServerUpdate,
    server_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
) -> ApiResult[McpServerDetailOut]:
    """更新 MCP Server。"""
    return ApiResult.ok(
        await svc.update_server(
            workspace_id=ws.workspace_id,
            server_id=server_id,
            body=body,
        )
    )


@router.delete("/{id}", response_model=ApiResult[None])
async def delete_mcp_server(
    server_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
) -> ApiResult[None]:
    """逻辑删除；若 Agent 仍绑定则 CONFLICT。"""
    await svc.delete_server(
        workspace_id=ws.workspace_id, server_id=server_id
    )
    return ApiResult.ok(None)


@router.post("/{id}/test", response_model=ApiResult[McpServerTestOut])
async def test_mcp_server(
    server_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
) -> ApiResult[McpServerTestOut]:
    """测试连通性（list_tools）。"""
    return ApiResult.ok(
        await svc.test_server(
            workspace_id=ws.workspace_id, server_id=server_id
        )
    )


@router.post("/{id}/debug", response_model=ApiResult[McpServerDebugOut])
async def debug_mcp_server(
    body: McpServerDebugIn,
    server_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[McpService, Depends(get_mcp_service)],
) -> ApiResult[McpServerDebugOut]:
    """调试：调用指定工具，返回结果与耗时。"""
    return ApiResult.ok(
        await svc.debug_call(
            workspace_id=ws.workspace_id,
            server_id=server_id,
            body=body,
        )
    )

"""workflow 路由：/api/v1/workflows。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentWorkspace, get_current_workspace, get_path_uuid
from app.core.pagination import CursorPage, CursorParams, get_cursor_params
from app.core.response import ApiResult
from app.modules.workflow.deps import get_workflow_service
from app.modules.workflow.schemas import (
    WorkflowCreate,
    WorkflowDetailOut,
    WorkflowListItemOut,
    WorkflowRunCreate,
    WorkflowRunOut,
    WorkflowUpdate,
)
from app.modules.workflow.service import WorkflowService

router = APIRouter(
    prefix="/api/v1/workflows",
    tags=["workflows"],
)


@router.get("", response_model=ApiResult[CursorPage[WorkflowListItemOut]])
async def list_workflows(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[WorkflowService, Depends(get_workflow_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[WorkflowListItemOut]]:
    """工作流列表（游标分页）。"""
    return ApiResult.ok(
        await svc.list_workflows_page(
            workspace_id=ws.workspace_id, params=params
        )
    )


@router.post(
    "",
    response_model=ApiResult[WorkflowDetailOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    body: WorkflowCreate,
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[WorkflowService, Depends(get_workflow_service)],
) -> ApiResult[WorkflowDetailOut]:
    """创建工作流（含 nodes / edges，同事务写入三表）。"""
    return ApiResult.ok(
        await svc.create_workflow(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            body=body,
        )
    )


@router.get(
    "/runs/{id}",
    response_model=ApiResult[WorkflowRunOut],
)
async def get_workflow_run(
    run_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[WorkflowService, Depends(get_workflow_service)],
) -> ApiResult[WorkflowRunOut]:
    """按 run id 查运行详情（置于 /{id} 之前，避免与工作流详情冲突）。"""
    return ApiResult.ok(
        await svc.get_run(workspace_id=ws.workspace_id, run_id=run_id)
    )


@router.get(
    "/{id}/runs",
    response_model=ApiResult[CursorPage[WorkflowRunOut]],
)
async def list_workflow_runs(
    workflow_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[WorkflowService, Depends(get_workflow_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[WorkflowRunOut]]:
    """某工作流的运行列表（游标分页）。"""
    return ApiResult.ok(
        await svc.list_runs_page(
            workspace_id=ws.workspace_id,
            workflow_id=workflow_id,
            params=params,
        )
    )


@router.post(
    "/{id}/run",
    response_model=ApiResult[WorkflowRunOut],
    status_code=status.HTTP_201_CREATED,
)
async def run_workflow(
    body: WorkflowRunCreate,
    workflow_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[WorkflowService, Depends(get_workflow_service)],
) -> ApiResult[WorkflowRunOut]:
    """触发一次工作流执行（进程内 async DAG）。"""
    return ApiResult.ok(
        await svc.run_workflow(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            workflow_id=workflow_id,
            body=body,
        )
    )


@router.get("/{id}", response_model=ApiResult[WorkflowDetailOut])
async def get_workflow(
    workflow_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[WorkflowService, Depends(get_workflow_service)],
) -> ApiResult[WorkflowDetailOut]:
    """工作流详情（完整节点与边）。"""
    return ApiResult.ok(
        await svc.get_workflow(
            workspace_id=ws.workspace_id, workflow_id=workflow_id
        )
    )


@router.put("/{id}", response_model=ApiResult[WorkflowDetailOut])
async def update_workflow(
    body: WorkflowUpdate,
    workflow_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[WorkflowService, Depends(get_workflow_service)],
) -> ApiResult[WorkflowDetailOut]:
    """更新工作流；带 nodes 时整图替换（软删旧节点/边再插入）。"""
    return ApiResult.ok(
        await svc.update_workflow(
            workspace_id=ws.workspace_id,
            workflow_id=workflow_id,
            body=body,
        )
    )


@router.delete("/{id}", response_model=ApiResult[None])
async def delete_workflow(
    workflow_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[WorkflowService, Depends(get_workflow_service)],
) -> ApiResult[None]:
    """逻辑删除工作流及其 nodes / edges。"""
    await svc.delete_workflow(
        workspace_id=ws.workspace_id, workflow_id=workflow_id
    )
    return ApiResult.ok(None)

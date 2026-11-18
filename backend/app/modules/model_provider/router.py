"""model_provider 路由：/api/v1/model-providers（对齐 CLAUDE.md）。

规范接口：
- POST   /                         创建（201 + ApiResult）
- GET    /                         列表（CursorPage 分页）
- GET    /{id}                     详情（含 modelConfig、health）
- PUT    /{id}                     更新
- DELETE /{id}                     删除
- POST   /{id}/test-connection     连通性测试
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.core.deps import CurrentWorkspace, get_current_workspace, get_path_uuid
from app.core.pagination import CursorPage, CursorParams, get_cursor_params
from app.core.response import ApiResult
from app.core.rules import require_uuid
from app.modules.model_provider.deps import get_model_provider_service
from app.modules.model_provider.schemas import (
    ProviderCreate,
    ProviderHealthOut,
    ProviderModelCreate,
    ProviderModelOut,
    ProviderModelUpdate,
    ProviderOut,
    ProviderUpdate,
)
from app.modules.model_provider.service import ModelProviderService

router = APIRouter(
    prefix="/api/v1/model-providers",
    tags=["model-providers"],
)


@router.get("", response_model=ApiResult[CursorPage[ProviderOut]])
async def list_providers(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[ProviderOut]]:
    """列表：游标分页，data 为 CursorPage。"""
    return ApiResult.ok(
        await svc.list_providers_page(
            workspace_id=ws.workspace_id, params=params
        )
    )


@router.post(
    "",
    response_model=ApiResult[ProviderOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    body: ProviderCreate,
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[ProviderOut]:
    """创建提供商。"""
    return ApiResult.ok(
        await svc.create_provider(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            body=body,
        )
    )


@router.get("/{id}", response_model=ApiResult[ProviderOut])
async def get_provider(
    provider_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[ProviderOut]:
    """详情：含 modelConfig 与 health。"""
    return ApiResult.ok(
        await svc.get_provider(
            workspace_id=ws.workspace_id, provider_id=provider_id
        )
    )


@router.put("/{id}", response_model=ApiResult[ProviderOut])
async def update_provider(
    body: ProviderUpdate,
    provider_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[ProviderOut]:
    """更新提供商（PUT；部分字段更新，未传字段保持原值）。"""
    return ApiResult.ok(
        await svc.update_provider(
            workspace_id=ws.workspace_id,
            provider_id=provider_id,
            body=body,
        )
    )


@router.delete("/{id}", response_model=ApiResult[None])
async def delete_provider(
    provider_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[None]:
    """删除提供商及其模型目录。"""
    await svc.delete_provider(
        workspace_id=ws.workspace_id, provider_id=provider_id
    )
    return ApiResult.ok(None)


@router.post("/{id}/test-connection", response_model=ApiResult[ProviderHealthOut])
async def test_connection(
    provider_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[ProviderHealthOut]:
    """连通性测试：成功记 UP；连续失败达阈值记 DOWN。"""
    return ApiResult.ok(
        await svc.check_health(
            workspace_id=ws.workspace_id, provider_id=provider_id
        )
    )


# ---------- 模型目录（附属资源）----------


@router.get("/{id}/models", response_model=ApiResult[list[ProviderModelOut]])
async def list_models(
    provider_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[list[ProviderModelOut]]:
    return ApiResult.ok(
        await svc.list_models(
            workspace_id=ws.workspace_id, provider_id=provider_id
        )
    )


@router.post(
    "/{id}/models",
    response_model=ApiResult[ProviderModelOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_model(
    body: ProviderModelCreate,
    provider_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[ProviderModelOut]:
    return ApiResult.ok(
        await svc.create_model(
            workspace_id=ws.workspace_id,
            provider_id=provider_id,
            body=body,
        )
    )


@router.put("/{id}/models/{model_id}", response_model=ApiResult[ProviderModelOut])
async def update_model(
    body: ProviderModelUpdate,
    id: Annotated[str, Path(description="提供商 UUID")],
    model_id: Annotated[str, Path(description="模型 UUID")],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[ProviderModelOut]:
    return ApiResult.ok(
        await svc.update_model(
            workspace_id=ws.workspace_id,
            provider_id=require_uuid(id, field="id"),
            model_id=require_uuid(model_id, field="model_id"),
            body=body,
        )
    )


@router.delete("/{id}/models/{model_id}", response_model=ApiResult[None])
async def delete_model(
    id: Annotated[str, Path(description="提供商 UUID")],
    model_id: Annotated[str, Path(description="模型 UUID")],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ModelProviderService, Depends(get_model_provider_service)],
) -> ApiResult[None]:
    await svc.delete_model(
        workspace_id=ws.workspace_id,
        provider_id=require_uuid(id, field="id"),
        model_id=require_uuid(model_id, field="model_id"),
    )
    return ApiResult.ok(None)

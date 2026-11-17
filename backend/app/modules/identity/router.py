"""identity 路由：/api/v1/auth + /api/v1/workspaces。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, get_current_user, get_path_uuid
from app.core.response import ApiResult
from app.modules.identity.deps import get_identity_service
from app.modules.identity.schemas import (
    TokenOut,
    UserLogin,
    UserOut,
    UserRegister,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.modules.identity.service import IdentityService

router = APIRouter(tags=["identity"])

auth_router = APIRouter(prefix="/api/v1/auth", tags=["identity-auth"])
workspace_router = APIRouter(prefix="/api/v1/workspaces", tags=["identity-workspaces"])


@auth_router.post(
    "/register",
    response_model=ApiResult[UserOut],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: UserRegister,
    svc: Annotated[IdentityService, Depends(get_identity_service)],
) -> ApiResult[UserOut]:
    return ApiResult.ok(await svc.register(body))


@auth_router.post("/login", response_model=ApiResult[TokenOut])
async def login(
    body: UserLogin,
    svc: Annotated[IdentityService, Depends(get_identity_service)],
) -> ApiResult[TokenOut]:
    return ApiResult.ok(await svc.login(body))


@workspace_router.post(
    "",
    response_model=ApiResult[WorkspaceOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    body: WorkspaceCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[IdentityService, Depends(get_identity_service)],
) -> ApiResult[WorkspaceOut]:
    return ApiResult.ok(await svc.create_workspace(user_id=user.user_id, body=body))


@workspace_router.get("", response_model=ApiResult[list[WorkspaceOut]])
async def list_workspaces(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[IdentityService, Depends(get_identity_service)],
) -> ApiResult[list[WorkspaceOut]]:
    return ApiResult.ok(await svc.list_workspaces(user_id=user.user_id))


@workspace_router.get("/{id}", response_model=ApiResult[WorkspaceOut])
async def get_workspace(
    workspace_id: Annotated[str, Depends(get_path_uuid)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[IdentityService, Depends(get_identity_service)],
) -> ApiResult[WorkspaceOut]:
    return ApiResult.ok(
        await svc.get_workspace(user_id=user.user_id, workspace_id=workspace_id)
    )


@workspace_router.patch("/{id}", response_model=ApiResult[WorkspaceOut])
async def update_workspace(
    body: WorkspaceUpdate,
    workspace_id: Annotated[str, Depends(get_path_uuid)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[IdentityService, Depends(get_identity_service)],
) -> ApiResult[WorkspaceOut]:
    return ApiResult.ok(
        await svc.update_workspace(
            user_id=user.user_id,
            workspace_id=workspace_id,
            body=body,
        )
    )


@workspace_router.delete("/{id}", response_model=ApiResult[None])
async def delete_workspace(
    workspace_id: Annotated[str, Depends(get_path_uuid)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    svc: Annotated[IdentityService, Depends(get_identity_service)],
) -> ApiResult[None]:
    await svc.delete_workspace(user_id=user.user_id, workspace_id=workspace_id)
    return ApiResult.ok(None)


router.include_router(auth_router)
router.include_router(workspace_router)

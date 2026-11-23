"""FastAPI 公共依赖：当前用户 / 工作区 / 路径 UUID。

其他业务模块只通过本模块取身份上下文，禁止 import identity service。
工作区成员存在性在本层用 SQL 校验（不 import identity models/service）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.logging import set_user_id, set_workspace_id
from app.core.rules import require_uuid
from app.core.security import decode_access_token


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """请求级当前用户（与 ORM 解耦）。"""

    user_id: str
    email: str | None = None


@dataclass(frozen=True, slots=True)
class CurrentWorkspace:
    """请求级当前工作区上下文。"""

    workspace_id: str
    user_id: str


def _parse_bearer(authorization: str | None) -> str:
    if not authorization:
        raise AppError(ErrorCode.UNAUTHORIZED)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AppError(ErrorCode.UNAUTHORIZED, "Authorization 必须为 Bearer Token")
    return token.strip()


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """解析 Bearer JWT，写入上下文；不做 DB 查库（identity 未就绪时亦可联调）。"""
    token = _parse_bearer(authorization)
    payload = decode_access_token(token)
    user_id = require_uuid(payload.user_id, field="user_id")
    set_user_id(user_id)
    return CurrentUser(user_id=user_id, email=payload.email)


async def get_current_workspace(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    x_workspace_id: Annotated[str | None, Header(alias="X-Workspace-Id")] = None,
) -> CurrentWorkspace:
    """要求登录 + X-Workspace-Id，且用户必须是该工作区成员。"""
    if not x_workspace_id or not x_workspace_id.strip():
        raise AppError(ErrorCode.BAD_REQUEST, "缺少请求头 X-Workspace-Id")
    workspace_id = require_uuid(x_workspace_id, field="X-Workspace-Id")
    # 禁止跨租户：仅 Header 不足以证明成员关系
    exists = await session.scalar(
        text(
            """
            SELECT 1 FROM identity_workspace_members
            WHERE workspace_id = :workspace_id AND user_id = :user_id
            LIMIT 1
            """
        ),
        {"workspace_id": workspace_id, "user_id": user.user_id},
    )
    if not exists:
        raise AppError(ErrorCode.FORBIDDEN, "不是该工作区成员")
    set_workspace_id(workspace_id)
    return CurrentWorkspace(workspace_id=workspace_id, user_id=user.user_id)


async def get_path_uuid(
    id: Annotated[str, Path(description="资源 UUID")],
) -> str:
    """路径参数 {id} 的 UUID 校验。"""
    return require_uuid(id, field="id")


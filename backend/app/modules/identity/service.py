"""identity 用例：注册登录 + 工作区 CRUD。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import new_uuid
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.rules import reject_if, require_non_blank, require_true
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.identity.models import User, Workspace, WorkspaceMember
from app.modules.identity.schemas import (
    TokenOut,
    UserLogin,
    UserOut,
    UserRegister,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)


class IdentityService:
    """身份与工作区服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------- auth ----------

    async def register(self, body: UserRegister) -> UserOut:
        email = body.email
        exists = await self._session.scalar(select(User.id).where(User.email == email))
        reject_if(exists is not None, code=ErrorCode.CONFLICT, message="邮箱已被注册")

        user = User(
            id=new_uuid(),
            email=email,
            password_hash=hash_password(body.password),
            display_name=body.display_name,
            status="active",
        )
        self._session.add(user)
        await self._session.flush()
        return self._to_user_out(user)

    async def login(self, body: UserLogin) -> TokenOut:
        user = await self._session.scalar(select(User).where(User.email == body.email))
        require_true(
            user is not None and verify_password(body.password, user.password_hash),
            code=ErrorCode.UNAUTHORIZED,
            message="邮箱或密码错误",
        )
        assert user is not None
        require_true(
            user.status == "active",
            code=ErrorCode.FORBIDDEN,
            message="账号已停用",
        )
        token = create_access_token(user_id=user.id, email=user.email)
        return TokenOut(access_token=token, user=self._to_user_out(user))

    async def get_user(self, user_id: str) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            raise AppError(ErrorCode.NOT_FOUND, "用户不存在")
        return user

    # ---------- workspace CRUD ----------

    async def create_workspace(self, *, user_id: str, body: WorkspaceCreate) -> WorkspaceOut:
        name = require_non_blank(body.name, field="name")
        ws = Workspace(id=new_uuid(), name=name, created_by=user_id)
        self._session.add(ws)
        await self._session.flush()
        member = WorkspaceMember(
            id=new_uuid(),
            workspace_id=ws.id,
            user_id=user_id,
            role="owner",
        )
        self._session.add(member)
        await self._session.flush()
        return self._to_workspace_out(ws, role="owner")

    async def list_workspaces(self, *, user_id: str) -> list[WorkspaceOut]:
        stmt = (
            select(Workspace, WorkspaceMember.role)
            .join(
                WorkspaceMember,
                WorkspaceMember.workspace_id == Workspace.id,
            )
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc(), Workspace.id.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [self._to_workspace_out(ws, role=role) for ws, role in rows]

    async def get_workspace(self, *, user_id: str, workspace_id: str) -> WorkspaceOut:
        ws, role = await self._require_membership(user_id=user_id, workspace_id=workspace_id)
        return self._to_workspace_out(ws, role=role)

    async def update_workspace(
        self,
        *,
        user_id: str,
        workspace_id: str,
        body: WorkspaceUpdate,
    ) -> WorkspaceOut:
        ws, role = await self._require_membership(user_id=user_id, workspace_id=workspace_id)
        require_true(
            role in {"owner", "admin"},
            code=ErrorCode.FORBIDDEN,
            message="无权限修改工作区",
        )
        changes = body.changed_fields()
        if "name" in changes and changes["name"] is not None:
            ws.name = require_non_blank(changes["name"], field="name")
        await self._session.flush()
        return self._to_workspace_out(ws, role=role)

    async def delete_workspace(self, *, user_id: str, workspace_id: str) -> None:
        ws, role = await self._require_membership(user_id=user_id, workspace_id=workspace_id)
        require_true(role == "owner", code=ErrorCode.FORBIDDEN, message="仅 owner 可删除工作区")
        members = (
            await self._session.scalars(
                select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
            )
        ).all()
        for m in members:
            await self._session.delete(m)
        await self._session.delete(ws)
        await self._session.flush()

    async def _require_membership(
        self,
        *,
        user_id: str,
        workspace_id: str,
    ) -> tuple[Workspace, str]:
        stmt = (
            select(Workspace, WorkspaceMember.role)
            .join(
                WorkspaceMember,
                WorkspaceMember.workspace_id == Workspace.id,
            )
            .where(
                Workspace.id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "工作区不存在或无权访问")
        return row[0], row[1]

    @staticmethod
    def _to_user_out(user: User) -> UserOut:
        return UserOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=user.status,
            created_at=user.created_at,
        )

    @staticmethod
    def _to_workspace_out(ws: Workspace, *, role: str | None) -> WorkspaceOut:
        return WorkspaceOut(
            id=ws.id,
            name=ws.name,
            created_by=ws.created_by,
            role=role,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
        )

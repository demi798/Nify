"""identity 表模型。"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class User(IdMixin, TimestampMixin, Base):
    """用户（无 workspace_id）。"""

    __tablename__ = "identity_users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class Workspace(IdMixin, TimestampMixin, Base):
    """工作区（无 workspace_id）。"""

    __tablename__ = "identity_workspaces"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)


class WorkspaceMember(IdMixin, TimestampMixin, Base):
    """工作区成员。"""

    __tablename__ = "identity_workspace_members"

    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")

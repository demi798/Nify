"""mcp 表模型（对齐 mcp_servers DDL）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Computed, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import (
    Base,
    IdMixin,
    SoftDeleteMixin,
    TimestampMixin,
    WorkspaceMixin,
    assert_soft_delete_allowed,
)


class McpServer(IdMixin, WorkspaceMixin, TimestampMixin, SoftDeleteMixin, Base):
    """MCP 白名单连接。"""

    __tablename__ = "mcp_servers"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    transport: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    auth_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tool_whitelist: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    alive_name: Mapped[str | None] = mapped_column(
        String(128),
        Computed("IF(deleted_at IS NULL, name, NULL)", persisted=True),
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert_soft_delete_allowed(cls.__tablename__)

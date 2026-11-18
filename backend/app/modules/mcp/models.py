"""mcp 表模型（一期仅列表选项所需字段）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Computed, String
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
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    alive_name: Mapped[str | None] = mapped_column(
        String(128),
        Computed("IF(deleted_at IS NULL, name, NULL)", persisted=True),
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert_soft_delete_allowed(cls.__tablename__)

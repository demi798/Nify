"""agent 表模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Computed, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import (
    Base,
    IdMixin,
    SoftDeleteMixin,
    TimestampMixin,
    WorkspaceMixin,
    assert_soft_delete_allowed,
)


class Agent(IdMixin, WorkspaceMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Agent：提示词、模型绑定与工具配置。"""

    __tablename__ = "agent_agents"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provider_id: Mapped[str] = mapped_column(String(36), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_config_id: Mapped[str] = mapped_column(String(36), nullable=False)
    knowledge_base_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    mcp_server_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    # MySQL 生成列：存活时等于 name，软删后为 NULL（配合 uk_agent_ws_name）
    alive_name: Mapped[str | None] = mapped_column(
        String(128),
        Computed("IF(deleted_at IS NULL, name, NULL)", persisted=True),
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert_soft_delete_allowed(cls.__tablename__)


class AgentToolBinding(IdMixin, WorkspaceMixin, TimestampMixin, Base):
    """Agent ↔ MCP 工具绑定表（对应课程概念表 agent_tool）。

    Nify 约定：主键/外键均为 UUID v7 字符串；tool_id 语义落在 ``mcp_server_id``
    （一期将整台启用中的 MCP Server 视为可绑定工具）。唯一键 uk_agent_tool。
    """

    __tablename__ = "agent_tool_bindings"

    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    mcp_server_id: Mapped[str] = mapped_column(String(36), nullable=False)

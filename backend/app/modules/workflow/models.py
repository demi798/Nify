"""workflow 表模型（工作流 + 节点 + 边）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Computed, Float, String
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


class Workflow(IdMixin, WorkspaceMixin, TimestampMixin, SoftDeleteMixin, Base):
    """工作流定义头表。"""

    __tablename__ = "workflow_workflows"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    alive_name: Mapped[str | None] = mapped_column(
        String(128),
        Computed("IF(deleted_at IS NULL, name, NULL)", persisted=True),
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert_soft_delete_allowed(cls.__tablename__)


class WorkflowNode(IdMixin, WorkspaceMixin, TimestampMixin, SoftDeleteMixin, Base):
    """工作流节点。"""

    __tablename__ = "workflow_nodes"

    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False)
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    alive_node_key: Mapped[str | None] = mapped_column(
        String(64),
        Computed("IF(deleted_at IS NULL, node_key, NULL)", persisted=True),
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert_soft_delete_allowed(cls.__tablename__)


class WorkflowEdge(IdMixin, WorkspaceMixin, TimestampMixin, SoftDeleteMixin, Base):
    """工作流边。"""

    __tablename__ = "workflow_edges"

    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False)
    edge_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_handle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_handle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    alive_edge_key: Mapped[str | None] = mapped_column(
        String(64),
        Computed("IF(deleted_at IS NULL, edge_key, NULL)", persisted=True),
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert_soft_delete_allowed(cls.__tablename__)

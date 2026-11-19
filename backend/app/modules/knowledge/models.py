"""knowledge 表模型（与 001_init_schema / CLAUDE §4.7 对齐）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Boolean, Computed, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import (
    Base,
    IdMixin,
    SoftDeleteMixin,
    TimestampMixin,
    WorkspaceMixin,
    assert_soft_delete_allowed,
)


class KnowledgeBase(IdMixin, WorkspaceMixin, TimestampMixin, SoftDeleteMixin, Base):
    """知识库（小表，软删）。"""

    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    alive_name: Mapped[str | None] = mapped_column(
        String(128),
        Computed("IF(deleted_at IS NULL, name, NULL)", persisted=True),
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert_soft_delete_allowed(cls.__tablename__)


class KnowledgeDocument(IdMixin, WorkspaceMixin, TimestampMixin, SoftDeleteMixin, Base):
    """知识库文档元数据（中表，软删）；正文与向量不在本表。"""

    __tablename__ = "knowledge_documents"

    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        assert_soft_delete_allowed(cls.__tablename__)


class KnowledgeChunk(IdMixin, WorkspaceMixin, TimestampMixin, Base):
    """知识库分块（大表）；禁止软删；正文在 MySQL，向量在 Milvus。"""

    __tablename__ = "knowledge_chunks"

    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    milvus_pk: Mapped[str] = mapped_column(String(36), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

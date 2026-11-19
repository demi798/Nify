"""conversation 表模型（与 001_init_schema / CLAUDE §4.7 对齐）。"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin


class Conversation(IdMixin, WorkspaceMixin, TimestampMixin, Base):
    """会话：与某个 Agent 的一条对话线程。"""

    __tablename__ = "conversation_conversations"

    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)


class ConversationMessage(IdMixin, WorkspaceMixin, TimestampMixin, Base):
    """会话消息（大表）；禁止软删；流式结束一次 INSERT。"""

    __tablename__ = "conversation_messages"

    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

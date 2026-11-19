"""conversation 入参 / 出参。"""

from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, Field, field_validator

from app.core.schemas import CreateSchema, SchemaBase
from app.modules.conversation.constants import CONTENT_MAX_LENGTH, TITLE_MAX_LENGTH


class ConversationCreate(CreateSchema):
    """创建会话。"""

    agent_id: str = Field(
        min_length=36,
        max_length=36,
        validation_alias=AliasChoices("agent_id", "agentId"),
    )
    title: str | None = Field(
        default=None,
        max_length=TITLE_MAX_LENGTH,
    )

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None


class ConversationOut(SchemaBase):
    """会话出参。"""

    id: str
    workspace_id: str
    agent_id: str
    title: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class MessageOut(SchemaBase):
    """消息出参。"""

    id: str
    workspace_id: str
    conversation_id: str
    role: str
    status: str
    content: str
    token_count: int
    created_at: datetime
    updated_at: datetime


class ChatIn(CreateSchema):
    """发送本轮用户消息。"""

    content: str = Field(
        min_length=1,
        max_length=CONTENT_MAX_LENGTH,
    )

    @field_validator("content")
    @classmethod
    def _content(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("content 不能为空")
        return text


class ChatOut(SchemaBase):
    """非流式对话结果。"""

    conversation_id: str
    user_message: MessageOut
    assistant_message: MessageOut

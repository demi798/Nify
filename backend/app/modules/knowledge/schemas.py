"""knowledge 入参 / 出参。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from app.core.schemas import CreateSchema, SchemaBase, UpdateSchema
from app.modules.knowledge.constants import (
    DESCRIPTION_MAX_LENGTH,
    NAME_MAX_LENGTH,
)


class KnowledgeBaseCreate(CreateSchema):
    """创建知识库。"""

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    is_enabled: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("name 不能为空")
        return text

    @field_validator("description")
    @classmethod
    def _description(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None


class KnowledgeBaseUpdate(UpdateSchema):
    """更新知识库（部分字段）。"""

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    is_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        if not text:
            raise ValueError("name 不能为空")
        return text

    @field_validator("description")
    @classmethod
    def _description(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None


class KnowledgeBaseOut(SchemaBase):
    """知识库详情 / 列表项。"""

    id: str
    workspace_id: str
    name: str
    description: str | None = None
    is_enabled: bool = True
    created_by: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseOptionOut(SchemaBase):
    """供 Agent 绑定的知识库选项（仅启用中）。"""

    id: str
    name: str


class KnowledgeBaseRefItemOut(SchemaBase):
    """引用该知识库的资源摘要。"""

    id: str
    name: str
    kind: str  # agent | workflow


class KnowledgeBaseReferencesOut(SchemaBase):
    """知识库被引用情况（删除前校验 / 前端提示）。"""

    knowledge_base_id: str
    agents: list[KnowledgeBaseRefItemOut] = Field(default_factory=list)
    workflows: list[KnowledgeBaseRefItemOut] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.agents) + len(self.workflows)


class KnowledgeDocumentOut(SchemaBase):
    """文档元数据出参。"""

    id: str
    workspace_id: str
    knowledge_base_id: str
    name: str
    storage_key: str
    byte_size: int
    content_type: str
    status: str
    error_message: str | None = None
    chunk_count: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime


class KnowledgeChunkOut(SchemaBase):
    """分块出参（管理端预览；不含向量）。"""

    id: str
    workspace_id: str
    knowledge_base_id: str
    document_id: str
    seq: int
    milvus_pk: str
    content: str
    token_count: int
    created_at: datetime
    updated_at: datetime

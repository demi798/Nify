"""workflow 入参 / 出参（创建与详情结构一致：含 nodes / edges）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.core.schemas import CreateSchema, SchemaBase, UpdateSchema
from app.modules.workflow.constants import (
    DESCRIPTION_MAX_LENGTH,
    EDGE_KEY_MAX_LENGTH,
    NAME_MAX_LENGTH,
    NODE_KEY_MAX_LENGTH,
)


class WorkflowNodePosition(SchemaBase):
    """画布坐标。"""

    x: float = 0.0
    y: float = 0.0


class WorkflowNodeIn(CreateSchema):
    """创建/更新时的节点。"""

    key: str = Field(min_length=1, max_length=NODE_KEY_MAX_LENGTH)
    type: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    config: dict[str, Any] = Field(default_factory=dict)
    position: WorkflowNodePosition | None = None

    @field_validator("key", "type")
    @classmethod
    def _required_str(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None


class WorkflowEdgeIn(CreateSchema):
    """创建/更新时的边。"""

    key: str = Field(min_length=1, max_length=EDGE_KEY_MAX_LENGTH)
    source: str = Field(min_length=1, max_length=NODE_KEY_MAX_LENGTH)
    target: str = Field(min_length=1, max_length=NODE_KEY_MAX_LENGTH)
    source_handle: str | None = Field(default=None, max_length=64)
    target_handle: str | None = Field(default=None, max_length=64)
    label: str | None = Field(default=None, max_length=128)

    @field_validator("key", "source", "target")
    @classmethod
    def _required_str(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator("source_handle", "target_handle", "label")
    @classmethod
    def _opt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None


class WorkflowCreate(CreateSchema):
    """创建工作流：完整图写入三张表。"""

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    is_enabled: bool = True
    nodes: list[WorkflowNodeIn] = Field(default_factory=list)
    edges: list[WorkflowEdgeIn] = Field(default_factory=list)

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

    @model_validator(mode="after")
    def _graph(self) -> WorkflowCreate:
        keys = [n.key for n in self.nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("nodes.key 不能重复")
        edge_keys = [e.key for e in self.edges]
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("edges.key 不能重复")
        key_set = set(keys)
        for e in self.edges:
            if e.source not in key_set or e.target not in key_set:
                raise ValueError(f"边 {e.key} 引用了不存在的节点")
        return self


class WorkflowUpdate(UpdateSchema):
    """更新工作流：可整体替换图（nodes/edges 整批软删再插）。"""

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    is_enabled: bool | None = None
    nodes: list[WorkflowNodeIn] | None = None
    edges: list[WorkflowEdgeIn] | None = None

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

    @model_validator(mode="after")
    def _graph(self) -> WorkflowUpdate:
        if self.nodes is None and self.edges is None:
            return self
        nodes = self.nodes if self.nodes is not None else []
        edges = self.edges if self.edges is not None else []
        # 更新图时必须同时提供 nodes（允许空图）；edges 缺省当 []
        if self.nodes is None:
            raise ValueError("更新图结构时必须提供 nodes")
        keys = [n.key for n in nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("nodes.key 不能重复")
        edge_keys = [e.key for e in edges]
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("edges.key 不能重复")
        key_set = set(keys)
        for e in edges:
            if e.source not in key_set or e.target not in key_set:
                raise ValueError(f"边 {e.key} 引用了不存在的节点")
        return self


class WorkflowNodeOut(SchemaBase):
    """详情中的节点（与创建入参结构对齐）。"""

    key: str
    type: str
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    position: WorkflowNodePosition | None = None


class WorkflowEdgeOut(SchemaBase):
    """详情中的边。"""

    key: str
    source: str
    target: str
    source_handle: str | None = None
    target_handle: str | None = None
    label: str | None = None


class WorkflowListItemOut(SchemaBase):
    """列表项（不含完整图）。"""

    id: str
    workspace_id: str
    name: str
    description: str | None = None
    is_enabled: bool
    node_count: int = 0
    edge_count: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime


class WorkflowDetailOut(SchemaBase):
    """详情：含完整 nodes / edges。"""

    id: str
    workspace_id: str
    name: str
    description: str | None = None
    is_enabled: bool
    nodes: list[WorkflowNodeOut] = Field(default_factory=list)
    edges: list[WorkflowEdgeOut] = Field(default_factory=list)
    created_by: str
    created_at: datetime
    updated_at: datetime

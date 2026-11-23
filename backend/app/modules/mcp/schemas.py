"""mcp 入参 / 出参。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator  # noqa: F401 — Field 用于 Out

from app.core.schemas import CreateSchema, SchemaBase, UpdateSchema
from app.modules.mcp.constants import (
    ENDPOINT_MAX_LENGTH,
    NAME_MAX_LENGTH,
    TEST_STATUSES,
    TRANSPORTS,
)

TransportLiteral = Literal["http", "sse", "stdio"]
TestStatusLiteral = Literal["UP", "DOWN", "UNKNOWN"]


def _infer_transport(endpoint: str) -> str:
    raw = (endpoint or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return "http"
    return "stdio"


class McpServerOptionOut(SchemaBase):
    """工具多选选项（Agent 绑定用）。"""

    id: str
    name: str
    transport: str
    is_enabled: bool


class McpToolOut(SchemaBase):
    """MCP 工具简述。"""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


class McpBoundToolOut(SchemaBase):
    """Agent 绑定后可供 LLM tools 参数使用的工具（含所属 Server）。

    一期无独立 mcp_tool 表：从 agent_tool_bindings → mcp_servers → list_tools 实时组装。
    """

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    mcp_server_id: str
    original_name: str


class McpServerCreate(CreateSchema):
    """创建 MCP Server。"""

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    endpoint: str = Field(min_length=1, max_length=ENDPOINT_MAX_LENGTH)
    transport: str | None = Field(default=None, max_length=32)
    is_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("is_enabled", "enabled"),
    )
    auth_token: str | None = Field(default=None, max_length=512)
    tool_whitelist: list[str] | None = None
    config: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("name 不能为空")
        return text

    @field_validator("endpoint")
    @classmethod
    def _endpoint(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("endpoint 不能为空")
        return text

    @field_validator("transport")
    @classmethod
    def _transport(cls, v: str | None) -> str | None:
        if v is None:
            return None
        key = v.strip().lower()
        if key not in TRANSPORTS:
            raise ValueError(f"transport 须为 {sorted(TRANSPORTS)} 之一")
        return key

    @field_validator("auth_token")
    @classmethod
    def _auth(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None

    @field_validator("tool_whitelist")
    @classmethod
    def _whitelist(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for raw in v:
            name = (raw or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
        return out


class McpServerUpdate(UpdateSchema):
    """更新 MCP Server。"""

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    endpoint: str | None = Field(
        default=None, min_length=1, max_length=ENDPOINT_MAX_LENGTH
    )
    transport: str | None = Field(default=None, max_length=32)
    is_enabled: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("is_enabled", "enabled"),
    )
    auth_token: str | None = Field(default=None, max_length=512)
    tool_whitelist: list[str] | None = None
    config: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        if not text:
            raise ValueError("name 不能为空")
        return text

    @field_validator("endpoint")
    @classmethod
    def _endpoint(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        if not text:
            raise ValueError("endpoint 不能为空")
        return text

    @field_validator("transport")
    @classmethod
    def _transport(cls, v: str | None) -> str | None:
        if v is None:
            return None
        key = v.strip().lower()
        if key not in TRANSPORTS:
            raise ValueError(f"transport 须为 {sorted(TRANSPORTS)} 之一")
        return key

    @field_validator("auth_token")
    @classmethod
    def _auth(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None

    @field_validator("tool_whitelist")
    @classmethod
    def _whitelist(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for raw in v:
            name = (raw or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(name)
        return out


class McpServerListItemOut(SchemaBase):
    """列表项。"""

    id: str
    workspace_id: str
    name: str
    transport: str
    endpoint: str
    is_enabled: bool
    has_auth: bool = False
    tool_whitelist: list[str] | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class McpServerDetailOut(SchemaBase):
    """详情：含远端工具列表。"""

    id: str
    workspace_id: str
    name: str
    transport: str
    endpoint: str
    is_enabled: bool
    has_auth: bool = False
    tool_whitelist: list[str] | None = None
    config: dict[str, Any] | None = None
    tools: list[McpToolOut] = Field(default_factory=list)
    tools_error: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class McpServerTestOut(SchemaBase):
    """连通性测试结果。"""

    status: TestStatusLiteral
    latency_ms: int | None = None
    tool_count: int = 0
    tools: list[McpToolOut] = Field(default_factory=list)
    message: str | None = None
    checked_at: datetime

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        key = v.strip().upper()
        if key not in TEST_STATUSES:
            raise ValueError(f"status 须为 {sorted(TEST_STATUSES)} 之一")
        return key


class McpServerDebugIn(CreateSchema):
    """调试调用入参：指定工具名与 arguments。"""

    tool_name: str = Field(
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("tool_name", "toolName"),
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("arguments", "args"),
    )

    @field_validator("tool_name")
    @classmethod
    def _tool_name(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("tool_name 不能为空")
        return text


class McpServerDebugOut(SchemaBase):
    """调试调用出参。"""

    result: str
    elapsed_ms: int


# 供 schemas 外推断 transport
infer_transport = _infer_transport

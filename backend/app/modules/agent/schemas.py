"""agent 入参 / 出参。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field, field_validator

from app.core.schemas import CreateSchema, SchemaBase, UpdateSchema
from app.modules.agent.constants import (
    DEFAULT_MAX_CONTEXT_TURNS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    MAX_CONTEXT_TURNS_MAX,
    MAX_CONTEXT_TURNS_MIN,
    MAX_TOKENS_MAX,
    MAX_TOKENS_MIN,
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
)


class AgentCreate(CreateSchema):
    """创建 Agent；兼容 camelCase 入参别名。"""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    system_prompt: str | None = Field(
        default=None,
        max_length=50_000,
        validation_alias=AliasChoices("system_prompt", "systemPrompt"),
    )
    model_config_id: str = Field(
        min_length=36,
        max_length=36,
        validation_alias=AliasChoices("model_config_id", "modelConfigId"),
    )
    temperature: float = Field(
        default=DEFAULT_TEMPERATURE,
        ge=TEMPERATURE_MIN,
        le=TEMPERATURE_MAX,
    )
    max_tokens: int = Field(
        default=DEFAULT_MAX_TOKENS,
        ge=MAX_TOKENS_MIN,
        le=MAX_TOKENS_MAX,
        validation_alias=AliasChoices("max_tokens", "maxTokens"),
    )
    max_context_turns: int = Field(
        default=DEFAULT_MAX_CONTEXT_TURNS,
        ge=MAX_CONTEXT_TURNS_MIN,
        le=MAX_CONTEXT_TURNS_MAX,
        validation_alias=AliasChoices("max_context_turns", "maxContextTurns"),
    )
    tool_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tool_ids", "toolIds"),
    )
    is_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("is_enabled", "isEnabled"),
    )

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

    @field_validator("system_prompt")
    @classmethod
    def _system_prompt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @field_validator("tool_ids")
    @classmethod
    def _tool_ids(cls, v: list[str]) -> list[str]:
        # 去重保序；空串剔除
        seen: set[str] = set()
        out: list[str] = []
        for raw in v or []:
            tid = (raw or "").strip()
            if not tid or tid in seen:
                continue
            seen.add(tid)
            out.append(tid)
        return out


class AgentUpdate(UpdateSchema):
    """更新 Agent；未传字段保持原值。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    system_prompt: str | None = Field(
        default=None,
        max_length=50_000,
        validation_alias=AliasChoices("system_prompt", "systemPrompt"),
    )
    model_config_id: str | None = Field(
        default=None,
        min_length=36,
        max_length=36,
        validation_alias=AliasChoices("model_config_id", "modelConfigId"),
    )
    temperature: float | None = Field(
        default=None,
        ge=TEMPERATURE_MIN,
        le=TEMPERATURE_MAX,
    )
    max_tokens: int | None = Field(
        default=None,
        ge=MAX_TOKENS_MIN,
        le=MAX_TOKENS_MAX,
        validation_alias=AliasChoices("max_tokens", "maxTokens"),
    )
    max_context_turns: int | None = Field(
        default=None,
        ge=MAX_CONTEXT_TURNS_MIN,
        le=MAX_CONTEXT_TURNS_MAX,
        validation_alias=AliasChoices("max_context_turns", "maxContextTurns"),
    )
    tool_ids: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices("tool_ids", "toolIds"),
    )
    is_enabled: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("is_enabled", "isEnabled"),
    )

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

    @field_validator("system_prompt")
    @classmethod
    def _system_prompt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @field_validator("tool_ids")
    @classmethod
    def _tool_ids(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for raw in v:
            tid = (raw or "").strip()
            if not tid or tid in seen:
                continue
            seen.add(tid)
            out.append(tid)
        return out


class AgentListItemOut(SchemaBase):
    """Agent 列表项（不含超长 system_prompt）。"""

    id: str
    workspace_id: str
    name: str
    description: str | None = None
    model_config_id: str
    model_provider_id: str
    model_name: str
    temperature: float
    tool_count: int = 0
    is_enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class AgentDetailOut(SchemaBase):
    """Agent 详情出参（对应 AgentDetailResponse）。"""

    id: str
    workspace_id: str
    name: str
    description: str | None = None
    system_prompt: str | None = None
    model_config_id: str
    model_provider_id: str
    model_name: str
    temperature: float
    max_tokens: int
    max_context_turns: int
    tool_ids: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    is_enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    # 可选展示：来自跨模块绑定校验时的快照（创建后回填）
    provider_name: str | None = None
    model_display_name: str | None = None

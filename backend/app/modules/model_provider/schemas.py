"""model_provider 入参 / 出参（对齐 CLAUDE.md ApiResult + 嵌套 modelConfig/health）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator

from app.core.schemas import CreateSchema, SchemaBase, UpdateSchema
from app.modules.model_provider.constants import (
    AUTH_SCHEMES,
    HEALTH_STATUSES,
    MODALITIES,
    MODEL_STATUSES,
    PROVIDER_TYPES,
)

ProviderTypeLiteral = Literal[
    "openai", "openai_compatible", "claude", "gemini", "ollama"
]
AuthSchemeLiteral = Literal["api_key", "api_key_header", "none"]
HealthStatusLiteral = Literal["UNKNOWN", "UP", "DEGRADED", "DOWN"]


def _validate_optional_http_url(value: str | None) -> str | None:
    """校验可选 Base URL：空则 None；须为 http(s) 且含主机。"""
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url 须为 http(s):// 开头的合法地址")
    if any(ch in raw for ch in (" ", '"', "'", "<", ">")):
        raise ValueError("base_url 含非法字符")
    return raw.rstrip("/")


# ---------- 模型目录 ----------


class ProviderModelCreate(CreateSchema):
    """新建模型目录项。"""

    model_key: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    modality: str = "chat"
    context_window: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    capabilities: dict[str, Any] | None = None
    is_default: bool = False
    is_enabled: bool = True
    status: str = "available"

    @field_validator("modality")
    @classmethod
    def _modality(cls, v: str) -> str:
        key = v.strip().lower()
        if key not in MODALITIES:
            raise ValueError(f"modality 须为 {sorted(MODALITIES)} 之一")
        return key

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        key = v.strip().lower()
        if key not in MODEL_STATUSES:
            raise ValueError(f"status 须为 {sorted(MODEL_STATUSES)} 之一")
        return key


class ProviderModelUpdate(UpdateSchema):
    """更新模型目录项。"""

    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    modality: str | None = None
    context_window: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    capabilities: dict[str, Any] | None = None
    is_default: bool | None = None
    is_enabled: bool | None = None
    status: str | None = None

    @field_validator("modality")
    @classmethod
    def _modality(cls, v: str | None) -> str | None:
        if v is None:
            return None
        key = v.strip().lower()
        if key not in MODALITIES:
            raise ValueError(f"modality 须为 {sorted(MODALITIES)} 之一")
        return key

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is None:
            return None
        key = v.strip().lower()
        if key not in MODEL_STATUSES:
            raise ValueError(f"status 须为 {sorted(MODEL_STATUSES)} 之一")
        return key


class ProviderModelOut(SchemaBase):
    """模型目录出参。"""

    id: str
    workspace_id: str
    provider_id: str
    model_key: str
    display_name: str
    modality: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    capabilities: dict[str, Any] | None = None
    is_default: bool
    is_enabled: bool
    status: str
    created_at: datetime
    updated_at: datetime


# ---------- modelConfig / health 嵌套体 ----------


class ModelConfigIn(CreateSchema):
    """创建/更新时的模型接入配置（可嵌套提交）。"""

    base_url: str | None = Field(default=None, max_length=512)
    auth_scheme: str | None = Field(default=None, max_length=32)
    api_key: str | None = Field(default=None, max_length=512)
    auth_extra: dict[str, Any] | None = None
    default_model_key: str | None = Field(default=None, max_length=128)
    config: dict[str, Any] | None = None
    models: list[ProviderModelCreate] | None = None

    @field_validator("base_url")
    @classmethod
    def _base_url(cls, v: str | None) -> str | None:
        return _validate_optional_http_url(v)

    @field_validator("auth_scheme")
    @classmethod
    def _auth_scheme(cls, v: str | None) -> str | None:
        if v is None:
            return None
        key = v.strip().lower()
        if key not in AUTH_SCHEMES:
            raise ValueError(f"auth_scheme 须为 {sorted(AUTH_SCHEMES)} 之一")
        return key


class ModelConfigOut(SchemaBase):
    """详情/列表中的模型接入配置（不含明文密钥）。"""

    base_url: str | None = None
    auth_scheme: str
    has_api_key: bool
    auth_extra: dict[str, Any] | None = None
    default_model_key: str | None = None
    config: dict[str, Any] | None = None
    models: list[ProviderModelOut] | None = None


class ProviderHealthInfo(SchemaBase):
    """连通性健康态（对齐 provider_health 语义）。"""

    status: HealthStatusLiteral
    latency_ms: int | None = None
    last_success_at: datetime | None = None
    fail_count: int = 0
    checked_at: datetime | None = None
    error_code: str | None = None
    message: str | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        key = v.strip().upper()
        if key not in HEALTH_STATUSES:
            raise ValueError(f"status 须为 {sorted(HEALTH_STATUSES)} 之一")
        return key


# ---------- Provider CRUD ----------


class ProviderCreate(CreateSchema):
    """新建提供商。支持扁平字段或嵌套 modelConfig（嵌套优先）。"""

    name: str = Field(min_length=1, max_length=128)
    provider_type: str = Field(min_length=1, max_length=32)
    is_enabled: bool = True
    # 扁平字段（与前端表单兼容）
    base_url: str | None = Field(default=None, max_length=512)
    auth_scheme: str | None = Field(default=None, max_length=32)
    api_key: str | None = Field(default=None, max_length=512)
    auth_extra: dict[str, Any] | None = None
    default_model_key: str | None = Field(default=None, max_length=128)
    config: dict[str, Any] | None = None
    models: list[ProviderModelCreate] | None = None
    # 嵌套配置（可选）
    modelConfig: ModelConfigIn | None = None

    @field_validator("provider_type")
    @classmethod
    def _provider_type(cls, v: str) -> str:
        key = v.strip().lower()
        if key not in PROVIDER_TYPES:
            raise ValueError(f"provider_type 须为 {sorted(PROVIDER_TYPES)} 之一")
        return key

    @field_validator("base_url")
    @classmethod
    def _base_url(cls, v: str | None) -> str | None:
        return _validate_optional_http_url(v)

    @field_validator("auth_scheme")
    @classmethod
    def _auth_scheme(cls, v: str | None) -> str | None:
        if v is None:
            return None
        key = v.strip().lower()
        if key not in AUTH_SCHEMES:
            raise ValueError(f"auth_scheme 须为 {sorted(AUTH_SCHEMES)} 之一")
        return key

    @model_validator(mode="after")
    def _merge_model_config(self) -> ProviderCreate:
        """嵌套 modelConfig 覆盖同名扁平字段。"""
        nested = self.modelConfig
        if nested is None:
            return self
        data = nested.model_dump(exclude_unset=True)
        for key, value in data.items():
            if key in type(self).model_fields:
                setattr(self, key, value)
        return self


class ProviderUpdate(UpdateSchema):
    """更新提供商（api_key 省略则保留原密钥）。支持嵌套 modelConfig。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_enabled: bool | None = None
    base_url: str | None = Field(default=None, max_length=512)
    auth_scheme: str | None = Field(default=None, max_length=32)
    api_key: str | None = Field(default=None, max_length=512)
    auth_extra: dict[str, Any] | None = None
    default_model_key: str | None = Field(default=None, max_length=128)
    config: dict[str, Any] | None = None
    modelConfig: ModelConfigIn | None = None

    @field_validator("base_url")
    @classmethod
    def _base_url(cls, v: str | None) -> str | None:
        return _validate_optional_http_url(v)

    @field_validator("auth_scheme")
    @classmethod
    def _auth_scheme(cls, v: str | None) -> str | None:
        if v is None:
            return None
        key = v.strip().lower()
        if key not in AUTH_SCHEMES:
            raise ValueError(f"auth_scheme 须为 {sorted(AUTH_SCHEMES)} 之一")
        return key

    @model_validator(mode="after")
    def _merge_model_config(self) -> ProviderUpdate:
        nested = self.modelConfig
        if nested is None:
            return self
        data = nested.model_dump(exclude_unset=True)
        for key, value in data.items():
            if key not in type(self).model_fields:
                continue
            setattr(self, key, value)
            self.model_fields_set.add(key)
        return self

    def changed_fields(self) -> dict[str, Any]:
        """部分更新字段；忽略仅作容器的 modelConfig 键。"""
        data = self.model_dump(exclude_unset=True)
        data.pop("modelConfig", None)
        return data


class ProviderOut(SchemaBase):
    """提供商出参：含嵌套 modelConfig 与 health。"""

    id: str
    workspace_id: str
    name: str
    provider_type: str
    is_enabled: bool
    modelConfig: ModelConfigOut
    health: ProviderHealthInfo
    created_by: str
    created_at: datetime
    updated_at: datetime


class ProviderHealthOut(SchemaBase):
    """连通性测试结果：id + health。"""

    id: str
    health: ProviderHealthInfo


class EnabledModelBinding(SchemaBase):
    """跨模块：按模型目录 id 校验后返回的绑定信息（无凭证）。"""

    model_id: str
    provider_id: str
    model_key: str
    display_name: str
    provider_name: str
    provider_type: str
    is_enabled: bool
    health_status: str

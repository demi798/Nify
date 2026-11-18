"""model_provider 表模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, WorkspaceMixin


class Provider(IdMixin, WorkspaceMixin, TimestampMixin, Base):
    """模型提供商连接实例。"""

    __tablename__ = "model_provider_providers"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    auth_scheme: Mapped[str] = mapped_column(String(32), nullable=False, default="api_key")
    credentials_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    auth_extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    default_model_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    health_status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    health_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    health_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    health_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    health_fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    health_last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)


class ProviderModel(IdMixin, WorkspaceMixin, TimestampMixin, Base):
    """提供商下的模型目录项。"""

    __tablename__ = "model_provider_models"

    provider_id: Mapped[str] = mapped_column(String(36), nullable=False)
    model_key: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    modality: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capabilities: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="available")

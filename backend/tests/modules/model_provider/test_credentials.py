"""P0：get_runtime_credentials 禁用 / DOWN 拒绝。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.model_provider.constants import (
    HEALTH_STATUS_DOWN,
    HEALTH_STATUS_UP,
)
from app.modules.model_provider.service import ModelProviderService

_WS = "019a0000-0000-7000-8000-0000000000a1"
_PID = "019a0000-0000-7000-8000-0000000000p1"


def _provider(
    *,
    enabled: bool = True,
    health: str = HEALTH_STATUS_UP,
) -> MagicMock:
    p = MagicMock()
    p.id = _PID
    p.is_enabled = enabled
    p.health_status = health
    p.updated_at = datetime.now(timezone.utc)
    p.provider_type = "fake"
    p.auth_scheme = "bearer"
    p.credentials_encrypted = None
    p.auth_extra = {}
    p.default_model_key = "fake"
    p.config = {}
    return p


@pytest.mark.asyncio
async def should_refuse_credentials_when_provider_disabled(monkeypatch):
    # Given：提供商禁用
    monkeypatch.setattr(
        "app.modules.model_provider.service.get_cached_runtime",
        lambda _pid: None,
    )
    svc = ModelProviderService(MagicMock())
    svc._get_provider_entity = AsyncMock(
        return_value=_provider(enabled=False)
    )

    # When / Then
    with pytest.raises(AppError) as ei:
        await svc.get_runtime_credentials(
            workspace_id=_WS, provider_id=_PID
        )
    assert ei.value.code == ErrorCode.FORBIDDEN.value
    assert "禁用" in ei.value.message


@pytest.mark.asyncio
async def should_refuse_credentials_when_health_is_down(monkeypatch):
    # Given：健康态 DOWN
    monkeypatch.setattr(
        "app.modules.model_provider.service.get_cached_runtime",
        lambda _pid: None,
    )
    svc = ModelProviderService(MagicMock())
    svc._get_provider_entity = AsyncMock(
        return_value=_provider(health=HEALTH_STATUS_DOWN)
    )

    # When / Then
    with pytest.raises(AppError) as ei:
        await svc.get_runtime_credentials(
            workspace_id=_WS, provider_id=_PID
        )
    assert ei.value.code == ErrorCode.LLM_UNAVAILABLE.value
    assert "DOWN" in ei.value.message


@pytest.mark.asyncio
async def should_return_runtime_shape_when_provider_healthy(monkeypatch):
    # Given：启用且 UP；凭证解密返回假 key
    monkeypatch.setattr(
        "app.modules.model_provider.service.get_cached_runtime",
        lambda _pid: None,
    )
    monkeypatch.setattr(
        "app.modules.model_provider.service.put_cached_runtime",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "app.modules.model_provider.service.get_api_key",
        lambda _enc: "fake-key",
    )
    svc = ModelProviderService(MagicMock())
    provider = _provider()
    svc._get_provider_entity = AsyncMock(return_value=provider)
    svc.resolve_base_url = MagicMock(return_value="http://127.0.0.1")

    # When
    creds = await svc.get_runtime_credentials(
        workspace_id=_WS, provider_id=_PID
    )

    # Then：字段形状可用，不含缓存内部 _rev
    assert creds["provider_id"] == _PID
    assert creds["provider_type"] == "fake"
    assert creds["api_key"] == "fake-key"
    assert creds["base_url"] == "http://127.0.0.1"
    assert "_rev" not in creds

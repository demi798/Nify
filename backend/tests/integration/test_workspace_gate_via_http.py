"""P0 集成冒烟：工作区门禁 HTTP 信封（无真实 MySQL，依赖覆盖）。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.deps import CurrentUser, CurrentWorkspace, get_current_user, get_current_workspace
from app.core.db import get_session
from app.core.exceptions import register_exception_handlers
from app.core.response import ApiResult, AppJSONResponse

_USER = "019a0000-0000-7000-8000-0000000000a1"
_WS = "019a0000-0000-7000-8000-0000000000b1"


def _build_app(*, member_exists: bool) -> FastAPI:
    app = FastAPI(default_response_class=AppJSONResponse)
    register_exception_handlers(app)

    @app.get("/api/v1/probe")
    async def probe(
        ws: CurrentWorkspace = Depends(get_current_workspace),
    ) -> ApiResult[dict]:
        return ApiResult.ok({"workspace_id": ws.workspace_id, "user_id": ws.user_id})

    async def _user() -> CurrentUser:
        return CurrentUser(user_id=_USER)

    async def _session():
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=1 if member_exists else None)
        yield session

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_session] = _session
    return app


@pytest.mark.asyncio
async def should_fail_when_workspace_header_missing_via_http():
    # Given：已登录依赖覆盖，无 X-Workspace-Id
    app = _build_app(member_exists=True)
    transport = ASGITransport(app=app)

    # When
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/probe")

    # Then：统一信封，data 为空
    body = resp.json()
    assert body.get("data") is None
    assert body.get("code")
    assert body.get("message")


@pytest.mark.asyncio
async def should_forbid_when_caller_not_member_via_http():
    # Given：Header 合法但非成员
    app = _build_app(member_exists=False)
    transport = ASGITransport(app=app)

    # When
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/probe",
            headers={"X-Workspace-Id": _WS},
        )

    # Then
    body = resp.json()
    assert resp.status_code == 403
    assert body.get("data") is None
    assert body.get("code") == "A0101"
    assert "不是该工作区成员" in (body.get("message") or "")


@pytest.mark.asyncio
async def should_pass_probe_when_member_via_http():
    # Given：成员存在
    app = _build_app(member_exists=True)
    transport = ASGITransport(app=app)

    # When
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/probe",
            headers={"X-Workspace-Id": _WS},
        )

    # Then
    body = resp.json()
    assert body.get("code") == "0"
    assert body["data"]["workspace_id"] == _WS
    assert body["data"]["user_id"] == _USER

"""P0：McpService.call_tool 白名单与停用门禁。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.mcp.service import McpService

_WS = "019a0000-0000-7000-8000-0000000000a1"
_SERVER = "019a0000-0000-7000-8000-0000000000s1"


def _server(
    *,
    enabled: bool = True,
    whitelist: list[str] | None = None,
) -> MagicMock:
    row = MagicMock()
    row.is_enabled = enabled
    row.tool_whitelist = whitelist
    row.transport = "streamable_http"
    row.endpoint = "http://127.0.0.1:8100/mcp"
    row.auth_encrypted = None
    row.config = {}
    return row


@pytest.mark.asyncio
async def should_refuse_call_tool_when_name_not_in_whitelist(monkeypatch):
    # Given：白名单仅 safe_tool；远端可追踪
    remote = AsyncMock(return_value="should-not-run")
    monkeypatch.setattr(
        "app.modules.mcp.service.mcp_client.call_tool", remote
    )
    monkeypatch.setattr(
        "app.modules.mcp.service.get_auth_token", lambda _: None
    )
    svc = McpService(MagicMock())
    svc._get_server_entity = AsyncMock(  # noqa: SLF001 — 测公开 call_tool 分支
        return_value=_server(whitelist=["safe_tool"])
    )

    # When / Then
    with pytest.raises(AppError) as ei:
        await svc.call_tool(
            workspace_id=_WS,
            mcp_server_id=_SERVER,
            tool_name="not_allowed",
            arguments={},
        )
    assert ei.value.code == ErrorCode.FORBIDDEN.value
    assert "白名单" in ei.value.message
    remote.assert_not_awaited()


@pytest.mark.asyncio
async def should_invoke_remote_when_tool_name_in_whitelist(monkeypatch):
    # Given：命中白名单
    remote = AsyncMock(return_value="tool-ok")
    monkeypatch.setattr(
        "app.modules.mcp.service.mcp_client.call_tool", remote
    )
    monkeypatch.setattr(
        "app.modules.mcp.service.get_auth_token", lambda _: "tok"
    )
    svc = McpService(MagicMock())
    svc._get_server_entity = AsyncMock(
        return_value=_server(whitelist=["safe_tool"])
    )

    # When
    result = await svc.call_tool(
        workspace_id=_WS,
        mcp_server_id=_SERVER,
        tool_name="safe_tool",
        arguments={"x": 1},
    )

    # Then
    assert result == "tool-ok"
    remote.assert_awaited_once()
    kwargs = remote.await_args.kwargs
    assert kwargs["tool_name"] == "safe_tool"
    assert kwargs["arguments"] == {"x": 1}


@pytest.mark.asyncio
async def should_refuse_call_tool_when_server_disabled(monkeypatch):
    # Given：Server 停用
    remote = AsyncMock()
    monkeypatch.setattr(
        "app.modules.mcp.service.mcp_client.call_tool", remote
    )
    svc = McpService(MagicMock())
    svc._get_server_entity = AsyncMock(
        return_value=_server(enabled=False, whitelist=None)
    )

    # When / Then
    with pytest.raises(AppError) as ei:
        await svc.call_tool(
            workspace_id=_WS,
            mcp_server_id=_SERVER,
            tool_name="any",
            arguments={},
        )
    assert ei.value.code == ErrorCode.BAD_REQUEST.value
    assert "停用" in ei.value.message
    remote.assert_not_awaited()

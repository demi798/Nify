"""P0：tool_loop 成功执行与 MCP 失败回传。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.conversation.internal.tool_loop import (
    append_tool_results,
    chat_with_tools,
)
from app.modules.mcp.schemas import McpBoundToolOut
from app.shared.llm import ChatMessage, ChatResponse

_WS = "019a0000-0000-7000-8000-0000000000a1"
_SERVER = "019a0000-0000-7000-8000-0000000000s1"


def _bound(name: str = "refund_query") -> McpBoundToolOut:
    return McpBoundToolOut(
        name=name,
        description="q",
        input_schema={"type": "object"},
        mcp_server_id=_SERVER,
        original_name=name,
    )


def _tool_call(*, name: str, arguments: str, call_id: str = "c1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


@pytest.mark.asyncio
async def should_append_tool_result_when_mcp_call_succeeds():
    # Given：合法 tool_calls；MCP 返回成功文本
    mcp = MagicMock()
    mcp.call_tool = AsyncMock(return_value="ok-result")
    first = ChatResponse(
        content="",
        finish_reason="tool_calls",
        tool_calls=[_tool_call(name="refund_query", arguments='{"order_id":"1"}')],
    )

    # When
    messages = await append_tool_results(
        workspace_id=_WS,
        llm_messages=[ChatMessage(role="user", content="查退款")],
        first=first,
        bound_tools=[_bound()],
        mcp=mcp,
    )

    # Then
    tool_msgs = [m for m in messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].content == "ok-result"
    mcp.call_tool.assert_awaited_once_with(
        workspace_id=_WS,
        mcp_server_id=_SERVER,
        tool_name="refund_query",
        arguments={"order_id": "1"},
    )


@pytest.mark.asyncio
async def should_return_tool_error_message_when_mcp_call_raises():
    # Given：call_tool 抛业务错误，不应向外冒泡成 500
    mcp = MagicMock()
    mcp.call_tool = AsyncMock(
        side_effect=AppError(ErrorCode.BAD_REQUEST, "远端超时")
    )
    first = ChatResponse(
        content=None,
        finish_reason="tool_calls",
        tool_calls=[_tool_call(name="refund_query", arguments="{}")],
    )

    # When
    messages = await append_tool_results(
        workspace_id=_WS,
        llm_messages=[ChatMessage(role="user", content="q")],
        first=first,
        bound_tools=[_bound()],
        mcp=mcp,
    )

    # Then：仍有 tool 消息，内容含失败说明
    tool_msgs = [m for m in messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "工具执行失败" in (tool_msgs[0].content or "")
    assert "远端超时" in (tool_msgs[0].content or "")


@pytest.mark.asyncio
async def should_return_invalid_json_tool_message_without_calling_mcp():
    # Given：arguments 非法 JSON
    mcp = MagicMock()
    mcp.call_tool = AsyncMock()
    first = ChatResponse(
        content="",
        finish_reason="tool_calls",
        tool_calls=[_tool_call(name="refund_query", arguments="{not-json")],
    )

    # When
    messages = await append_tool_results(
        workspace_id=_WS,
        llm_messages=[ChatMessage(role="user", content="q")],
        first=first,
        bound_tools=[_bound()],
        mcp=mcp,
    )

    # Then
    tool_msgs = [m for m in messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "不是合法 JSON" in (tool_msgs[0].content or "")
    mcp.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def should_call_llm_twice_when_first_response_has_tool_calls(monkeypatch):
    # Given：首次 tool_calls，二次返回最终文本
    gateway = MagicMock()
    first = ChatResponse(
        content="",
        finish_reason="tool_calls",
        tool_calls=[_tool_call(name="refund_query", arguments="{}")],
    )
    second = ChatResponse(content="最终回复", finish_reason="stop")
    gateway.chat = AsyncMock(side_effect=[first, second])
    monkeypatch.setattr(
        "app.modules.conversation.internal.tool_loop.get_llm_gateway",
        lambda: gateway,
    )
    mcp = MagicMock()
    mcp.call_tool = AsyncMock(return_value="tool-ok")
    agent = MagicMock()
    agent.model_name = "fake"
    agent.temperature = 0.2
    agent.max_tokens = 128
    creds = {"provider_type": "fake", "api_key": "k", "base_url": None}

    # When
    out = await chat_with_tools(
        workspace_id=_WS,
        agent=agent,
        creds=creds,
        llm_messages=[ChatMessage(role="user", content="hi")],
        openai_tools=[{"type": "function", "function": {"name": "refund_query"}}],
        bound_tools=[_bound()],
        mcp=mcp,
    )

    # Then
    assert out.content == "最终回复"
    assert gateway.chat.await_count == 2
    mcp.call_tool.assert_awaited_once()

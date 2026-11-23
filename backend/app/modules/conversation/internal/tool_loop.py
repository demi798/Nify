"""MCP 工具调用回合：首次非流式 → 执行工具 → 二次补全。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.exceptions import AppError
from app.modules.conversation.constants import ROLE_ASSISTANT, ROLE_TOOL
from app.modules.mcp.service import McpBoundToolOut, McpService
from app.modules.model_provider.service import (
    ChatMessage,
    ChatResponse,
    get_llm_gateway,
)

logger = logging.getLogger(__name__)


async def chat_with_tools(
    *,
    workspace_id: str,
    agent: Any,
    creds: dict[str, Any],
    llm_messages: list[ChatMessage],
    openai_tools: list[dict[str, Any]],
    bound_tools: list[McpBoundToolOut],
    mcp: McpService,
) -> ChatResponse:
    """非流式：首次带 tools；若 tool_calls 则执行后二次调用。"""
    gateway = get_llm_gateway()
    first = await gateway.chat(
        provider=str(creds["provider_type"]),
        workspace_id=workspace_id,
        model=agent.model_name,
        messages=llm_messages,
        api_key=str(creds.get("api_key") or ""),
        base_url=creds.get("base_url"),
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tools=openai_tools,
    )
    finish = (first.finish_reason or "").lower()
    if finish != "tool_calls" and not first.tool_calls:
        return first
    follow = await append_tool_results(
        workspace_id=workspace_id,
        llm_messages=list(llm_messages),
        first=first,
        bound_tools=bound_tools,
        mcp=mcp,
    )
    return await gateway.chat(
        provider=str(creds["provider_type"]),
        workspace_id=workspace_id,
        model=agent.model_name,
        messages=follow,
        api_key=str(creds.get("api_key") or ""),
        base_url=creds.get("base_url"),
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
    )


async def append_tool_results(
    *,
    workspace_id: str,
    llm_messages: list[ChatMessage],
    first: ChatResponse,
    bound_tools: list[McpBoundToolOut],
    mcp: McpService,
) -> list[ChatMessage]:
    """把 assistant.tool_calls + 各 tool 结果追加进 messages。"""
    by_name = {t.name: t for t in bound_tools}
    calls = list(first.tool_calls or [])
    messages = list(llm_messages)
    messages.append(
        ChatMessage(
            role=ROLE_ASSISTANT,
            content=first.content or None,
            tool_calls=calls,
        )
    )
    for call in calls:
        call_id = str(call.get("id") or "")
        fn = call.get("function") if isinstance(call.get("function"), dict) else {}
        tool_name = str((fn or {}).get("name") or "")
        raw_args = (fn or {}).get("arguments") or "{}"
        try:
            arguments = (
                json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            )
            if not isinstance(arguments, dict):
                arguments = {}
        except Exception:  # noqa: BLE001 — 非法 JSON 回传 LLM
            messages.append(
                ChatMessage(
                    role=ROLE_TOOL,
                    content=f"工具参数不是合法 JSON：{raw_args!r}",
                    tool_call_id=call_id or None,
                    name=tool_name or None,
                )
            )
            continue

        bound = by_name.get(tool_name)
        if bound is None:
            tool_content = f"未找到工具定义：{tool_name}"
        else:
            try:
                tool_content = await mcp.call_tool(
                    workspace_id=workspace_id,
                    mcp_server_id=bound.mcp_server_id,
                    tool_name=bound.original_name,
                    arguments=arguments,
                )
            except Exception as exc:  # noqa: BLE001 — 失败回传，不中断对话
                logger.warning(
                    "tool call failed name=%s server=%s err=%s",
                    tool_name,
                    bound.mcp_server_id,
                    exc,
                )
                msg = (
                    exc.message
                    if isinstance(exc, AppError)
                    else (str(exc) or "工具调用失败")
                )
                tool_content = f"工具执行失败：{msg}"

        messages.append(
            ChatMessage(
                role=ROLE_TOOL,
                content=tool_content or "",
                tool_call_id=call_id or None,
                name=tool_name or None,
            )
        )
    return messages

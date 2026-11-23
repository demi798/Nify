"""MCP Client 薄封装：只做协议连通与 list_tools，不含业务权限。"""

from __future__ import annotations

import logging
import shlex
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.mcp.constants import (
    CONNECT_TIMEOUT_SECONDS,
    TRANSPORT_HTTP,
    TRANSPORT_SSE,
    TRANSPORT_STDIO,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class McpToolInfo:
    """远端工具简述。"""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


@dataclass(slots=True)
class McpConnectResult:
    """连通性探测结果。"""

    ok: bool
    latency_ms: int | None = None
    tools: list[McpToolInfo] = field(default_factory=list)
    error_message: str | None = None


def _build_client(
    *,
    transport: str,
    endpoint: str,
    auth_token: str | None = None,
    config: dict[str, Any] | None = None,
):
    """按 transport 构造官方 ``mcp.Client``（未进入上下文）。"""
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    cfg = dict(config or {})
    timeout = float(cfg.get("timeout") or CONNECT_TIMEOUT_SECONDS)

    if transport == TRANSPORT_HTTP:
        url = endpoint.strip()
        if auth_token:
            import httpx2
            from mcp.client.streamable_http import streamable_http_client

            http = httpx2.AsyncClient(
                headers={"Authorization": f"Bearer {auth_token}"},
                timeout=httpx2.Timeout(timeout, read=max(timeout, 60.0)),
            )
            return Client(
                streamable_http_client(url, http_client=http),
                read_timeout_seconds=timeout,
            )
        return Client(url, read_timeout_seconds=timeout)

    if transport == TRANSPORT_SSE:
        from mcp.client.sse import sse_client

        headers: dict[str, Any] | None = None
        if auth_token:
            headers = {"Authorization": f"Bearer {auth_token}"}
        return Client(
            sse_client(url=endpoint.strip(), headers=headers, timeout=timeout),
            read_timeout_seconds=timeout,
        )

    if transport == TRANSPORT_STDIO:
        # endpoint：可执行命令行；config.args 可追加参数
        parts = shlex.split(endpoint.strip())
        if not parts:
            raise AppError(ErrorCode.BAD_REQUEST, "stdio endpoint 不能为空")
        extra_args = cfg.get("args")
        args: list[str] = list(parts[1:])
        if isinstance(extra_args, list):
            args.extend(str(a) for a in extra_args)
        env = cfg.get("env") if isinstance(cfg.get("env"), dict) else None
        params = StdioServerParameters(
            command=parts[0],
            args=args,
            env={str(k): str(v) for k, v in env.items()} if env else None,
        )
        return Client(params, read_timeout_seconds=timeout)

    raise AppError(ErrorCode.BAD_REQUEST, f"不支持的 transport：{transport}")


def _tool_from_sdk(tool: Any) -> McpToolInfo:
    name = str(getattr(tool, "name", "") or "")
    desc = getattr(tool, "description", None)
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = getattr(tool, "input_schema", None)
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(mode="python")
    if schema is not None and not isinstance(schema, dict):
        schema = None
    return McpToolInfo(
        name=name,
        description=str(desc) if desc else None,
        input_schema=schema,
    )


async def list_tools(
    *,
    transport: str,
    endpoint: str,
    auth_token: str | None = None,
    config: dict[str, Any] | None = None,
) -> list[McpToolInfo]:
    """列出远端工具；失败抛 AppError。"""
    client = _build_client(
        transport=transport,
        endpoint=endpoint,
        auth_token=auth_token,
        config=config,
    )
    try:
        async with client:
            result = await client.list_tools()
            tools = getattr(result, "tools", None) or []
            return [_tool_from_sdk(t) for t in tools if getattr(t, "name", None)]
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001 — 映射为外部服务错误
        logger.warning("mcp list_tools failed: %s", exc)
        raise AppError(
            ErrorCode.EXTERNAL_SERVICE_ERROR,
            f"MCP 拉取工具失败：{exc}",
        ) from exc


async def test_connection(
    *,
    transport: str,
    endpoint: str,
    auth_token: str | None = None,
    config: dict[str, Any] | None = None,
) -> McpConnectResult:
    """连通性测试：成功则附带工具列表。"""
    started = time.perf_counter()
    try:
        tools = await list_tools(
            transport=transport,
            endpoint=endpoint,
            auth_token=auth_token,
            config=config,
        )
        latency = int((time.perf_counter() - started) * 1000)
        return McpConnectResult(ok=True, latency_ms=latency, tools=tools)
    except AppError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        return McpConnectResult(
            ok=False,
            latency_ms=latency,
            error_message=exc.message,
        )
    except Exception as exc:  # noqa: BLE001
        latency = int((time.perf_counter() - started) * 1000)
        return McpConnectResult(
            ok=False,
            latency_ms=latency,
            error_message=str(exc) or "MCP 连通性测试失败",
        )


def _result_to_text(result: Any) -> str:
    """把 CallToolResult 压成可供 LLM 阅读的文本。"""
    if result is None:
        return ""
    # SDK 常见：content 为 TextContent 列表
    parts: list[str] = []
    content = getattr(result, "content", None)
    if isinstance(content, list):
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
    structured = getattr(result, "structured_content", None)
    if structured is not None and not parts:
        try:
            import json

            return json.dumps(structured, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            return str(structured)
    if parts:
        return "\n".join(parts)
    is_error = bool(getattr(result, "isError", None) or getattr(result, "is_error", None))
    if is_error:
        return str(result)
    return str(result)


async def call_tool(
    *,
    transport: str,
    endpoint: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    auth_token: str | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    """调用远端工具；成功返回文本；失败抛 AppError（由上层决定是否吞掉）。"""
    client = _build_client(
        transport=transport,
        endpoint=endpoint,
        auth_token=auth_token,
        config=config,
    )
    try:
        async with client:
            result = await client.call_tool(tool_name, arguments or {})
            text = _result_to_text(result)
            is_error = bool(
                getattr(result, "isError", None) or getattr(result, "is_error", None)
            )
            if is_error:
                raise AppError(
                    ErrorCode.EXTERNAL_SERVICE_ERROR,
                    text or f"工具 {tool_name} 执行失败",
                )
            return text
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("mcp call_tool failed name=%s err=%s", tool_name, exc)
        raise AppError(
            ErrorCode.EXTERNAL_SERVICE_ERROR,
            f"MCP 工具调用失败：{exc}",
        ) from exc

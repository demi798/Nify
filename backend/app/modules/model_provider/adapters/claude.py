"""Anthropic Claude Messages API 适配器（原生协议）。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.model_provider.adapters.base import (
    ChatRequest,
    ChatResponse,
    StreamDelta,
)
from app.modules.model_provider.constants import ANTHROPIC_VERSION, DEFAULT_BASE_URLS
from app.modules.model_provider.internal.http_clients import (
    get_http_client,
    outbound_headers,
)

logger = logging.getLogger(__name__)


def _map_http_error(status_code: int, body: str) -> AppError:
    snippet = (body or "")[:200]
    if status_code in {401, 403}:
        return AppError(ErrorCode.LLM_AUTH, f"Claude 鉴权失败（HTTP {status_code}）")
    if status_code == 429:
        return AppError(ErrorCode.LLM_RATE_LIMIT, "Claude 触发限流")
    if status_code in {408, 502, 503, 504}:
        return AppError(ErrorCode.LLM_UNAVAILABLE, f"Claude 暂不可用（HTTP {status_code}）")
    if 400 <= status_code < 500:
        return AppError(ErrorCode.LLM_BAD_REQUEST, f"Claude 请求错误：{snippet or status_code}")
    return AppError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"Claude 服务错误：{snippet or status_code}")


def _split_system(request: ChatRequest) -> tuple[str | None, list[dict[str, Any]]]:
    """把 messages 中的 system 提到顶层。"""
    system_parts: list[str] = []
    messages: list[dict[str, Any]] = []
    for msg in request.messages:
        if msg.role == "system":
            system_parts.append(msg.content)
            continue
        role = msg.role if msg.role in {"user", "assistant"} else "user"
        messages.append({"role": role, "content": msg.content})
    system = "\n\n".join(system_parts) if system_parts else None
    return system, messages


class ClaudeAdapter:
    """Claude 原生 Messages + SSE。"""

    provider = "claude"

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        base = (request.base_url or DEFAULT_BASE_URLS["claude"]).rstrip("/")
        url = f"{base}/v1/messages"
        system, messages = _split_system(request)
        if not messages:
            raise AppError(ErrorCode.LLM_BAD_REQUEST, "Claude 请求缺少对话消息")

        version = str(
            (request.extra or {}).get("anthropic_version") or ANTHROPIC_VERSION
        )
        headers = outbound_headers(
            extra={
                "Content-Type": "application/json",
                "x-api-key": request.api_key,
                "anthropic-version": version,
            }
        )
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 1024,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        client = get_http_client(self.provider)
        try:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    raise _map_http_error(resp.status_code, body)
                async for line in resp.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    etype = event.get("type")
                    if etype == "content_block_delta":
                        delta = event.get("delta") or {}
                        text = delta.get("text") or ""
                        if text:
                            yield StreamDelta(text=text)
                    elif etype == "message_stop":
                        yield StreamDelta(text="", finish_reason="stop")
                        return
                    elif etype == "error":
                        err = event.get("error") or {}
                        raise AppError(
                            ErrorCode.LLM_UNAVAILABLE,
                            str(err.get("message") or "Claude 流式错误"),
                        )
        except AppError:
            raise
        except httpx.TimeoutException as exc:
            raise AppError(ErrorCode.LLM_TIMEOUT, "Claude 响应超时") from exc
        except httpx.HTTPError as exc:
            raise AppError(ErrorCode.LLM_UNAVAILABLE, "Claude 连接失败") from exc

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """非流式 Messages API。"""
        base = (request.base_url or DEFAULT_BASE_URLS["claude"]).rstrip("/")
        url = f"{base}/v1/messages"
        system, messages = _split_system(request)
        if not messages:
            raise AppError(ErrorCode.LLM_BAD_REQUEST, "Claude 请求缺少对话消息")

        version = str(
            (request.extra or {}).get("anthropic_version") or ANTHROPIC_VERSION
        )
        headers = outbound_headers(
            extra={
                "Content-Type": "application/json",
                "x-api-key": request.api_key,
                "anthropic-version": version,
            }
        )
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 1024,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        client = get_http_client(self.provider)
        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise _map_http_error(resp.status_code, resp.text)
            data = resp.json()
            parts: list[str] = []
            for block in data.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
            usage = data.get("usage")
            usage_dict = usage if isinstance(usage, dict) else None
            return ChatResponse(
                content="".join(parts),
                finish_reason=data.get("stop_reason"),
                usage=usage_dict,
                raw=data if isinstance(data, dict) else {},
            )
        except AppError:
            raise
        except httpx.TimeoutException as exc:
            raise AppError(ErrorCode.LLM_TIMEOUT, "Claude 响应超时") from exc
        except httpx.HTTPError as exc:
            raise AppError(ErrorCode.LLM_UNAVAILABLE, "Claude 连接失败") from exc
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise AppError(ErrorCode.EXTERNAL_SERVICE_ERROR, "Claude 响应解析失败") from exc


async def probe_claude(
    *,
    base_url: str,
    api_key: str,
    model: str,
    anthropic_version: str = ANTHROPIC_VERSION,
) -> None:
    """短请求探测 Claude 连通性。"""
    base = base_url.rstrip("/")
    url = f"{base}/v1/messages"
    headers = outbound_headers(
        extra={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": anthropic_version,
        }
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }
    client = get_http_client("claude")
    try:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise _map_http_error(resp.status_code, resp.text)
    except AppError:
        raise
    except httpx.TimeoutException as exc:
        raise AppError(ErrorCode.LLM_TIMEOUT, "Claude 响应超时") from exc
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.LLM_UNAVAILABLE, "Claude 连接失败") from exc

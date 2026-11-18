"""OpenAI Chat Completions 兼容协议（流式 + 健康探测）。

供 openai / gemini / ollama 等兼容端点复用；不重试、不熔断。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.model_provider.adapters.base import ChatMessage, ChatRequest, StreamDelta
from app.modules.model_provider.internal.http_clients import (
    get_http_client,
    outbound_headers,
)

logger = logging.getLogger(__name__)

_RETRYABLE_HTTP = frozenset({408, 429, 502, 503, 504})


def _normalize_base(base_url: str) -> str:
    return base_url.rstrip("/")


def _map_http_error(status_code: int, body: str) -> AppError:
    snippet = (body or "")[:200]
    if status_code in {401, 403}:
        return AppError(ErrorCode.LLM_AUTH, f"模型鉴权失败（HTTP {status_code}）")
    if status_code == 429:
        return AppError(ErrorCode.LLM_RATE_LIMIT, "模型调用触发限流")
    if status_code in _RETRYABLE_HTTP:
        return AppError(
            ErrorCode.LLM_UNAVAILABLE,
            f"模型服务暂不可用（HTTP {status_code}）",
        )
    if 400 <= status_code < 500:
        return AppError(ErrorCode.LLM_BAD_REQUEST, f"模型请求错误：{snippet or status_code}")
    return AppError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"模型服务错误：{snippet or status_code}")


def build_chat_payload(request: ChatRequest) -> dict[str, Any]:
    """构造 chat/completions 请求体。"""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": messages,
        "stream": True,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    return payload


def auth_headers_for_bearer(api_key: str) -> dict[str, str]:
    """Bearer 鉴权头；空 key 时不带头（Ollama）。"""
    if not api_key:
        return {"Content-Type": "application/json"}
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }


async def stream_chat_completions(
    *,
    provider: str,
    request: ChatRequest,
    base_url: str,
    headers: dict[str, str],
) -> AsyncIterator[StreamDelta]:
    """POST /chat/completions 并解析 SSE。"""
    url = f"{_normalize_base(base_url)}/chat/completions"
    client = get_http_client(provider)
    payload = build_chat_payload(request)
    try:
        async with client.stream(
            "POST",
            url,
            headers=outbound_headers(extra=headers),
            json=payload,
        ) as resp:
            if resp.status_code >= 400:
                body = (await resp.aread()).decode("utf-8", errors="replace")
                raise _map_http_error(resp.status_code, body)
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    yield StreamDelta(text="", finish_reason="stop")
                    return
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice0 = choices[0] or {}
                delta = choice0.get("delta") or {}
                text = delta.get("content") or ""
                finish = choice0.get("finish_reason")
                if text or finish:
                    yield StreamDelta(text=text or "", finish_reason=finish)
    except AppError:
        raise
    except httpx.TimeoutException as exc:
        raise AppError(ErrorCode.LLM_TIMEOUT, "模型响应超时") from exc
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.LLM_UNAVAILABLE, "模型连接失败") from exc


async def probe_chat_completions(
    *,
    provider: str,
    base_url: str,
    headers: dict[str, str],
    model: str,
) -> None:
    """非流式短请求探测连通性。"""
    url = f"{_normalize_base(base_url)}/chat/completions"
    client = get_http_client(provider)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }
    try:
        resp = await client.post(
            url,
            headers=outbound_headers(extra=headers),
            json=payload,
        )
        if resp.status_code >= 400:
            raise _map_http_error(resp.status_code, resp.text)
    except AppError:
        raise
    except httpx.TimeoutException as exc:
        raise AppError(ErrorCode.LLM_TIMEOUT, "模型响应超时") from exc
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.LLM_UNAVAILABLE, "模型连接失败") from exc


def messages_to_openai(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in messages]

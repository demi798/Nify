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
from app.modules.model_provider.adapters.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    StreamDelta,
)
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


def _message_to_openai(m: ChatMessage) -> dict[str, Any]:
    """单条消息转 OpenAI 形态（含 tool / tool_calls）。"""
    item: dict[str, Any] = {"role": m.role}
    # tool_calls 回合允许 content 为 null/空
    if m.tool_calls:
        item["tool_calls"] = m.tool_calls
        if m.content is not None and str(m.content) != "":
            item["content"] = m.content
        else:
            item["content"] = None
    else:
        item["content"] = m.content if m.content is not None else ""
    if m.tool_call_id:
        item["tool_call_id"] = m.tool_call_id
    if m.name:
        item["name"] = m.name
    return item


def build_chat_payload(request: ChatRequest, *, stream: bool = True) -> dict[str, Any]:
    """构造 chat/completions 请求体。"""
    messages = [_message_to_openai(m) for m in request.messages]
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": messages,
        "stream": stream,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    # 仅当显式传入 tools 时附带，避免空列表改变无工具路径行为
    if request.tools:
        payload["tools"] = request.tools
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
    payload = build_chat_payload(request, stream=True)
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


async def chat_completions(
    *,
    provider: str,
    request: ChatRequest,
    base_url: str,
    headers: dict[str, str],
) -> ChatResponse:
    """POST /chat/completions（非流式）并映射为 ChatResponse。"""
    url = f"{_normalize_base(base_url)}/chat/completions"
    client = get_http_client(provider)
    payload = build_chat_payload(request, stream=False)
    try:
        resp = await client.post(
            url,
            headers=outbound_headers(extra=headers),
            json=payload,
        )
        if resp.status_code >= 400:
            raise _map_http_error(resp.status_code, resp.text)
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise AppError(ErrorCode.LLM_UNAVAILABLE, "模型返回空 choices")
        choice0 = choices[0] or {}
        message = choice0.get("message") or {}
        content = message.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)
        raw_calls = message.get("tool_calls")
        tool_calls: list[dict[str, Any]] | None = None
        if isinstance(raw_calls, list) and raw_calls:
            tool_calls = [c for c in raw_calls if isinstance(c, dict)]
        usage = data.get("usage")
        usage_dict = usage if isinstance(usage, dict) else None
        finish = choice0.get("finish_reason")
        # 部分厂商只回 tool_calls 不标 finish_reason
        if tool_calls and not finish:
            finish = "tool_calls"
        return ChatResponse(
            content=content,
            finish_reason=finish,
            usage=usage_dict,
            tool_calls=tool_calls,
            raw=data if isinstance(data, dict) else {},
        )
    except AppError:
        raise
    except httpx.TimeoutException as exc:
        raise AppError(ErrorCode.LLM_TIMEOUT, "模型响应超时") from exc
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.LLM_UNAVAILABLE, "模型连接失败") from exc
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise AppError(ErrorCode.EXTERNAL_SERVICE_ERROR, "模型响应解析失败") from exc


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


def messages_to_openai(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [_message_to_openai(m) for m in messages]


async def create_embeddings(
    *,
    provider: str,
    base_url: str,
    headers: dict[str, str],
    model: str,
    inputs: list[str],
) -> list[list[float]]:
    """POST /embeddings；按 data[].index 排序后与输入对齐。"""
    if not inputs:
        return []
    url = f"{_normalize_base(base_url)}/embeddings"
    client = get_http_client(provider)
    payload = {"model": model, "input": inputs}
    try:
        resp = await client.post(
            url,
            headers=outbound_headers(extra=headers),
            json=payload,
        )
        if resp.status_code >= 400:
            raise _map_http_error(resp.status_code, resp.text)
        body = resp.json()
        rows = body.get("data")
        if not isinstance(rows, list) or not rows:
            raise AppError(ErrorCode.LLM_UNAVAILABLE, "Embedding 返回空 data")
        # 不能假设返回顺序与输入一致，必须按 index 排序
        sorted_rows = sorted(
            rows,
            key=lambda r: int((r or {}).get("index", 0)),
        )
        vectors: list[list[float]] = []
        for row in sorted_rows:
            emb = (row or {}).get("embedding")
            if not isinstance(emb, list) or not emb:
                raise AppError(ErrorCode.LLM_UNAVAILABLE, "Embedding 向量为空")
            vectors.append([float(x) for x in emb])
        if len(vectors) != len(inputs):
            raise AppError(
                ErrorCode.LLM_UNAVAILABLE,
                f"Embedding 条数不匹配：期望 {len(inputs)} 实际 {len(vectors)}",
            )
        return vectors
    except AppError:
        raise
    except httpx.TimeoutException as exc:
        raise AppError(ErrorCode.LLM_TIMEOUT, "Embedding 响应超时") from exc
    except httpx.HTTPError as exc:
        raise AppError(ErrorCode.LLM_UNAVAILABLE, "Embedding 连接失败") from exc
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise AppError(ErrorCode.EXTERNAL_SERVICE_ERROR, "Embedding 响应解析失败") from exc

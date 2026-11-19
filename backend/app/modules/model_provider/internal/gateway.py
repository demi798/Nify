"""LLMGateway：模型调用唯一出口（限流 / 超时 / 重试 / 熔断）。

conversation / agent / workflow / knowledge 禁止直连厂商 SDK。
持有 DB 事务或 asyncio.Lock 时禁止调用本 Gateway。
adapters 禁止重试/熔断，只做协议与 C* 错误映射。
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.model_provider.adapters.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMAdapter,
    StreamDelta,
)
from app.modules.model_provider.adapters.fake import FakeLLMAdapter
from app.modules.model_provider.internal import openai_compat
from app.modules.model_provider.internal.stream_guard import iter_with_stream_timeouts

logger = logging.getLogger(__name__)

# 未产出 delta 前可重试的错误码 / HTTP 语义
_RETRYABLE_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.LLM_TIMEOUT,
        ErrorCode.LLM_RATE_LIMIT,
        ErrorCode.LLM_UNAVAILABLE,
        ErrorCode.EXTERNAL_SERVICE_ERROR,
    }
)
_RETRYABLE_HTTP_STATUS: frozenset[int] = frozenset({408, 429, 502, 503, 504})


def is_retryable_http_status(status_code: int) -> bool:
    """供 adapter 映射前判断；Gateway 按 ErrorCode 决定是否重试。"""
    return status_code in _RETRYABLE_HTTP_STATUS


@dataclass
class _CircuitState:
    failures: int = 0
    opened_until: float = 0.0

    def is_open(self) -> bool:
        return time.monotonic() < self.opened_until

    def record_success(self) -> None:
        self.failures = 0
        self.opened_until = 0.0

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= settings.llm_circuit_fail_threshold:
            self.opened_until = time.monotonic() + settings.llm_circuit_open_sec
            logger.warning(
                "circuit open provider failures=%s cool_down=%ss",
                self.failures,
                settings.llm_circuit_open_sec,
            )


class LLMGateway:
    """三级 Semaphore + 分层超时 + 重试 + 熔断的统一网关。"""

    def __init__(self) -> None:
        global_n = min(settings.llm_global_concurrency, settings.llm_max_concurrency)
        self._global_sem = asyncio.Semaphore(global_n)
        self._provider_sems: dict[str, asyncio.Semaphore] = {}
        self._workspace_sems: dict[str, asyncio.Semaphore] = {}
        self._circuits: dict[str, _CircuitState] = {}
        self._adapters: dict[str, LLMAdapter] = {"fake": FakeLLMAdapter()}

    def register_adapter(self, adapter: LLMAdapter) -> None:
        """注册/覆盖厂商 adapter。"""
        self._adapters[adapter.provider] = adapter

    def _provider_sem(self, provider: str) -> asyncio.Semaphore:
        key = provider.lower()
        if key not in self._provider_sems:
            n = min(settings.llm_provider_concurrency, settings.llm_max_concurrency)
            self._provider_sems[key] = asyncio.Semaphore(n)
        return self._provider_sems[key]

    def _workspace_sem(self, workspace_id: str) -> asyncio.Semaphore:
        if workspace_id not in self._workspace_sems:
            n = min(settings.llm_workspace_concurrency, settings.llm_max_concurrency)
            self._workspace_sems[workspace_id] = asyncio.Semaphore(n)
        return self._workspace_sems[workspace_id]

    def _circuit(self, provider: str) -> _CircuitState:
        key = provider.lower()
        if key not in self._circuits:
            self._circuits[key] = _CircuitState()
        return self._circuits[key]

    def _get_adapter(self, provider: str) -> LLMAdapter:
        adapter = self._adapters.get(provider.lower())
        if adapter is None:
            raise AppError(
                ErrorCode.LLM_BAD_REQUEST,
                f"未注册的模型提供商: {provider}",
            )
        return adapter

    async def stream_chat(
        self,
        *,
        provider: str,
        workspace_id: str,
        model: str,
        messages: list[ChatMessage],
        api_key: str = "fake",
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamDelta]:
        """流式调用；已推送 delta 后禁止整段自动重试。"""
        provider_key = provider.lower()
        circuit = self._circuit(provider_key)
        if circuit.is_open():
            raise AppError(ErrorCode.LLM_UNAVAILABLE, "模型提供商熔断中，请稍后重试")

        adapter = self._get_adapter(provider_key)
        request = ChatRequest(
            model=model,
            messages=messages,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra or {},
        )

        global_sem = self._global_sem
        provider_sem = self._provider_sem(provider_key)
        workspace_sem = self._workspace_sem(workspace_id)

        await global_sem.acquire()
        await provider_sem.acquire()
        await workspace_sem.acquire()
        started = time.perf_counter()
        attempt = 0
        emitted = False
        try:
            while True:
                attempt += 1
                try:
                    upstream = adapter.stream_chat(request)
                    guarded = iter_with_stream_timeouts(upstream)
                    async for delta in guarded:
                        if delta.text:
                            emitted = True
                        # 禁止每个 token INFO
                        yield delta
                    circuit.record_success()
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    logger.info(
                        "llm stream ok provider=%s model=%s latency_ms=%s attempt=%s",
                        provider_key,
                        model,
                        latency_ms,
                        attempt,
                    )
                    return
                except asyncio.CancelledError:
                    # 不可吞掉；不记熔断失败（客户端主动取消）。
                    # 健康巡检标记 DOWN 不得触发此处取消；仅新请求入口拒绝。
                    logger.info(
                        "llm stream cancelled provider=%s model=%s attempt=%s emitted=%s",
                        provider_key,
                        model,
                        attempt,
                        emitted,
                    )
                    raise
                except AppError as exc:
                    retryable = exc.error_code in _RETRYABLE_CODES
                    # 已推 delta：禁止整段自动重试
                    if emitted or not retryable or attempt >= settings.llm_max_retries:
                        circuit.record_failure()
                        latency_ms = int((time.perf_counter() - started) * 1000)
                        logger.error(
                            "llm stream fail provider=%s model=%s latency_ms=%s "
                            "attempt=%s code=%s emitted=%s",
                            provider_key,
                            model,
                            latency_ms,
                            attempt,
                            exc.code,
                            emitted,
                        )
                        raise
                    logger.warning(
                        "llm stream retry provider=%s model=%s attempt=%s code=%s",
                        provider_key,
                        model,
                        attempt,
                        exc.code,
                    )
                    await self._backoff(attempt)
                except Exception as exc:
                    # adapter 未映射异常：未产出前可重试
                    if emitted or attempt >= settings.llm_max_retries:
                        circuit.record_failure()
                        raise AppError(
                            ErrorCode.LLM_UNAVAILABLE,
                            "模型调用失败",
                        ) from exc
                    logger.warning(
                        "llm stream retry provider=%s model=%s attempt=%s err=%s",
                        provider_key,
                        model,
                        attempt,
                        exc,
                    )
                    await self._backoff(attempt)
        finally:
            # SSE/外调路径必须释放限流名额
            workspace_sem.release()
            provider_sem.release()
            global_sem.release()

    async def chat(
        self,
        *,
        provider: str,
        workspace_id: str,
        model: str,
        messages: list[ChatMessage],
        api_key: str = "fake",
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """非流式调用；整段失败可按策略重试（无已推送 delta 限制）。"""
        provider_key = provider.lower()
        circuit = self._circuit(provider_key)
        if circuit.is_open():
            raise AppError(ErrorCode.LLM_UNAVAILABLE, "模型提供商熔断中，请稍后重试")

        adapter = self._get_adapter(provider_key)
        request = ChatRequest(
            model=model,
            messages=messages,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra or {},
        )

        global_sem = self._global_sem
        provider_sem = self._provider_sem(provider_key)
        workspace_sem = self._workspace_sem(workspace_id)

        await global_sem.acquire()
        await provider_sem.acquire()
        await workspace_sem.acquire()
        started = time.perf_counter()
        attempt = 0
        try:
            while True:
                attempt += 1
                try:
                    result = await adapter.chat(request)
                    circuit.record_success()
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    logger.info(
                        "llm chat ok provider=%s model=%s latency_ms=%s attempt=%s",
                        provider_key,
                        model,
                        latency_ms,
                        attempt,
                    )
                    return result
                except asyncio.CancelledError:
                    logger.info(
                        "llm chat cancelled provider=%s model=%s attempt=%s",
                        provider_key,
                        model,
                        attempt,
                    )
                    raise
                except AppError as exc:
                    retryable = exc.error_code in _RETRYABLE_CODES
                    if not retryable or attempt >= settings.llm_max_retries:
                        circuit.record_failure()
                        latency_ms = int((time.perf_counter() - started) * 1000)
                        logger.error(
                            "llm chat fail provider=%s model=%s latency_ms=%s "
                            "attempt=%s code=%s",
                            provider_key,
                            model,
                            latency_ms,
                            attempt,
                            exc.code,
                        )
                        raise
                    logger.warning(
                        "llm chat retry provider=%s model=%s attempt=%s code=%s",
                        provider_key,
                        model,
                        attempt,
                        exc.code,
                    )
                    await self._backoff(attempt)
                except Exception as exc:
                    if attempt >= settings.llm_max_retries:
                        circuit.record_failure()
                        raise AppError(
                            ErrorCode.LLM_UNAVAILABLE,
                            "模型调用失败",
                        ) from exc
                    logger.warning(
                        "llm chat retry provider=%s model=%s attempt=%s err=%s",
                        provider_key,
                        model,
                        attempt,
                        exc,
                    )
                    await self._backoff(attempt)
        finally:
            workspace_sem.release()
            provider_sem.release()
            global_sem.release()

    async def embed(
        self,
        *,
        provider: str,
        workspace_id: str,
        model: str,
        inputs: list[str],
        api_key: str = "fake",
        base_url: str | None = None,
    ) -> EmbeddingResponse:
        """批量 Embedding；限流/重试/熔断与 chat 一致。返回向量已按 index 对齐。"""
        provider_key = provider.lower()
        circuit = self._circuit(provider_key)
        if circuit.is_open():
            raise AppError(ErrorCode.LLM_UNAVAILABLE, "模型提供商熔断中，请稍后重试")

        request = EmbeddingRequest(
            model=model,
            inputs=list(inputs),
            api_key=api_key,
            base_url=base_url,
        )

        global_sem = self._global_sem
        provider_sem = self._provider_sem(provider_key)
        workspace_sem = self._workspace_sem(workspace_id)

        await global_sem.acquire()
        await provider_sem.acquire()
        await workspace_sem.acquire()
        started = time.perf_counter()
        attempt = 0
        try:
            while True:
                attempt += 1
                try:
                    vectors = await self._embed_once(provider_key, request)
                    circuit.record_success()
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    logger.info(
                        "llm embed ok provider=%s model=%s n=%s latency_ms=%s attempt=%s",
                        provider_key,
                        model,
                        len(vectors),
                        latency_ms,
                        attempt,
                    )
                    return EmbeddingResponse(vectors=vectors, model=model)
                except asyncio.CancelledError:
                    raise
                except AppError as exc:
                    retryable = exc.error_code in _RETRYABLE_CODES
                    if not retryable or attempt >= settings.llm_max_retries:
                        circuit.record_failure()
                        raise
                    logger.warning(
                        "llm embed retry provider=%s model=%s attempt=%s code=%s",
                        provider_key,
                        model,
                        attempt,
                        exc.code,
                    )
                    await self._backoff(attempt)
                except Exception as exc:
                    if attempt >= settings.llm_max_retries:
                        circuit.record_failure()
                        raise AppError(
                            ErrorCode.LLM_UNAVAILABLE,
                            "Embedding 调用失败",
                        ) from exc
                    await self._backoff(attempt)
        finally:
            workspace_sem.release()
            provider_sem.release()
            global_sem.release()

    async def _embed_once(
        self, provider_key: str, request: EmbeddingRequest
    ) -> list[list[float]]:
        """单次 Embedding；fake 本地生成，其余走 OpenAI 兼容 /embeddings。"""
        if provider_key == "fake":
            dim = settings.milvus_embedding_dim
            return [
                self._fake_vector(text, dim=dim) for text in request.inputs
            ]

        if provider_key not in {
            "openai",
            "openai_compatible",
            "gemini",
            "ollama",
        }:
            raise AppError(
                ErrorCode.LLM_BAD_REQUEST,
                f"提供商 {provider_key} 暂不支持 Embedding",
            )
        if not request.base_url:
            raise AppError(ErrorCode.BAD_REQUEST, "Embedding 需要 Base URL")
        headers = openai_compat.auth_headers_for_bearer(request.api_key)
        return await openai_compat.create_embeddings(
            provider=provider_key,
            base_url=request.base_url,
            headers=headers,
            model=request.model,
            inputs=request.inputs,
        )

    @staticmethod
    def _fake_vector(text: str, *, dim: int) -> list[float]:
        """确定性伪向量（本地联调）；已做 L2 归一化。"""
        seed = abs(hash(text)) % (2**31)
        rng = random.Random(seed)
        vec = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    @staticmethod
    async def _backoff(attempt: int) -> None:
        """指数退避 + full jitter。"""
        base = min(2**attempt, 8)
        delay = random.random() * base
        await asyncio.sleep(delay)


_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    """进程内 Gateway 单例。"""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway

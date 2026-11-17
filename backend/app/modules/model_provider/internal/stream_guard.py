"""流式读守卫：TTFT / idle / total 分层超时。

httpx 的 read timeout 无法区分「首包」与「帧间隔」，因此在 async 迭代层实现。
超时必须抛 AppError(LLM_TIMEOUT)，由 Gateway 决定是否可重试；调用方须 aclose 上游。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TypeVar

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError

T = TypeVar("T")


async def iter_with_stream_timeouts(
    source: AsyncIterator[T],
    *,
    ttft_sec: float | None = None,
    idle_sec: float | None = None,
    total_sec: float | None = None,
    has_emitted: bool = False,
) -> AsyncIterator[T]:
    """包装上游流：首包 TTFT、帧间 idle、整段 total。

    has_emitted=True 表示外层已向下游推过 delta（用于语义标记，超时仍抛 LLM_TIMEOUT，
    Gateway 根据 emitted 禁止整段重试）。
    """
    _ = has_emitted
    ttft = settings.llm_ttft_timeout_sec if ttft_sec is None else ttft_sec
    idle = settings.llm_idle_timeout_sec if idle_sec is None else idle_sec
    total = settings.llm_total_timeout_sec if total_sec is None else total_sec

    started = asyncio.get_running_loop().time()
    first = True
    aiter = source.__aiter__()
    try:
        while True:
            elapsed = asyncio.get_running_loop().time() - started
            remaining_total = total - elapsed
            if remaining_total <= 0:
                raise AppError(ErrorCode.LLM_TIMEOUT, "模型调用总超时")

            wait = ttft if first else idle
            wait = min(wait, remaining_total)
            try:
                item = await asyncio.wait_for(aiter.__anext__(), timeout=wait)
            except StopAsyncIteration:
                return
            except TimeoutError as exc:
                if first:
                    raise AppError(
                        ErrorCode.LLM_TIMEOUT,
                        "等待模型首包超时（TTFT）",
                    ) from exc
                raise AppError(
                    ErrorCode.LLM_TIMEOUT,
                    "模型流式空闲超时（idle）",
                ) from exc

            first = False
            yield item
    finally:
        # 尽量关闭上游 async generator，避免连接泄漏
        aclose = getattr(source, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except Exception:
                pass

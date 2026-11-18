"""Provider 健康巡检：每分钟对 enabled Provider 做连通性测试。

约定：只更新库内健康态（UP/DEGRADED/DOWN），**禁止**取消进行中的
LLMGateway 对话流。DOWN 仅由 ``get_runtime_credentials`` 拒绝新请求。
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.core.db import session_context
from app.modules.model_provider.service import ModelProviderService

logger = logging.getLogger(__name__)

_task: asyncio.Task[None] | None = None
_stop = asyncio.Event()


async def _loop() -> None:
    """定时循环；异常不中断后续周期。"""
    interval = max(15, int(settings.provider_health_interval_sec or 60))
    # 启动后稍等，避开冷启动尖峰
    try:
        await asyncio.wait_for(_stop.wait(), timeout=min(5, interval))
        return
    except TimeoutError:
        pass

    while not _stop.is_set():
        try:
            async with session_context() as session:
                svc = ModelProviderService(session)
                stats = await svc.run_enabled_health_checks()
            logger.info(
                "provider health sweep done total=%s ok=%s fail=%s skip=%s",
                stats.get("total"),
                stats.get("ok"),
                stats.get("fail"),
                stats.get("skip"),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("provider health sweep failed")

        try:
            await asyncio.wait_for(_stop.wait(), timeout=interval)
            break
        except TimeoutError:
            continue


def start_provider_health_scheduler() -> None:
    """在应用 lifespan 中启动后台任务。"""
    global _task
    if not settings.provider_health_enabled:
        logger.info("provider health scheduler disabled")
        return
    if _task is not None and not _task.done():
        return
    _stop.clear()
    _task = asyncio.create_task(_loop(), name="provider-health-scheduler")
    logger.info(
        "provider health scheduler started interval_sec=%s fail_threshold=%s",
        settings.provider_health_interval_sec,
        settings.provider_health_fail_threshold,
    )


async def stop_provider_health_scheduler() -> None:
    """停止后台巡检任务。"""
    global _task
    _stop.set()
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("provider health scheduler stop error")
    _task = None
    logger.info("provider health scheduler stopped")

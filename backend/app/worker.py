"""异步 worker 进程入口：消费 Redis 队列（解析 / embedding）。

与 api 同镜像、同代码库；禁止复制业务逻辑，后续在此分发到各模块 Service。
一期：空转消费并打日志，确认队列链路可用。
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.core.config import settings
from app.core.db import close_engine, configure_orm, init_engine
from app.core.logging import (
    set_request_id,
    set_user_id,
    set_workspace_id,
    setup_logging,
)
from app.core.queue import QUEUE_DOCUMENT_PARSE, dequeue_any
from app.core.redis_client import close_redis, init_redis

logger = logging.getLogger(__name__)

_stop = asyncio.Event()


def _install_signals() -> None:
    loop = asyncio.get_running_loop()

    def _handle(*_args: object) -> None:
        logger.info("worker received stop signal")
        _stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle)
        except NotImplementedError:
            # Windows 等环境可能不支持
            signal.signal(sig, lambda *_: _handle())


def _bind_job_context(job: dict) -> None:
    """继承入队时的 request_id / workspace_id，保证 worker 日志可追踪。"""
    rid = job.get("request_id")
    set_request_id(str(rid) if rid else None)
    uid = job.get("user_id")
    set_user_id(str(uid) if uid else None)
    ws = job.get("workspace_id")
    set_workspace_id(str(ws) if ws else None)


async def handle_job(queue_name: str, job: dict) -> None:
    """任务分发占位：一期仅记录，knowledge 落地后再接真实处理。"""
    _bind_job_context(job)
    logger.info(
        "worker idle consume queue=%s job_id=%s type=%s workspace_id=%s",
        queue_name,
        job.get("job_id"),
        job.get("type"),
        job.get("workspace_id"),
    )
    # TODO: document_parse → KnowledgeService.process_document(...)


async def run_worker() -> None:
    """主循环：BRPOP 多队列，空转消费。"""
    setup_logging()
    configure_orm()
    init_engine()
    await init_redis()
    _install_signals()

    queues = settings.worker_queue_list or [QUEUE_DOCUMENT_PARSE]
    logger.info("worker started queues=%s", queues)

    try:
        while not _stop.is_set():
            item = await dequeue_any(queues, timeout_sec=settings.worker_poll_timeout_sec)
            if item is None:
                continue
            queue_name, job = item
            try:
                await handle_job(queue_name, job)
            except Exception:
                logger.exception(
                    "worker job failed queue=%s job_id=%s",
                    queue_name,
                    job.get("job_id"),
                )
            finally:
                set_request_id(None)
                set_user_id(None)
                set_workspace_id(None)
    finally:
        await close_redis()
        await close_engine()
        logger.info("worker stopped")


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

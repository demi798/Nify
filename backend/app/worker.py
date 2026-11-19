"""异步 worker 进程入口：消费 Redis 队列（文档解析 / embedding）。

与 api 同镜像、同代码库；禁止复制业务逻辑，分发到各模块 Service。
单任务异常只记日志，不中断主循环（不影响线程池/事件循环中其它文档）。
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.core.config import settings
from app.core.db import close_engine, configure_orm, init_engine, session_context
from app.core.logging import (
    set_request_id,
    set_user_id,
    set_workspace_id,
    setup_logging,
)
from app.core.queue import QUEUE_DOCUMENT_PARSE, dequeue_any
from app.core.redis_client import close_redis, init_redis
from app.modules.knowledge.constants import JOB_TYPE_DOCUMENT_PARSE
from app.modules.model_provider.adapters import register_default_adapters

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
    """任务分发：document_parse → KnowledgeService.process_document。"""
    _bind_job_context(job)
    job_type = str(job.get("type") or "")
    logger.info(
        "worker consume queue=%s job_id=%s type=%s workspace_id=%s",
        queue_name,
        job.get("job_id"),
        job_type,
        job.get("workspace_id"),
    )

    if job_type != JOB_TYPE_DOCUMENT_PARSE:
        logger.warning("unknown job type=%s ignored", job_type)
        return

    payload = job.get("payload") or {}
    if not isinstance(payload, dict):
        logger.error("invalid payload job_id=%s", job.get("job_id"))
        return

    workspace_id = str(
        payload.get("workspace_id") or job.get("workspace_id") or ""
    )
    document_id = str(payload.get("document_id") or "")
    if not workspace_id or not document_id:
        logger.error(
            "document_parse missing ids job_id=%s payload=%s",
            job.get("job_id"),
            payload,
        )
        return

    from app.modules.knowledge.service import KnowledgeService
    from app.modules.model_provider.service import ModelProviderService

    async with session_context() as session:
        providers = ModelProviderService(session)
        svc = KnowledgeService(session, model_provider_service=providers)
        await svc.process_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )


async def run_worker() -> None:
    """主循环：BRPOP 多队列；单任务失败不退出进程。"""
    setup_logging()
    configure_orm()
    init_engine()
    await init_redis()
    register_default_adapters()
    _install_signals()

    queues = settings.worker_queue_list or [QUEUE_DOCUMENT_PARSE]
    logger.info("worker started queues=%s", queues)

    try:
        while not _stop.is_set():
            item = await dequeue_any(
                queues, timeout_sec=settings.worker_poll_timeout_sec
            )
            if item is None:
                continue
            queue_name, job = item
            try:
                await handle_job(queue_name, job)
            except Exception:
                # 管线内部已尽量标 failed；此处兜底保证主循环继续
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

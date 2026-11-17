"""Redis 队列约定：知识库文档解析等异步任务。

键名：{prefix}{queue_name}，例如 nify:queue:document_parse
payload JSON：job_id / type / workspace_id / payload / enqueued_at
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.logging import get_request_id, get_user_id
from app.core.db import new_uuid
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

# 一期预置队列名（不含前缀）
QUEUE_DOCUMENT_PARSE = "queue:document_parse"


def queue_key(queue_name: str) -> str:
    """拼完整 Redis list key。"""
    name = queue_name if queue_name.startswith("queue:") else f"queue:{queue_name}"
    return f"{settings.redis_key_prefix}{name}"


async def enqueue(
    queue_name: str,
    *,
    job_type: str,
    workspace_id: str,
    payload: dict[str, Any],
    request_id: str | None = None,
) -> str:
    """入队并返回 job_id；默认写入当前请求的 request_id，供 worker 对齐日志。"""
    redis = get_redis()
    job_id = new_uuid()
    rid = request_id or get_request_id()
    body = {
        "job_id": job_id,
        "type": job_type,
        "workspace_id": workspace_id,
        "request_id": rid,
        "user_id": get_user_id(),
        "payload": payload,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis.lpush(queue_key(queue_name), json.dumps(body, ensure_ascii=False))
    logger.info(
        "job enqueued queue=%s job_id=%s type=%s workspace_id=%s request_id=%s",
        queue_name,
        job_id,
        job_type,
        workspace_id,
        rid or "-",
    )
    return job_id


async def dequeue(
    queue_name: str,
    *,
    timeout_sec: int | None = None,
) -> dict[str, Any] | None:
    """阻塞弹出一条任务；超时返回 None。"""
    redis = get_redis()
    timeout = (
        timeout_sec if timeout_sec is not None else settings.worker_poll_timeout_sec
    )
    result = await redis.brpop(queue_key(queue_name), timeout=timeout)
    if result is None:
        return None
    _key, raw = result
    data = json.loads(raw)
    if not isinstance(data, dict):
        logger.warning("invalid job payload discarded: %s", raw)
        return None
    return data


async def dequeue_any(
    queue_names: list[str],
    *,
    timeout_sec: int | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """在多个队列上 BRPOP；返回 (queue_name, job)。"""
    redis = get_redis()
    timeout = (
        timeout_sec if timeout_sec is not None else settings.worker_poll_timeout_sec
    )
    keys = [queue_key(name) for name in queue_names]
    result = await redis.brpop(keys, timeout=timeout)
    if result is None:
        return None
    key, raw = result
    prefix = settings.redis_key_prefix
    queue_name = key[len(prefix) :] if key.startswith(prefix) else key
    data = json.loads(raw)
    if not isinstance(data, dict):
        logger.warning("invalid job payload discarded: %s", raw)
        return None
    return queue_name, data

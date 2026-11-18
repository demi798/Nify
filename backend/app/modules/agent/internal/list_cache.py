"""Agent 列表进程内短缓存。

写路径（创建/更新/删除）必须调用 ``invalidate_agent_list(workspace_id)``，
禁止只靠 TTL。多 worker 部署时应改为 Redis。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from app.modules.agent.constants import LIST_CACHE_PREFIX

logger = logging.getLogger(__name__)

# key -> (expire_at_monotonic, payload)
_store: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()
_TTL_SEC = 30.0


def _cache_key(workspace_id: str) -> str:
    return f"{LIST_CACHE_PREFIX}{workspace_id}"


def get_cached_agent_list(workspace_id: str) -> Any | None:
    """读取未过期的列表缓存；无则 None。"""
    if _TTL_SEC <= 0 or not workspace_id:
        return None
    now = time.monotonic()
    key = _cache_key(workspace_id)
    with _lock:
        item = _store.get(key)
        if item is None:
            return None
        expire_at, payload = item
        if now >= expire_at:
            _store.pop(key, None)
            return None
        return payload


def put_cached_agent_list(workspace_id: str, payload: Any) -> None:
    """写入短缓存。"""
    if _TTL_SEC <= 0 or not workspace_id:
        return
    with _lock:
        _store[_cache_key(workspace_id)] = (time.monotonic() + _TTL_SEC, payload)


def invalidate_agent_list(workspace_id: str) -> None:
    """写路径必须调用：清除该工作区 Agent 列表缓存。"""
    if not workspace_id:
        return
    key = _cache_key(workspace_id)
    with _lock:
        existed = _store.pop(key, None) is not None
    if existed:
        logger.info("agent list cache invalidated workspace_id=%s", workspace_id)
    else:
        logger.debug("agent list cache invalidate miss workspace_id=%s", workspace_id)

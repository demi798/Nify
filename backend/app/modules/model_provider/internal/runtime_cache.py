"""Provider 运行时缓存约定（凭证 / 路由决策）。

后续加 Redis 或本地短缓存时必须遵守：

1. **写路径失效**：改 api_key / base_url / auth / 禁用 / 删除后调用
   ``invalidate_provider_runtime(provider_id)``，禁止只靠 TTL。
2. **短 TTL 兜底**：即便漏删，缓存也不得超过数十秒（见 settings，默认 30s）。
3. **禁止跨请求长期持有明文 Key**：对话链路当次取用即丢。
4. **健康态 DOWN**：只拒绝「新请求」入口（见 ``get_runtime_credentials``）；
   **禁止**因巡检结果取消进行中的 LLMGateway stream。

当前实现：进程内可选短缓存；未命中则由调用方读库。多 worker 部署时应改为 Redis。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# provider_id -> (expire_at_monotonic, payload)
_store: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()


def _ttl_sec() -> float:
    raw = getattr(settings, "provider_runtime_cache_ttl_sec", 30)
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return 30.0


def get_cached_runtime(provider_id: str) -> dict[str, Any] | None:
    """读取未过期的运行时缓存；无则 None。"""
    if _ttl_sec() <= 0:
        return None
    now = time.monotonic()
    with _lock:
        item = _store.get(provider_id)
        if item is None:
            return None
        expire_at, payload = item
        if now >= expire_at:
            _store.pop(provider_id, None)
            return None
        return dict(payload)


def put_cached_runtime(provider_id: str, payload: dict[str, Any]) -> None:
    """写入短缓存（TTL<=0 时不缓存）。"""
    ttl = _ttl_sec()
    if ttl <= 0:
        return
    with _lock:
        _store[provider_id] = (time.monotonic() + ttl, dict(payload))


def invalidate_provider_runtime(provider_id: str) -> None:
    """写路径必须调用：清除该 Provider 的运行时缓存。"""
    if not provider_id:
        return
    with _lock:
        existed = _store.pop(provider_id, None) is not None
    if existed:
        logger.info("provider runtime cache invalidated id=%s", provider_id)
    else:
        logger.debug("provider runtime cache invalidate miss id=%s", provider_id)

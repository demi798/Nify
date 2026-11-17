"""按 provider 复用的 httpx.AsyncClient 单例。

禁止在业务路径每次请求新建 Client；出站自动透传 X-Request-Id。
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.core.logging import get_request_id

logger = logging.getLogger(__name__)

_clients: dict[str, httpx.AsyncClient] = {}


async def _inject_request_id(request: httpx.Request) -> None:
    """出站请求带上当前 request_id，便于跨服务对齐日志。"""
    rid = get_request_id()
    if not rid:
        return
    # 已有则不覆盖调用方显式设置
    if "X-Request-Id" not in request.headers and "x-request-id" not in request.headers:
        request.headers["X-Request-Id"] = rid


def outbound_headers(*, extra: dict[str, str] | None = None) -> dict[str, str]:
    """构造出站头；禁止把 api_key 放进 URL query，由调用方用 Authorization/自定义头。"""
    headers: dict[str, str] = {}
    rid = get_request_id()
    if rid:
        headers["X-Request-Id"] = rid
    if extra:
        headers.update(extra)
    return headers


def build_timeout(
    *,
    connect: float | None = None,
    read: float | None = None,
) -> httpx.Timeout:
    """httpx 层超时（connect/read）；TTFT/idle 由流式守卫在读迭代时控制。"""
    return httpx.Timeout(
        connect=connect if connect is not None else settings.llm_connect_timeout_sec,
        read=read if read is not None else settings.llm_total_timeout_sec,
        write=settings.llm_connect_timeout_sec,
        pool=settings.llm_connect_timeout_sec,
    )


def get_http_client(provider: str) -> httpx.AsyncClient:
    """获取（或创建）指定 provider 的 AsyncClient。"""
    key = provider.strip().lower()
    client = _clients.get(key)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=build_timeout(),
            follow_redirects=False,
            event_hooks={"request": [_inject_request_id]},
        )
        _clients[key] = client
        logger.info("httpx client created provider=%s", key)
    return client


async def close_all_http_clients() -> None:
    """应用关闭时释放全部 Client。"""
    for key, client in list(_clients.items()):
        if not client.is_closed:
            await client.aclose()
            logger.info("httpx client closed provider=%s", key)
    _clients.clear()

"""Redis 连接（全局客户端，供队列/限流使用）。"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

_redis: Any = None


async def init_redis() -> Any:
    """应用启动时初始化 Redis 连接。"""
    global _redis
    if _redis is None:
        from redis.asyncio import Redis  # 延迟导入，避免未安装时拖垮整个 core

        _redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    """应用关闭时释放 Redis。"""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis() -> Any:
    """获取已初始化的 Redis；未 init 则抛错。"""
    if _redis is None:
        raise RuntimeError("Redis 尚未初始化，请先在 lifespan 中调用 init_redis()")
    return _redis

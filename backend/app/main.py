"""应用启动类：只组装 FastAPI，不写业务逻辑。

按 CLAUDE.md：启动入口在 app/main.py，配置在 app/core/config.py，
禁止把启动类/全局配置放进 app/modules/。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

import uvicorn
from fastapi import FastAPI

from app.core.config import settings
from app.core.db import close_engine, configure_orm, init_engine
from app.core.exceptions import register_exception_handlers
from app.core.health import router as health_router
from app.core.logging import RequestContextMiddleware, setup_logging
from app.core.redis_client import close_redis, init_redis
from app.core.response import AppJSONResponse, configure_datetime_serialization
from app.core.storage import get_file_storage
from app.modules.identity.internal.seed import ensure_demo_account
from app.modules.model_provider.adapters import register_default_adapters
from app.modules.model_provider.internal.health_scheduler import (
    start_provider_health_scheduler,
    stop_provider_health_scheduler,
)
from app.modules.model_provider.internal.http_clients import close_all_http_clients

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """启动：日志、ORM、MySQL、Redis、Files、adapters、演示账号、健康巡检；关闭时释放。"""
    setup_logging()
    configure_datetime_serialization()
    configure_orm()
    init_engine()
    await init_redis()
    get_file_storage().ensure_root()
    register_default_adapters()
    try:
        await ensure_demo_account()
    except Exception:
        # 库未就绪时不阻断启动（如本地未配 MySQL）
        logger.exception("seed demo account failed")
    start_provider_health_scheduler()
    try:
        yield
    finally:
        await stop_provider_health_scheduler()
        await close_all_http_clients()
        await close_redis()
        await close_engine()


def create_app() -> FastAPI:
    """创建应用：中间件 + 全局异常处理 + 基础设施路由。"""
    configure_datetime_serialization()
    app = FastAPI(
        title="Nify",
        version="0.1.0",
        lifespan=lifespan,
        default_response_class=AppJSONResponse,
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    # 业务模块 router（按 CLAUDE.md 白名单逐步挂载）
    from app.modules.agent import router as agent_router
    from app.modules.conversation import router as conversation_router
    from app.modules.identity import router as identity_router
    from app.modules.knowledge import router as knowledge_router
    from app.modules.mcp import router as mcp_router
    from app.modules.model_provider import router as model_provider_router
    from app.modules.workflow import router as workflow_router

    app.include_router(identity_router)
    app.include_router(model_provider_router)
    app.include_router(agent_router)
    app.include_router(conversation_router)
    app.include_router(knowledge_router)
    app.include_router(workflow_router)
    app.include_router(mcp_router)
    return app


app = create_app()


def run() -> None:
    """本地启动入口，默认端口 8080。"""
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )


if __name__ == "__main__":
    run()

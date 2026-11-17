"""结构化日志、请求上下文（contextvars）与 request_id 中间件。

禁止业务代码使用 print；统一 logging.getLogger(__name__)。
contextvars 仅供日志/追踪跨层读取，禁止当业务状态机。
"""

from __future__ import annotations

import logging
import re
import sys
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings

# ---------- 请求上下文 ----------

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
workspace_id_var: ContextVar[str | None] = ContextVar("workspace_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def set_request_id(value: str | None) -> None:
    request_id_var.set(value)


def get_user_id() -> str | None:
    return user_id_var.get()


def set_user_id(value: str | None) -> None:
    user_id_var.set(value)


def get_workspace_id() -> str | None:
    return workspace_id_var.get()


def set_workspace_id(value: str | None) -> None:
    workspace_id_var.set(value)


# ---------- 日志 ----------

_SENSITIVE_RE = re.compile(
    r"(authorization|api[_-]?key|password|secret|token)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


class ContextFilter(logging.Filter):
    """把 request_id / user_id / workspace_id 注入 LogRecord。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"  # type: ignore[attr-defined]
        record.user_id = get_user_id() or "-"  # type: ignore[attr-defined]
        record.workspace_id = get_workspace_id() or "-"  # type: ignore[attr-defined]
        return True


class SensitiveFilter(logging.Filter):
    """粗粒度脱敏：避免密钥类字段整段进日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SENSITIVE_RE.sub(r"\1=***", record.msg)
        return True


def setup_logging() -> None:
    """进程启动时配置根日志（幂等覆盖 handlers）。"""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.addFilter(ContextFilter())
    handler.addFilter(SensitiveFilter())

    if settings.log_json:
        formatter: logging.Formatter = logging.Formatter(
            '{"level":"%(levelname)s","logger":"%(name)s",'
            '"request_id":"%(request_id)s","user_id":"%(user_id)s",'
            '"workspace_id":"%(workspace_id)s","message":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] "
            "rid=%(request_id)s uid=%(user_id)s ws=%(workspace_id)s %(message)s"
        )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # 降噪第三方库
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求生成/透传 X-Request-Id，并清理上下文。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        # 优先 X-Request-Id，其次兼容 X-Trace-Id
        incoming = (
            request.headers.get("X-Request-Id")
            or request.headers.get("x-request-id")
            or request.headers.get("X-Trace-Id")
            or request.headers.get("x-trace-id")
        )
        request_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        set_request_id(request_id)
        set_user_id(None)
        set_workspace_id(None)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            set_request_id(None)
            set_user_id(None)
            set_workspace_id(None)

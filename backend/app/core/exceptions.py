"""业务异常与全局异常处理器。

所有异常响应必须走 build_error_response + ErrorCode，禁止手写散落 JSON。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import ErrorCode
from app.core.response import ApiResult, AppJSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """业务/系统可预期错误；由全局 handler 转为 ApiResult 失败体。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        *,
        http_status: int | None = None,
    ) -> None:
        # 强制使用枚举，禁止魔法字符串错误码
        self.error_code = code
        self.code = code.value
        self.message = message or code.default_message
        self.http_status = http_status or code.http_status
        super().__init__(self.message)


def build_error_response(
    code: ErrorCode,
    message: str | None = None,
    *,
    http_status: int | None = None,
) -> AppJSONResponse:
    """统一异常响应出口：ApiResult.fail + ErrorCode。

    全局 handler 必须调用本方法，不得自行拼装 body。
    """
    status = http_status if http_status is not None else code.http_status
    body = ApiResult.fail(code, message)
    return AppJSONResponse(status_code=status, content=body.to_dict())


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> AppJSONResponse:
        """业务异常 → 对应 ErrorCode。"""
        return build_error_response(
            exc.error_code,
            exc.message,
            http_status=exc.http_status,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> AppJSONResponse:
        """参数校验错误 → VALIDATION_ERROR；message 带上首条可读原因。"""
        logger.warning("request validation failed: %s", exc.errors())
        message = _format_validation_message(exc)
        return build_error_response(ErrorCode.VALIDATION_ERROR, message)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> AppJSONResponse:
        """框架 HTTPException → 映射 ErrorCode。"""
        error_code = _map_status_to_error_code(exc.status_code)
        message = _safe_detail_message(exc.detail, error_code)
        return build_error_response(
            error_code,
            message,
            http_status=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        _request: Request,
        exc: Exception,
    ) -> AppJSONResponse:
        """未捕获异常 → 系统内部错误 INTERNAL_ERROR。"""
        logger.exception("unhandled error: %s", exc)
        return build_error_response(ErrorCode.INTERNAL_ERROR)


def _map_status_to_error_code(status_code: int) -> ErrorCode:
    """HTTP 状态码映射到稳定业务错误码枚举。"""
    mapping: dict[int, ErrorCode] = {
        400: ErrorCode.BAD_REQUEST,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.TOO_MANY_REQUESTS,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }
    return mapping.get(status_code, ErrorCode.INTERNAL_ERROR)


def _safe_detail_message(detail: Any, fallback: ErrorCode) -> str:
    """提取可展示短句；避免把 dict/堆栈塞进 message。"""
    if isinstance(detail, str) and detail.strip():
        return detail
    return fallback.default_message


def _format_validation_message(exc: RequestValidationError) -> str:
    """把首条 Pydantic 错误收成短句，例如 name: 不能为空。"""
    errors = exc.errors()
    if not errors:
        return ErrorCode.VALIDATION_ERROR.default_message
    first = errors[0]
    loc = first.get("loc") or ()
    # 跳过 body/query/path 前缀
    parts = [str(p) for p in loc if p not in {"body", "query", "path", "header"}]
    field = ".".join(parts) if parts else "参数"
    msg = str(first.get("msg") or "校验失败")
    # Pydantic v2 常带 Value error, 前缀
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :]
    return f"{field}: {msg}"

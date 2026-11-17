"""全局基础设施：响应信封、错误码、异常、分页、ORM 混入等。"""

from app.core.config import get_settings, settings
from app.core.db import (
    SOFT_DELETE_TABLES,
    Base,
    IdMixin,
    SoftDeleteBase,
    SoftDeleteMixin,
    TimestampMixin,
    assert_soft_delete_allowed,
    close_engine,
    configure_orm,
    get_session,
    init_engine,
    soft_delete,
    utc_now,
)
from app.core.redis_client import close_redis, get_redis, init_redis
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, build_error_response, register_exception_handlers
from app.core.pagination import (
    CursorPage,
    CursorParams,
    OffsetPageParams,
    build_cursor_page,
    clamp_limit,
    decode_cursor,
    encode_cursor,
    get_cursor_params,
    get_offset_page_params,
)
from app.core.response import ApiResult

__all__ = [
    "SOFT_DELETE_TABLES",
    "ApiResult",
    "AppError",
    "Base",
    "CursorPage",
    "CursorParams",
    "ErrorCode",
    "IdMixin",
    "OffsetPageParams",
    "SoftDeleteBase",
    "SoftDeleteMixin",
    "TimestampMixin",
    "assert_soft_delete_allowed",
    "build_cursor_page",
    "build_error_response",
    "clamp_limit",
    "close_engine",
    "close_redis",
    "configure_orm",
    "decode_cursor",
    "encode_cursor",
    "get_cursor_params",
    "get_offset_page_params",
    "get_redis",
    "get_session",
    "get_settings",
    "init_engine",
    "init_redis",
    "register_exception_handlers",
    "settings",
    "soft_delete",
    "utc_now",
]

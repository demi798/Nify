"""统一响应：ApiResult 信封、JSONResponse、全局时间序列化。

时间格式（对应 LocalDateTime / LocalDate）：
- datetime → yyyy-MM-dd'T'HH:mm:ss（UTC，无毫秒、无时区后缀）
- date     → yyyy-MM-dd
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_serializer

from app.core.error_codes import ErrorCode

T = TypeVar("T")

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"

_CONFIGURED = False


def format_datetime(value: datetime) -> str:
    """LocalDateTime → ISO-8601（秒级）。"""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.strftime(DATETIME_FORMAT)


def format_date(value: date) -> str:
    """LocalDate → yyyy-MM-dd；勿传入 datetime（应走 format_datetime）。"""
    return value.strftime(DATE_FORMAT)


def normalize_json_times(obj: Any) -> Any:
    """递归把 datetime/date 转为约定字符串（其它类型原样返回）。"""
    # datetime 是 date 子类，必须先判断 datetime
    if isinstance(obj, datetime):
        return format_datetime(obj)
    if isinstance(obj, date):
        return format_date(obj)
    if isinstance(obj, BaseModel):
        return normalize_json_times(obj.model_dump(mode="python"))
    if isinstance(obj, dict):
        return {k: normalize_json_times(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalize_json_times(v) for v in obj]
    return obj


def configure_datetime_serialization() -> None:
    """注册 FastAPI jsonable_encoder，保证响应路径统一时间格式（幂等）。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    from fastapi.encoders import ENCODERS_BY_TYPE

    ENCODERS_BY_TYPE[datetime] = format_datetime
    ENCODERS_BY_TYPE[date] = format_date
    _CONFIGURED = True


class AppJSONResponse(JSONResponse):
    """默认响应类；与 exception handler 共用同一时间格式。"""

    def render(self, content: Any) -> bytes:
        normalized = normalize_json_times(content)
        return json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


class ApiResult(BaseModel, Generic[T]):
    """所有非 SSE JSON 接口的统一返回体。"""

    code: str = Field(description='成功为 "0"，失败为稳定业务码')
    message: str = Field(description="给人看的短句，禁止写入堆栈")
    data: T | None = Field(default=None, description="成功为业务体；失败必须为 null")

    @classmethod
    def ok(cls, data: T, message: str = "ok") -> ApiResult[T]:
        """构造成功响应；仅用于 router 成功路径。"""
        return cls(code=ErrorCode.OK.value, message=message, data=data)

    @classmethod
    def fail(
        cls,
        code: ErrorCode | str,
        message: str | None = None,
    ) -> ApiResult[None]:
        """构造失败响应；仅供全局 exception handler / 框架层使用。"""
        if isinstance(code, ErrorCode):
            return cls(
                code=code.value,
                message=message or code.default_message,
                data=None,
            )
        return cls(code=code, message=message or "请求失败", data=None)

    @model_serializer(mode="wrap", when_used="json")
    def _serialize_times(self, handler: Callable[[Any], Any]) -> Any:
        """保证信封内 datetime/date 走全局格式。"""
        _ = handler
        return normalize_json_times(self.model_dump(mode="python"))

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 字典（失败时 data 恒为 null）。"""
        return normalize_json_times(self.model_dump(mode="python"))

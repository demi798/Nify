"""分页插件

- 大/中表：cursor 游标分页，禁止 OFFSET / COUNT(*)
- 小表：允许 page+limit，且 page*limit <= 1000
- 响应体放入 ApiResult.data，形状为 CursorPage（无 total/page/size）
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError

T = TypeVar("T")

_CURSOR_SEP = "|"


class CursorPage(BaseModel, Generic[T]):
    """游标分页业务体；禁止携带 total/page/size。"""

    items: list[T] = Field(default_factory=list, description="当前页数据")
    next_cursor: str | None = Field(
        default=None,
        description="下一页游标，格式 <iso>|<uuid>；无下一页时为 null",
    )


class CursorParams(BaseModel):
    """大/中表列表查询参数。"""

    cursor: str | None = Field(default=None, description="上一页返回的 next_cursor")
    limit: int = Field(default_factory=lambda: settings.page_default_limit)

    @field_validator("limit")
    @classmethod
    def _clamp_limit(cls, value: int) -> int:
        return clamp_limit(value)


class OffsetPageParams(BaseModel):
    """小表列表查询参数（page + limit）；禁止用于大表。"""

    page: int = Field(default=1, ge=1)
    limit: int = Field(default_factory=lambda: settings.page_default_limit)

    @field_validator("limit")
    @classmethod
    def _clamp_limit(cls, value: int) -> int:
        return clamp_limit(value)

    @model_validator(mode="after")
    def _check_window(self) -> OffsetPageParams:
        if self.page * self.limit > settings.page_max_offset_window:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"page*limit 不能超过 {settings.page_max_offset_window}，请改用游标分页",
            )
        return self

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def clamp_limit(limit: int) -> int:
    """将 limit 限制在 [1, page_max_limit]。"""
    if limit < 1:
        return settings.page_default_limit
    if limit > settings.page_max_limit:
        return settings.page_max_limit
    return limit


def encode_cursor(created_at: datetime, entity_id: str) -> str:
    """编码 keyset 游标：<iso>|<uuid>。"""
    ts = created_at.isoformat(timespec="milliseconds")
    if created_at.tzinfo is None and not ts.endswith("Z"):
        ts = f"{ts}Z"
    return f"{ts}{_CURSOR_SEP}{entity_id}"


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """解码游标；非法则抛参数错误。"""
    if not cursor or _CURSOR_SEP not in cursor:
        raise AppError(ErrorCode.BAD_REQUEST, "cursor 格式无效")
    ts_part, entity_id = cursor.rsplit(_CURSOR_SEP, 1)
    if not entity_id.strip():
        raise AppError(ErrorCode.BAD_REQUEST, "cursor 格式无效")
    try:
        normalized = ts_part.replace("Z", "+00:00") if ts_part.endswith("Z") else ts_part
        created_at = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AppError(ErrorCode.BAD_REQUEST, "cursor 时间格式无效") from exc
    if created_at.tzinfo is not None:
        created_at = created_at.replace(tzinfo=None)
    return created_at, entity_id


def build_cursor_page(
    rows: Sequence[T],
    limit: int,
    *,
    created_at_of: Callable[[T], datetime],
    id_of: Callable[[T], str],
) -> CursorPage[T]:
    """根据多取的一行判断是否有下一页，并生成 CursorPage。

    查询时应使用 ``limit + 1``；若多出一行则丢弃并设置 next_cursor。
    """
    limit = clamp_limit(limit)
    has_more = len(rows) > limit
    items = list(rows[:limit])
    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(created_at_of(last), id_of(last))
    return CursorPage[T](items=items, next_cursor=next_cursor)


def get_cursor_params(
    cursor: str | None = Query(default=None, description="游标"),
    limit: int = Query(default=settings.page_default_limit, ge=1),
) -> CursorParams:
    """FastAPI Depends 用：解析并钳制游标分页参数。"""
    return CursorParams(cursor=cursor, limit=clamp_limit(limit))


def get_offset_page_params(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=settings.page_default_limit, ge=1),
) -> OffsetPageParams:
    """FastAPI Depends 用：小表 page/limit（含窗口校验）。"""
    return OffsetPageParams(page=page, limit=clamp_limit(limit))

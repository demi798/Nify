"""业务 Pydantic Schema 基类与创建/更新约定。

- SchemaBase：Out / 读模型，统一时间序列化
- CreateSchema：创建入参，禁止多余字段，自动 strip
- UpdateSchema：更新入参，禁止多余字段；未传字段保持未设置（exclude_unset）
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_serializer, model_validator

from app.core.response import normalize_json_times


class SchemaBase(BaseModel):
    """模块 Out/ListOut 等请继承本类。"""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="ignore",
    )

    @model_serializer(mode="wrap", when_used="json")
    def _serialize_times(self, handler: Callable[[Any], Any]) -> Any:
        # handler(mode=json) 会带上微秒；改为 python 转储后再规范格式
        _ = handler
        return normalize_json_times(self.model_dump(mode="python"))


class CreateSchema(SchemaBase):
    """创建类入参基类：禁止未知字段，避免静默丢弃拼写错误。"""

    model_config = ConfigDict(
        from_attributes=False,
        str_strip_whitespace=True,
        extra="forbid",
        str_min_length=0,
    )


class UpdateSchema(SchemaBase):
    """更新类入参基类：禁止未知字段；至少提供一个可更新字段。"""

    model_config = ConfigDict(
        from_attributes=False,
        str_strip_whitespace=True,
        extra="forbid",
    )

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> Self:
        # 使用 model_fields_set：全部未传则拒绝空更新（走 ValidationError → A0002）
        if not self.model_fields_set:
            raise ValueError("更新请求至少包含一个字段")
        return self

    def changed_fields(self) -> dict[str, Any]:
        """供 service 做部分更新：仅含客户端显式传入的字段。"""
        return self.model_dump(exclude_unset=True)

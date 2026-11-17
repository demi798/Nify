"""跨模块可复用的入参字段类型（对齐 DDL / CLAUDE.md 类型字典）。

业务 schemas 用 Annotated 组合，避免每个 Create/Update 重复写约束。
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

# ---------- 基础正则 ----------
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def _require_non_empty(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("不能为空")
    return text


def _normalize_email(value: str) -> str:
    text = value.strip().lower()
    if not _EMAIL_RE.match(text):
        raise ValueError("邮箱格式无效")
    if len(text) > 320:
        raise ValueError("邮箱长度不能超过 320")
    return text


def _normalize_uuid(value: str) -> str:
    text = value.strip()
    if not _UUID_RE.match(text):
        raise ValueError("UUID 格式无效")
    return text


def _normalize_optional_blank(value: str | None) -> str | None:
    """空串视为 None，避免用 '' 表示未知。"""
    if value is None:
        return None
    text = value.strip()
    return text or None


def _optional_max_len(max_len: int) -> AfterValidator:
    def _check(value: str | None) -> str | None:
        normalized = _normalize_optional_blank(value)
        if normalized is not None and len(normalized) > max_len:
            raise ValueError(f"长度不能超过 {max_len}")
        return normalized

    return AfterValidator(_check)


# 非空短文本（去首尾空白）
NonEmptyStr = Annotated[
    str,
    AfterValidator(_require_non_empty),
    StringConstraints(min_length=1, max_length=512),
]

# 名称 VARCHAR(128)
NameStr = Annotated[
    str,
    AfterValidator(_require_non_empty),
    StringConstraints(min_length=1, max_length=128),
]

# 可选描述 / 副标题 VARCHAR(512)；空串 → None
DescriptionStr = Annotated[str | None, _optional_max_len(512)]

# 邮箱（入库前小写）
EmailStr = Annotated[str, AfterValidator(_normalize_email)]

# 资源 UUID（路径参数 / 外键列）
UuidStr = Annotated[str, AfterValidator(_normalize_uuid)]

# 密码：仅长度边界，复杂度留给 identity 业务规则
PasswordStr = Annotated[
    str,
    StringConstraints(min_length=8, max_length=72),
]

# 状态 / 短码 VARCHAR(32)
StatusStr = Annotated[
    str,
    AfterValidator(_require_non_empty),
    StringConstraints(min_length=1, max_length=32),
]

# 模型名 / provider 码等 VARCHAR(128)
CodeStr = Annotated[
    str,
    AfterValidator(_require_non_empty),
    StringConstraints(min_length=1, max_length=128),
]

# URL / storage_key / endpoint VARCHAR(512)
UrlStr = Annotated[
    str,
    AfterValidator(_require_non_empty),
    StringConstraints(min_length=1, max_length=512),
]

OptionalUrlStr = Annotated[str | None, _optional_max_len(512)]

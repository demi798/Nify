"""少量跨模块业务规则断言（service 层使用）。

schema 已保证类型/长度/格式；此处只处理：
- 工作区一致性
- 枚举白名单
- 非空业务前置条件
禁止在此写查库逻辑。
"""

from __future__ import annotations

import re
from collections.abc import Collection
from typing import Any

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def require_uuid(value: str, *, field: str = "id") -> str:
    """断言 UUID 格式。"""
    text = (value or "").strip()
    if not _UUID_RE.match(text):
        raise AppError(ErrorCode.BAD_REQUEST, f"{field} 格式无效")
    return text


def require_non_blank(value: str | None, *, field: str) -> str:
    """断言业务必填字符串非空。"""
    if value is None or not str(value).strip():
        raise AppError(ErrorCode.BAD_REQUEST, f"{field} 不能为空")
    return str(value).strip()


def require_workspace_match(
    entity_workspace_id: str,
    current_workspace_id: str,
    *,
    message: str = "资源不属于当前工作区",
) -> None:
    """写操作 / 点查：实体 workspace_id 必须与请求工作区一致。"""
    if entity_workspace_id != current_workspace_id:
        raise AppError(ErrorCode.FORBIDDEN, message)


def require_in(
    value: str,
    allowed: Collection[str],
    *,
    field: str,
) -> str:
    """状态机 / 枚举白名单。"""
    if value not in allowed:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"{field} 取值无效，允许: {', '.join(sorted(allowed))}",
        )
    return value


def require_true(condition: Any, *, code: ErrorCode, message: str) -> None:
    """通用业务前置；condition 为假则抛 AppError。"""
    if not condition:
        raise AppError(code, message)


def reject_if(condition: Any, *, code: ErrorCode, message: str) -> None:
    """条件成立则拒绝（如名称冲突）。"""
    if condition:
        raise AppError(code, message)

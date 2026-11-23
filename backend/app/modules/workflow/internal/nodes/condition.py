"""条件节点：极简表达式求值 → next_handle true/false。"""

from __future__ import annotations

from typing import Any

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.workflow.internal.engine.context import RunContext
from app.modules.workflow.internal.engine.graph import RuntimeNode
from app.modules.workflow.internal.nodes.base import NodeResult
from app.modules.workflow.node_config import ConditionNodeConfig


class ConditionNodeHandler:
    """一期仅支持路径真值 / not / == / != 极简模板，禁止脚本引擎。"""

    async def execute(
        self, *, node: RuntimeNode, ctx: RunContext
    ) -> NodeResult:
        cfg = node.config
        if not isinstance(cfg, ConditionNodeConfig):
            raise AppError(ErrorCode.BAD_REQUEST, "condition 节点配置无效")
        ok = _eval_expression(cfg.expression, ctx)
        return NodeResult(
            output={"result": ok},
            next_handle="true" if ok else "false",
        )


def _eval_expression(expression: str, ctx: RunContext) -> bool:
    """求值极简表达式。

    支持：
    - ``nodes.xxx.field`` / ``sys.query``：按 Python 真值
    - ``not <path>``
    - ``<path> == <literal>`` / ``!=``
      literal 可为空串、true/false、数字、或带引号字符串
    """
    expr = (expression or "").strip()
    if not expr:
        raise AppError(ErrorCode.BAD_REQUEST, "condition 表达式不能为空")

    lower = expr.lower()
    if lower.startswith("not "):
        path = expr[4:].strip()
        return not _truthy(ctx.pool.get(path))

    for op in ("==", "!="):
        if op in expr:
            left, right = expr.split(op, 1)
            left_path = left.strip()
            right_lit = right.strip()
            left_val = ctx.pool.get(left_path)
            right_val = _parse_literal(right_lit)
            eq = _equals(left_val, right_val)
            return eq if op == "==" else (not eq)

    # 纯路径真值
    if expr.startswith("sys.") or expr.startswith("nodes."):
        return _truthy(ctx.pool.get(expr))

    raise AppError(
        ErrorCode.BAD_REQUEST,
        f"不支持的 condition 表达式：{expression}",
    )


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return bool(value)


def _parse_literal(raw: str) -> Any:
    text = raw.strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    low = text.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "none", ""}:
        return None if low in {"null", "none"} else ""
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _equals(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return True
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return str(left) == str(right) if left is not None and right is not None else left == right

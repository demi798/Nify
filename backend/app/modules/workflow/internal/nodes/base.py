"""节点处理器协议与结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.modules.workflow.internal.engine.context import RunContext
from app.modules.workflow.internal.engine.graph import RuntimeNode


@dataclass(slots=True)
class NodeResult:
    """节点执行结果。"""

    output: dict[str, Any] = field(default_factory=dict)
    # condition 节点设置；其余为 None → 走全部默认出边
    next_handle: str | None = None


class NodeHandler(Protocol):
    """节点处理器协议。"""

    async def execute(
        self, *, node: RuntimeNode, ctx: RunContext
    ) -> NodeResult: ...

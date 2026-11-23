"""RuntimeGraph：从 DB 节点/边构建邻接表，并做 start/end/环路校验。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.workflow.constants import NODE_TYPE_END, NODE_TYPE_START
from app.modules.workflow.node_config import NodeConfigParser


@dataclass(slots=True)
class RuntimeNode:
    """运行时节点。"""

    key: str
    node_type: str
    name: str | None
    config: Any  # NodeConfig 判别联合实例


@dataclass(slots=True)
class RuntimeEdge:
    """运行时出边。"""

    target: str
    source_handle: str | None = None


@dataclass
class RuntimeGraph:
    """有向图：outs[source] = [(target, source_handle), ...]。"""

    nodes: dict[str, RuntimeNode]
    outs: dict[str, list[RuntimeEdge]] = field(default_factory=dict)
    start_key: str = ""
    end_keys: set[str] = field(default_factory=set)

    def successors(
        self, node_key: str, *, handle: str | None = None
    ) -> list[str]:
        """取后继；condition 传入 handle 时按 source_handle 过滤。"""
        edges = self.outs.get(node_key) or []
        if handle is None:
            # 普通节点：走全部出边（一期通常一条）
            return [e.target for e in edges]
        matched = [
            e.target
            for e in edges
            if (e.source_handle or "") == handle
        ]
        if matched:
            return matched
        # 兼容未标 handle 的默认边
        return [e.target for e in edges if not e.source_handle]


def build_runtime_graph(
    *,
    nodes: list[Any],
    edges: list[Any],
) -> RuntimeGraph:
    """从 ORM/Out 列表构建 RuntimeGraph。

    nodes 需有 node_key/node_type/config（或 key/type/config）。
    edges 需有 source_key/target_key/source_handle（或 source/target）。
    """
    runtime_nodes: dict[str, RuntimeNode] = {}
    for raw in nodes:
        key = _attr(raw, "node_key", "key")
        ntype = str(_attr(raw, "node_type", "type") or "").strip().lower()
        name = _attr(raw, "name", "name")
        config_raw = _attr(raw, "config", "config") or {}
        if isinstance(config_raw, dict):
            cfg = NodeConfigParser.parse(ntype, config_raw)
        else:
            cfg = config_raw
        runtime_nodes[str(key)] = RuntimeNode(
            key=str(key),
            node_type=ntype,
            name=name,
            config=cfg,
        )

    if not runtime_nodes:
        raise AppError(ErrorCode.BAD_REQUEST, "工作流没有任何节点")

    starts = [k for k, n in runtime_nodes.items() if n.node_type == NODE_TYPE_START]
    if len(starts) != 1:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            f"工作流必须有且仅有一个 start 节点（当前 {len(starts)} 个）",
        )
    ends = {k for k, n in runtime_nodes.items() if n.node_type == NODE_TYPE_END}
    if not ends:
        raise AppError(ErrorCode.BAD_REQUEST, "工作流缺少 end 节点")

    outs: dict[str, list[RuntimeEdge]] = {k: [] for k in runtime_nodes}
    for raw in edges:
        source = str(_attr(raw, "source_key", "source"))
        target = str(_attr(raw, "target_key", "target"))
        handle = _attr(raw, "source_handle", "source_handle")
        if source not in runtime_nodes or target not in runtime_nodes:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"边引用了不存在的节点：{source} → {target}",
            )
        outs[source].append(
            RuntimeEdge(
                target=target,
                source_handle=str(handle).strip() if handle else None,
            )
        )

    graph = RuntimeGraph(
        nodes=runtime_nodes,
        outs=outs,
        start_key=starts[0],
        end_keys=ends,
    )
    _assert_no_cycle(graph)
    return graph


def _assert_no_cycle(graph: RuntimeGraph) -> None:
    """DFS 检测有向环。"""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in graph.nodes}

    def dfs(u: str) -> None:
        color[u] = GRAY
        for e in graph.outs.get(u) or []:
            v = e.target
            if color[v] == GRAY:
                raise AppError(ErrorCode.BAD_REQUEST, "工作流图存在环路")
            if color[v] == WHITE:
                dfs(v)
        color[u] = BLACK

    dfs(graph.start_key)


def _attr(obj: Any, *names: str) -> Any:
    if isinstance(obj, dict):
        for n in names:
            if n in obj:
                return obj[n]
        return None
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return None

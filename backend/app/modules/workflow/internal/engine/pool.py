"""VariablePool：运行时变量池（sys.* / nodes.<key>.*）。"""

from __future__ import annotations

from typing import Any


class VariablePool:
    """进程内变量池；路径形如 ``sys.query`` / ``nodes.kb1.chunks``。"""

    def __init__(
        self,
        *,
        query: str,
        workspace_id: str,
        user_id: str,
        conversation_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._sys: dict[str, Any] = {
            "query": query,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "extra": dict(extra or {}),
        }
        self._nodes: dict[str, dict[str, Any]] = {}
        # 最近一次可用文本（llm / knowledge 写入，供 end 兜底）
        self.last_text: str | None = None

    def set_node_output(self, node_key: str, output: dict[str, Any]) -> None:
        """写入节点输出；若含 text 则更新 last_text。"""
        data = dict(output or {})
        self._nodes[node_key] = data
        text = data.get("text")
        if isinstance(text, str) and text.strip():
            self.last_text = text.strip()

    def get(self, path: str) -> Any:
        """按点分路径取值；不存在返回 None。

        支持：
        - ``sys.query`` / ``sys.workspace_id`` / …
        - ``nodes.<node_key>.<field>``（可多级，沿 dict 下钻）
        """
        raw = (path or "").strip()
        if not raw:
            return None
        parts = raw.split(".")
        if parts[0] == "sys":
            cur: Any = self._sys
            for p in parts[1:]:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(p)
            return cur
        if parts[0] == "nodes":
            if len(parts) < 2:
                return None
            cur = self._nodes.get(parts[1])
            for p in parts[2:]:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(p)
            return cur
        return None

    def get_sys(self, key: str) -> Any:
        return self._sys.get(key)

    @property
    def node_outputs(self) -> dict[str, dict[str, Any]]:
        return self._nodes

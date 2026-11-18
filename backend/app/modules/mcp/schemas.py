"""mcp 入参 / 出参（一期：列表选项）。"""

from __future__ import annotations

from app.core.schemas import SchemaBase


class McpServerOptionOut(SchemaBase):
    """工具多选选项。"""

    id: str
    name: str
    transport: str
    is_enabled: bool

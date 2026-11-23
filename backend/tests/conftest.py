"""pytest 公共 fixture（离线单测默认不连外部 LLM/MCP/Milvus）。"""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

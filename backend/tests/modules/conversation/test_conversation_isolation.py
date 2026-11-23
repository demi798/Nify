"""P0：会话 workspace 点查隔离。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.conversation.service import ConversationService

_WS_A = "019a0000-0000-7000-8000-0000000000a1"
_WS_B = "019a0000-0000-7000-8000-0000000000b1"
_CONV_ID = "019a0000-0000-7000-8000-0000000000c1"


def _svc(session: AsyncMock) -> ConversationService:
    return ConversationService(
        session,
        agent_service=MagicMock(),
        model_provider_service=MagicMock(),
        mcp_service=MagicMock(),
    )


@pytest.mark.asyncio
async def should_raise_not_found_when_conversation_belongs_to_other_workspace():
    # Given：点查在 WS-B 下找不到（实体只属于 WS-A）
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    svc = _svc(session)

    # When / Then
    with pytest.raises(AppError) as ei:
        await svc.get_conversation(
            workspace_id=_WS_B, conversation_id=_CONV_ID
        )
    assert ei.value.code == ErrorCode.NOT_FOUND.value
    assert "会话不存在" in ei.value.message


@pytest.mark.asyncio
async def should_return_conversation_when_workspace_matches():
    # Given：同工作区命中
    row = MagicMock()
    row.id = _CONV_ID
    row.workspace_id = _WS_A
    row.agent_id = "019a0000-0000-7000-8000-0000000000d1"
    row.title = "t"
    row.created_by = "019a0000-0000-7000-8000-0000000000e1"
    now = datetime.now(timezone.utc)
    row.created_at = now
    row.updated_at = now
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=row)
    svc = _svc(session)

    # When
    out = await svc.get_conversation(
        workspace_id=_WS_A, conversation_id=_CONV_ID
    )

    # Then
    assert out.id == _CONV_ID
    assert out.workspace_id == _WS_A

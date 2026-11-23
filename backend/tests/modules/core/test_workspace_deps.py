"""P0：工作区门禁 get_current_workspace。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.deps import CurrentUser, get_current_workspace
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError

# 合法 UUID（规则校验用）
_USER_ID = "019a0000-0000-7000-8000-0000000000a1"
_WS_ID = "019a0000-0000-7000-8000-0000000000b1"


@pytest.mark.asyncio
async def should_reject_when_workspace_header_missing():
    # Given：已登录用户，无 X-Workspace-Id
    user = CurrentUser(user_id=_USER_ID)
    session = AsyncMock()

    # When / Then
    with pytest.raises(AppError) as ei:
        await get_current_workspace(user=user, session=session, x_workspace_id=None)
    assert ei.value.code == ErrorCode.BAD_REQUEST.value
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def should_reject_when_caller_not_workspace_member():
    # Given：Header 合法，但成员表无记录
    user = CurrentUser(user_id=_USER_ID)
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)

    # When / Then
    with pytest.raises(AppError) as ei:
        await get_current_workspace(
            user=user, session=session, x_workspace_id=_WS_ID
        )
    assert ei.value.code == ErrorCode.FORBIDDEN.value
    assert "不是该工作区成员" in ei.value.message


@pytest.mark.asyncio
async def should_pass_when_caller_is_workspace_member():
    # Given：成员存在
    user = CurrentUser(user_id=_USER_ID)
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=1)

    # When
    ctx = await get_current_workspace(
        user=user, session=session, x_workspace_id=_WS_ID
    )

    # Then
    assert ctx.workspace_id == _WS_ID
    assert ctx.user_id == _USER_ID
    session.scalar.assert_awaited_once()

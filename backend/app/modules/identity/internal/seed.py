"""演示账号幂等种子：用户 + 默认工作区。"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.db import new_uuid, session_context
from app.core.security import hash_password
from app.modules.identity.models import User, Workspace, WorkspaceMember

logger = logging.getLogger(__name__)


async def ensure_demo_account() -> None:
    """若开启配置且账号不存在，则创建演示用户与工作区。"""
    if not settings.seed_demo_account:
        return

    email = settings.demo_email.strip().lower()
    async with session_context() as session:
        exists = await session.scalar(select(User.id).where(User.email == email))
        if exists is not None:
            logger.info("demo account already exists email=%s", email)
            return

        user_id = new_uuid()
        user = User(
            id=user_id,
            email=email,
            password_hash=hash_password(settings.demo_password),
            display_name=settings.demo_display_name,
            status="active",
        )
        session.add(user)
        await session.flush()

        ws_id = new_uuid()
        workspace = Workspace(
            id=ws_id,
            name=settings.demo_workspace_name,
            created_by=user_id,
        )
        session.add(workspace)
        session.add(
            WorkspaceMember(
                id=new_uuid(),
                workspace_id=ws_id,
                user_id=user_id,
                role="owner",
            )
        )
        await session.flush()
        logger.info(
            "demo account seeded email=%s workspace=%s",
            email,
            settings.demo_workspace_name,
        )

"""model_provider 依赖组装。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.model_provider.service import ModelProviderService


async def get_model_provider_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ModelProviderService:
    return ModelProviderService(session)

"""健康检查接口（基础设施，不属于业务 modules）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.response import ApiResult

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=ApiResult[dict[str, Any]])
async def health() -> ApiResult[dict[str, Any]]:
    """存活探针：进程已启动即可返回成功。"""
    return ApiResult.ok({"status": "up"})

"""conversation 路由：/api/v1/conversations。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from starlette.responses import StreamingResponse

from app.core.deps import CurrentWorkspace, get_current_workspace, get_path_uuid
from app.core.pagination import CursorPage, CursorParams, get_cursor_params
from app.core.response import ApiResult
from app.core.sse import sse_response
from app.modules.conversation.deps import get_conversation_service
from app.modules.conversation.schemas import (
    ChatIn,
    ChatOut,
    ConversationCreate,
    ConversationOut,
    MessageOut,
)
from app.modules.conversation.service import ConversationService

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
)


@router.get("", response_model=ApiResult[CursorPage[ConversationOut]])
async def list_conversations(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[ConversationOut]]:
    return ApiResult.ok(
        await svc.list_conversations_page(
            workspace_id=ws.workspace_id, params=params
        )
    )


@router.post(
    "",
    response_model=ApiResult[ConversationOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    body: ConversationCreate,
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ApiResult[ConversationOut]:
    return ApiResult.ok(
        await svc.create_conversation(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            body=body,
        )
    )


@router.get("/{id}", response_model=ApiResult[ConversationOut])
async def get_conversation(
    conversation_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ApiResult[ConversationOut]:
    return ApiResult.ok(
        await svc.get_conversation(
            workspace_id=ws.workspace_id, conversation_id=conversation_id
        )
    )


@router.delete("/{id}", response_model=ApiResult[None])
async def delete_conversation(
    conversation_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ApiResult[None]:
    await svc.delete_conversation(
        workspace_id=ws.workspace_id, conversation_id=conversation_id
    )
    return ApiResult.ok(None)


@router.get(
    "/{id}/messages",
    response_model=ApiResult[CursorPage[MessageOut]],
)
async def list_messages(
    conversation_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[MessageOut]]:
    return ApiResult.ok(
        await svc.list_messages_page(
            workspace_id=ws.workspace_id,
            conversation_id=conversation_id,
            params=params,
        )
    )


@router.post(
    "/{id}/chat",
    response_model=ApiResult[ChatOut],
)
async def chat(
    body: ChatIn,
    conversation_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ApiResult[ChatOut]:
    """非流式对话。"""
    return ApiResult.ok(
        await svc.chat(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            conversation_id=conversation_id,
            body=body,
        )
    )


@router.post("/{id}/chat/stream")
async def stream_chat(
    body: ChatIn,
    conversation_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[ConversationService, Depends(get_conversation_service)],
) -> StreamingResponse:
    """流式对话（SSE）；帧协议见 core.sse，不用 ApiResult 包每一帧。"""
    return sse_response(
        svc.stream_chat(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            conversation_id=conversation_id,
            body=body,
        )
    )

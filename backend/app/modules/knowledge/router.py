"""knowledge 路由：/api/v1/knowledge。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.core.deps import CurrentWorkspace, get_current_workspace, get_path_uuid
from app.core.pagination import CursorPage, CursorParams, get_cursor_params
from app.core.response import ApiResult
from app.modules.knowledge.deps import get_knowledge_service
from app.modules.knowledge.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseOptionOut,
    KnowledgeBaseOut,
    KnowledgeBaseReferencesOut,
    KnowledgeBaseUpdate,
    KnowledgeChunkOut,
    KnowledgeDocumentOut,
)
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["knowledge"],
)


# ---------- 知识库 ----------


@router.get(
    "/bases",
    response_model=ApiResult[CursorPage[KnowledgeBaseOut]],
)
async def list_knowledge_bases(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
    q: Annotated[
        str | None, Query(description="按名称模糊搜索")
    ] = None,
) -> ApiResult[CursorPage[KnowledgeBaseOut]]:
    """知识库列表（游标分页）。"""
    return ApiResult.ok(
        await svc.list_bases_page(
            workspace_id=ws.workspace_id, params=params, name_query=q
        )
    )


@router.get(
    "/bases/options",
    response_model=ApiResult[list[KnowledgeBaseOptionOut]],
)
async def list_knowledge_base_options(
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[list[KnowledgeBaseOptionOut]]:
    """知识库选项（Agent 绑定）。"""
    return ApiResult.ok(
        await svc.list_base_options(workspace_id=ws.workspace_id)
    )


@router.post(
    "/bases",
    response_model=ApiResult[KnowledgeBaseOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[KnowledgeBaseOut]:
    """创建知识库。"""
    return ApiResult.ok(
        await svc.create_base(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            body=body,
        )
    )


@router.get("/bases/{id}", response_model=ApiResult[KnowledgeBaseOut])
async def get_knowledge_base(
    knowledge_base_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[KnowledgeBaseOut]:
    """知识库详情。"""
    return ApiResult.ok(
        await svc.get_base(
            workspace_id=ws.workspace_id,
            knowledge_base_id=knowledge_base_id,
        )
    )


@router.put("/bases/{id}", response_model=ApiResult[KnowledgeBaseOut])
async def update_knowledge_base(
    body: KnowledgeBaseUpdate,
    knowledge_base_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[KnowledgeBaseOut]:
    """热更新知识库（启用中亦可改元数据 / 开关）。"""
    return ApiResult.ok(
        await svc.update_base(
            workspace_id=ws.workspace_id,
            knowledge_base_id=knowledge_base_id,
            body=body,
        )
    )


@router.get(
    "/bases/{id}/references",
    response_model=ApiResult[KnowledgeBaseReferencesOut],
)
async def get_knowledge_base_references(
    knowledge_base_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[KnowledgeBaseReferencesOut]:
    """查询引用该知识库的 Agent / 工作流（删除前提示用）。"""
    return ApiResult.ok(
        await svc.get_base_references(
            workspace_id=ws.workspace_id,
            knowledge_base_id=knowledge_base_id,
        )
    )


@router.delete("/bases/{id}", response_model=ApiResult[None])
async def delete_knowledge_base(
    knowledge_base_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[None]:
    """软删除知识库（须先取消关联并清空文档）。"""
    await svc.delete_base(
        workspace_id=ws.workspace_id,
        knowledge_base_id=knowledge_base_id,
    )
    return ApiResult.ok(None)


# ---------- 文档（挂在知识库下）----------


@router.get(
    "/bases/{id}/documents",
    response_model=ApiResult[CursorPage[KnowledgeDocumentOut]],
)
async def list_documents(
    knowledge_base_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[KnowledgeDocumentOut]]:
    """知识库下文档列表。"""
    return ApiResult.ok(
        await svc.list_documents_page(
            workspace_id=ws.workspace_id,
            knowledge_base_id=knowledge_base_id,
            params=params,
        )
    )


@router.post(
    "/bases/{id}/documents",
    response_model=ApiResult[KnowledgeDocumentOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    file: Annotated[UploadFile, File(description="知识库文档文件")],
    name: Annotated[str | None, Form()] = None,
) -> ApiResult[KnowledgeDocumentOut]:
    """上传文档：落盘 + pending + 入队解析。"""
    raw = await file.read()
    filename = (name or file.filename or "untitled").strip() or "untitled"
    content_type = (file.content_type or "application/octet-stream").strip()
    return ApiResult.ok(
        await svc.upload_document(
            workspace_id=ws.workspace_id,
            user_id=ws.user_id,
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            content_type=content_type,
            data=raw,
        )
    )


# ---------- 文档（按 document id）----------


@router.get(
    "/documents/{id}",
    response_model=ApiResult[KnowledgeDocumentOut],
)
async def get_document(
    document_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[KnowledgeDocumentOut]:
    """文档详情。"""
    return ApiResult.ok(
        await svc.get_document(
            workspace_id=ws.workspace_id, document_id=document_id
        )
    )


@router.delete("/documents/{id}", response_model=ApiResult[None])
async def delete_document(
    document_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[None]:
    """删除文档：清 chunks + Milvus 后软删。"""
    await svc.delete_document(
        workspace_id=ws.workspace_id, document_id=document_id
    )
    return ApiResult.ok(None)


@router.post(
    "/documents/{id}/retry",
    response_model=ApiResult[KnowledgeDocumentOut],
)
async def retry_document(
    document_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
) -> ApiResult[KnowledgeDocumentOut]:
    """失败文档重新入队解析。"""
    return ApiResult.ok(
        await svc.retry_document(
            workspace_id=ws.workspace_id, document_id=document_id
        )
    )


@router.get(
    "/documents/{id}/chunks",
    response_model=ApiResult[CursorPage[KnowledgeChunkOut]],
)
async def list_document_chunks(
    document_id: Annotated[str, Depends(get_path_uuid)],
    ws: Annotated[CurrentWorkspace, Depends(get_current_workspace)],
    svc: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    params: Annotated[CursorParams, Depends(get_cursor_params)],
) -> ApiResult[CursorPage[KnowledgeChunkOut]]:
    """文档分块列表（管理预览）。"""
    return ApiResult.ok(
        await svc.list_chunks_page(
            workspace_id=ws.workspace_id,
            document_id=document_id,
            params=params,
        )
    )

"""文档入库管线：串联五步，具体逻辑在独立私有方法。

Python/Nify 适配：
- 状态：processing → ready / failed（对应 Java DONE）
- 存储：MySQL knowledge_chunks（正文）+ Milvus（向量），非 pgvector
- Embedding：经 LLMGateway，凭证来自 ModelProviderService
- 重活（读盘/PDF）走 asyncio.to_thread，不阻塞事件循环
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import new_uuid
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.storage import LocalFileStorage, get_file_storage
from app.modules.knowledge.adapters.milvus import get_milvus_store
from app.modules.knowledge.constants import (
    EMBED_BATCH_SIZE,
    ERROR_MESSAGE_MAX_LENGTH,
    MILVUS_UPSERT_BATCH,
    STATUS_FAILED,
    STATUS_PROCESSING,
    STATUS_READY,
)
from app.modules.knowledge.internal.chunking import ChunkDTO, split_chunks
from app.modules.knowledge.internal.extract import extract_text
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument
from app.modules.model_provider.internal.gateway import get_llm_gateway
from app.modules.model_provider.service import ModelProviderService

logger = logging.getLogger(__name__)


class DocumentIngestPipeline:
    """单文档处理管线；一次实例绑定一个 session。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        model_provider: ModelProviderService,
        storage: LocalFileStorage | None = None,
    ) -> None:
        self._session = session
        self._providers = model_provider
        self._storage = storage or get_file_storage()

    async def run(self, *, workspace_id: str, document_id: str) -> None:
        """串联五步 + 状态管理；单文档失败不影响其它任务。"""
        doc = await self._load_document(workspace_id, document_id)
        try:
            await self._mark_processing(doc)

            text = await self._extract_text(doc)
            chunks = await self._split_chunks(text)
            if not chunks:
                raise AppError(ErrorCode.BAD_REQUEST, "分块结果为空")

            embedded = await self._embed_chunks(
                workspace_id=workspace_id, chunks=chunks
            )
            await self._save_chunks(doc, embedded)

            doc.status = STATUS_READY
            doc.error_message = None
            await self._session.flush()
            await self._session.commit()
            logger.info(
                "document ingest ok document_id=%s chunks=%s",
                doc.id,
                len(embedded),
            )
        except Exception as exc:  # noqa: BLE001 — 管线边界必须吞掉并标 failed
            logger.exception(
                "document ingest failed document_id=%s", document_id
            )
            await self._mark_failed(document_id, workspace_id, exc)

    # ---------- 1. 状态 ----------

    async def _mark_processing(self, doc: KnowledgeDocument) -> None:
        doc.status = STATUS_PROCESSING
        doc.error_message = None
        await self._session.flush()
        await self._session.commit()

    async def _mark_failed(
        self, document_id: str, workspace_id: str, exc: BaseException
    ) -> None:
        """独立事务写 failed，避免外层 rollback 冲掉状态。"""
        try:
            await self._session.rollback()
            doc = await self._session.get(KnowledgeDocument, document_id)
            if doc is None or doc.workspace_id != workspace_id:
                return
            if getattr(doc, "deleted_at", None) is not None:
                return
            message = ""
            if isinstance(exc, AppError):
                message = exc.message
            else:
                message = str(exc) or exc.__class__.__name__
            doc.status = STATUS_FAILED
            doc.error_message = self._clip_error(message)
            await self._session.commit()
        except Exception:  # noqa: BLE001
            logger.exception(
                "mark document failed also failed document_id=%s", document_id
            )
            try:
                await self._session.rollback()
            except Exception:  # noqa: BLE001
                pass

    # ---------- 2. 解析 ----------

    async def _extract_text(self, doc: KnowledgeDocument) -> str:
        path = self._storage.resolve_path(doc.storage_key)
        return await asyncio.to_thread(
            extract_text,
            file_path=path,
            content_type=doc.content_type,
            filename=doc.name,
        )

    # ---------- 3. 分块 ----------

    async def _split_chunks(self, text: str) -> list[ChunkDTO]:
        return await asyncio.to_thread(split_chunks, text)

    # ---------- 4. 向量化 ----------

    async def _embed_chunks(
        self, *, workspace_id: str, chunks: list[ChunkDTO]
    ) -> list[ChunkDTO]:
        """调用 Embedding API；每批最多 EMBED_BATCH_SIZE；按 index 对齐。"""
        runtime = await self._providers.get_embedding_runtime(
            workspace_id=workspace_id
        )
        gateway = get_llm_gateway()
        provider = str(runtime["provider_type"])
        model = str(runtime["model"])
        api_key = str(runtime.get("api_key") or "")
        base_url = runtime.get("base_url")
        if isinstance(base_url, str):
            base_url = base_url or None
        else:
            base_url = None

        dim = settings.milvus_embedding_dim
        for start in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[start : start + EMBED_BATCH_SIZE]
            inputs = [c.content for c in batch]
            # 调 LLM 前不持有长事务（已在 processing commit）
            result = await gateway.embed(
                provider=provider,
                workspace_id=workspace_id,
                model=model,
                inputs=inputs,
                api_key=api_key,
                base_url=base_url,
            )
            vectors = result.vectors
            if len(vectors) != len(batch):
                raise AppError(
                    ErrorCode.LLM_UNAVAILABLE,
                    "Embedding 返回条数与分块不一致",
                )
            for chunk, vec in zip(batch, vectors, strict=True):
                # 启用 Milvus 时必须与集合 dim 一致；未启用则仅校验非空
                if settings.milvus_enabled and len(vec) != dim:
                    raise AppError(
                        ErrorCode.BAD_REQUEST,
                        f"向量维度 {len(vec)} 与配置 dim={dim} 不一致，"
                        "请调整 NIFY_MILVUS_EMBEDDING_DIM 或 Embedding 模型",
                    )
                if not vec:
                    raise AppError(ErrorCode.LLM_UNAVAILABLE, "Embedding 向量为空")
                chunk.embedding = self._l2_normalize(vec)
        return chunks

    # ---------- 5. 存储 ----------

    async def _save_chunks(
        self, doc: KnowledgeDocument, chunks: list[ChunkDTO]
    ) -> None:
        """先清旧切片，再写 MySQL；启用 Milvus 时批量 upsert 向量。"""
        await self._session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.workspace_id == doc.workspace_id,
                KnowledgeChunk.document_id == doc.id,
            )
        )
        await self._session.flush()

        milvus_rows: list[dict] = []
        for chunk in chunks:
            if not chunk.embedding:
                raise AppError(ErrorCode.BAD_REQUEST, "分块缺少 embedding")
            milvus_pk = new_uuid()
            row = KnowledgeChunk(
                id=new_uuid(),
                workspace_id=doc.workspace_id,
                knowledge_base_id=doc.knowledge_base_id,
                document_id=doc.id,
                seq=int(chunk.chunk_index),
                milvus_pk=milvus_pk,
                content=chunk.content,
                token_count=int(chunk.token_count),
            )
            self._session.add(row)
            milvus_rows.append(
                {
                    "milvus_pk": milvus_pk,
                    "workspace_id": doc.workspace_id,
                    "knowledge_base_id": doc.knowledge_base_id,
                    "document_id": doc.id,
                    "embedding": chunk.embedding,
                }
            )
        await self._session.flush()

        if settings.milvus_enabled:
            store = get_milvus_store()
            await store.ensure_collection()
            # 重建：先按 document 删旧向量
            await store.delete_by_document(document_id=doc.id)
            for i in range(0, len(milvus_rows), MILVUS_UPSERT_BATCH):
                batch = milvus_rows[i : i + MILVUS_UPSERT_BATCH]
                await store.upsert_vectors(batch)
        else:
            logger.warning(
                "milvus disabled; chunks saved to MySQL only document_id=%s",
                doc.id,
            )

    # ---------- 工具 ----------

    async def _load_document(
        self, workspace_id: str, document_id: str
    ) -> KnowledgeDocument:
        doc = await self._session.get(KnowledgeDocument, document_id)
        if doc is None or doc.workspace_id != workspace_id:
            raise AppError(ErrorCode.NOT_FOUND, "文档不存在")
        if getattr(doc, "deleted_at", None) is not None:
            raise AppError(ErrorCode.NOT_FOUND, "文档已删除")
        return doc

    @staticmethod
    def _l2_normalize(vec: list[float]) -> list[float]:
        norm = sum(x * x for x in vec) ** 0.5
        if norm <= 0:
            return vec
        return [x / norm for x in vec]

    @staticmethod
    def _clip_error(message: str) -> str:
        text = (message or "").strip()
        if len(text) > ERROR_MESSAGE_MAX_LENGTH:
            return text[: ERROR_MESSAGE_MAX_LENGTH - 1] + "…"
        return text

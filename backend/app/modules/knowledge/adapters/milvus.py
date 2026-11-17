"""Milvus 薄封装：一期仅集合 nify_chunks。

业务通过本 adapter 访问向量库；禁止 router 直调。
pymilvus 为同步 SDK，经 asyncio.to_thread 调用。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VectorHit:
    """检索命中（不含正文；正文回表 MySQL）。"""

    milvus_pk: str
    score: float
    workspace_id: str
    knowledge_base_id: str
    document_id: str


class MilvusChunkStore:
    """知识库分块向量读写。"""

    def __init__(self) -> None:
        self._connected = False

    def _require_enabled(self) -> None:
        if not settings.milvus_enabled:
            raise AppError(
                ErrorCode.SERVICE_UNAVAILABLE,
                "Milvus 未启用（NIFY_MILVUS_ENABLED=false）",
            )

    async def connect(self) -> None:
        """懒连接；未启用则跳过。"""
        if not settings.milvus_enabled or self._connected:
            return

        def _connect() -> None:
            from pymilvus import connections

            connections.connect(
                alias="default",
                host=settings.milvus_host,
                port=str(settings.milvus_port),
            )

        await asyncio.to_thread(_connect)
        self._connected = True
        logger.info(
            "milvus connected host=%s port=%s",
            settings.milvus_host,
            settings.milvus_port,
        )

    async def ensure_collection(self) -> None:
        """确保集合与 HNSW 索引存在（薄封装，后续 knowledge 再加深）。"""
        self._require_enabled()
        await self.connect()

        def _ensure() -> None:
            from pymilvus import (
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                utility,
            )

            name = settings.milvus_collection
            if utility.has_collection(name):
                return
            fields = [
                FieldSchema(
                    name="milvus_pk",
                    dtype=DataType.VARCHAR,
                    is_primary=True,
                    max_length=36,
                ),
                FieldSchema(name="workspace_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(
                    name="knowledge_base_id",
                    dtype=DataType.VARCHAR,
                    max_length=36,
                ),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=settings.milvus_embedding_dim,
                ),
            ]
            schema = CollectionSchema(fields=fields, description="nify chunks")
            col = Collection(name=name, schema=schema)
            col.create_index(
                field_name="embedding",
                index_params={
                    "index_type": "HNSW",
                    "metric_type": "COSINE",
                    "params": {"M": 16, "efConstruction": 200},
                },
            )
            logger.info("milvus collection created name=%s", name)

        await asyncio.to_thread(_ensure)

    async def upsert_vectors(
        self,
        rows: list[dict[str, Any]],
    ) -> None:
        """批量 upsert；rows 含 milvus_pk/workspace_id/knowledge_base_id/document_id/embedding。"""
        self._require_enabled()
        await self.connect()
        if not rows:
            return

        def _upsert() -> None:
            from pymilvus import Collection

            col = Collection(settings.milvus_collection)
            col.insert(
                [
                    [r["milvus_pk"] for r in rows],
                    [r["workspace_id"] for r in rows],
                    [r["knowledge_base_id"] for r in rows],
                    [r["document_id"] for r in rows],
                    [r["embedding"] for r in rows],
                ]
            )
            col.flush()

        await asyncio.to_thread(_upsert)
        logger.info("milvus upsert count=%s", len(rows))

    async def search(
        self,
        *,
        workspace_id: str,
        embedding: list[float],
        knowledge_base_id: str | None = None,
        top_k: int = 5,
    ) -> list[VectorHit]:
        """向量检索；filter 必含 workspace_id。"""
        self._require_enabled()
        await self.connect()
        top_k = max(1, min(top_k, 20))

        def _search() -> list[VectorHit]:
            from pymilvus import Collection

            col = Collection(settings.milvus_collection)
            col.load()
            expr = f'workspace_id == "{workspace_id}"'
            if knowledge_base_id:
                expr += f' && knowledge_base_id == "{knowledge_base_id}"'
            results = col.search(
                data=[embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=top_k,
                expr=expr,
                output_fields=[
                    "milvus_pk",
                    "workspace_id",
                    "knowledge_base_id",
                    "document_id",
                ],
            )
            hits: list[VectorHit] = []
            for batch in results:
                for hit in batch:
                    entity = hit.entity
                    hits.append(
                        VectorHit(
                            milvus_pk=str(entity.get("milvus_pk")),
                            score=float(hit.distance),
                            workspace_id=str(entity.get("workspace_id")),
                            knowledge_base_id=str(entity.get("knowledge_base_id")),
                            document_id=str(entity.get("document_id")),
                        )
                    )
            return hits

        return await asyncio.to_thread(_search)

    async def delete_by_document(self, *, document_id: str) -> None:
        """按 document_id 删除向量（重建/删文档时调用）。"""
        self._require_enabled()
        await self.connect()

        def _delete() -> None:
            from pymilvus import Collection

            col = Collection(settings.milvus_collection)
            expr = f'document_id == "{document_id}"'
            col.delete(expr)

        await asyncio.to_thread(_delete)
        logger.info("milvus delete document_id=%s", document_id)


_store: MilvusChunkStore | None = None


def get_milvus_store() -> MilvusChunkStore:
    global _store
    if _store is None:
        _store = MilvusChunkStore()
    return _store

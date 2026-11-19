"""knowledge 用例：知识库 CRUD + 文档上传/列表/删除/重试 + 分块列表。

跨模块仅暴露本 Service；Milvus 经 adapters.milvus；文件经 core.storage；入队经 core.queue。
禁止在本 Service 内做大文件解析与批量 embedding（交给 worker）。
"""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath

from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import new_uuid, soft_delete
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.pagination import (
    CursorPage,
    CursorParams,
    build_cursor_page,
    decode_cursor,
)
from app.core.queue import QUEUE_DOCUMENT_PARSE, enqueue
from app.core.rules import reject_if, require_non_blank, require_uuid
from app.core.storage import LocalFileStorage, get_file_storage
from app.modules.knowledge.adapters.milvus import get_milvus_store
from app.modules.knowledge.constants import (
    ERROR_MESSAGE_MAX_LENGTH,
    JOB_TYPE_DOCUMENT_PARSE,
    MAX_UPLOAD_BYTES,
    RETRIABLE_STATUSES,
    STATUS_DELETE_FAILED,
    STATUS_PENDING,
)
from app.modules.knowledge.internal.pipeline import DocumentIngestPipeline
from app.modules.knowledge.models import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
)
from app.modules.knowledge.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseOptionOut,
    KnowledgeBaseOut,
    KnowledgeBaseRefItemOut,
    KnowledgeBaseReferencesOut,
    KnowledgeBaseUpdate,
    KnowledgeChunkOut,
    KnowledgeDocumentOut,
)
from app.modules.model_provider.service import ModelProviderService

logger = logging.getLogger(__name__)

_UNSAFE_NAME_RE = re.compile(r"[^\w.\-()\u4e00-\u9fff]+", re.UNICODE)


class KnowledgeService:
    """知识库与文档管理。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        model_provider_service: ModelProviderService | None = None,
        storage: LocalFileStorage | None = None,
    ) -> None:
        self._session = session
        self._providers = model_provider_service or ModelProviderService(session)
        self._storage = storage or get_file_storage()

    async def process_document(
        self, *, workspace_id: str, document_id: str
    ) -> None:
        """Worker 入口：跑完解析→分块→向量化→落库管线。"""
        pipeline = DocumentIngestPipeline(
            self._session,
            model_provider=self._providers,
            storage=self._storage,
        )
        await pipeline.run(workspace_id=workspace_id, document_id=document_id)

    # ---------- 知识库 ----------

    async def list_bases_page(
        self,
        *,
        workspace_id: str,
        params: CursorParams,
        name_query: str | None = None,
    ) -> CursorPage[KnowledgeBaseOut]:
        """工作区知识库游标分页；可选按名称模糊搜索。"""
        limit = params.limit
        stmt = select(KnowledgeBase).where(KnowledgeBase.workspace_id == workspace_id)
        q = (name_query or "").strip()
        if q:
            # 转义 LIKE 通配符，避免用户输入 %/_ 扩大匹配
            safe = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(KnowledgeBase.name.like(f"%{safe}%", escape="\\"))
        if params.cursor:
            cursor_at, cursor_id = decode_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    KnowledgeBase.created_at < cursor_at,
                    and_(
                        KnowledgeBase.created_at == cursor_at,
                        KnowledgeBase.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            KnowledgeBase.created_at.desc(), KnowledgeBase.id.desc()
        ).limit(limit + 1)
        rows = list((await self._session.scalars(stmt)).all())
        counts = await self._document_counts(
            workspace_id=workspace_id,
            knowledge_base_ids=[r.id for r in rows],
        )
        items = [
            self._to_base_out(r, document_count=counts.get(r.id, 0)) for r in rows
        ]
        return build_cursor_page(
            items,
            limit,
            created_at_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    async def list_base_options(
        self, *, workspace_id: str
    ) -> list[KnowledgeBaseOptionOut]:
        """启用中的知识库选项（供 Agent 绑定）。"""
        stmt = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.workspace_id == workspace_id,
                KnowledgeBase.is_enabled.is_(True),
            )
            .order_by(KnowledgeBase.created_at.asc(), KnowledgeBase.id.asc())
        )
        rows = list((await self._session.scalars(stmt)).all())
        return [KnowledgeBaseOptionOut(id=r.id, name=r.name) for r in rows]

    async def resolve_base_briefs(
        self, *, workspace_id: str, knowledge_base_ids: list[str]
    ) -> list[KnowledgeBaseOptionOut]:
        """按 id 批量解析知识库简述（含停用；已软删的标「已删除」），供 Agent 列表展示。"""
        if not knowledge_base_ids:
            return []
        # 去重保序
        ordered: list[str] = []
        seen: set[str] = set()
        for raw in knowledge_base_ids:
            kid = (raw or "").strip()
            if not kid or kid in seen:
                continue
            seen.add(kid)
            ordered.append(kid)

        stmt = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.workspace_id == workspace_id,
                KnowledgeBase.id.in_(ordered),
            )
            .execution_options(include_deleted=True)
        )
        rows = list((await self._session.scalars(stmt)).all())
        by_id = {r.id: r for r in rows}
        out: list[KnowledgeBaseOptionOut] = []
        for kid in ordered:
            row = by_id.get(kid)
            if row is None:
                out.append(KnowledgeBaseOptionOut(id=kid, name="未知知识库"))
                continue
            name = row.name
            if row.deleted_at is not None:
                name = f"{name}（已删除）"
            elif not bool(row.is_enabled):
                name = f"{name}（已停用）"
            out.append(KnowledgeBaseOptionOut(id=kid, name=name))
        return out

    async def get_base(
        self, *, workspace_id: str, knowledge_base_id: str
    ) -> KnowledgeBaseOut:
        row = await self._get_base_entity(workspace_id, knowledge_base_id)
        counts = await self._document_counts(
            workspace_id=workspace_id, knowledge_base_ids=[row.id]
        )
        return self._to_base_out(row, document_count=counts.get(row.id, 0))

    async def create_base(
        self,
        *,
        workspace_id: str,
        user_id: str,
        body: KnowledgeBaseCreate,
    ) -> KnowledgeBaseOut:
        name = require_non_blank(body.name, field="name")
        await self._assert_base_name_unique(workspace_id=workspace_id, name=name)
        row = KnowledgeBase(
            id=new_uuid(),
            workspace_id=workspace_id,
            name=name,
            description=body.description,
            is_enabled=bool(body.is_enabled),
            created_by=user_id,
            deleted_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_base_out(row, document_count=0)

    async def update_base(
        self,
        *,
        workspace_id: str,
        knowledge_base_id: str,
        body: KnowledgeBaseUpdate,
    ) -> KnowledgeBaseOut:
        """热更新：启用中的知识库可直接改元数据 / 开关，无需先停用或解绑。"""
        row = await self._get_base_entity(workspace_id, knowledge_base_id)
        changes = body.changed_fields()
        if "name" in changes and changes["name"] is not None:
            name = require_non_blank(changes["name"], field="name")
            if name != row.name:
                await self._assert_base_name_unique(
                    workspace_id=workspace_id,
                    name=name,
                    exclude_id=row.id,
                )
            row.name = name
        if "description" in changes:
            row.description = changes["description"]
        if "is_enabled" in changes and changes["is_enabled"] is not None:
            row.is_enabled = bool(changes["is_enabled"])
        await self._session.flush()
        counts = await self._document_counts(
            workspace_id=workspace_id, knowledge_base_ids=[row.id]
        )
        return self._to_base_out(row, document_count=counts.get(row.id, 0))

    async def get_base_references(
        self, *, workspace_id: str, knowledge_base_id: str
    ) -> KnowledgeBaseReferencesOut:
        """查询仍引用该知识库的 Agent / 工作流（跨表只读，不 import 他模块 Model）。"""
        row = await self._get_base_entity(workspace_id, knowledge_base_id)
        agents, workflows = await self._load_base_references(
            workspace_id=workspace_id, knowledge_base_id=row.id
        )
        return KnowledgeBaseReferencesOut(
            knowledge_base_id=row.id,
            agents=agents,
            workflows=workflows,
        )

    async def delete_base(
        self, *, workspace_id: str, knowledge_base_id: str
    ) -> None:
        """软删知识库；须先解除 Agent/工作流关联，并清空文档。"""
        row = await self._get_base_entity(workspace_id, knowledge_base_id)
        agents, workflows = await self._load_base_references(
            workspace_id=workspace_id, knowledge_base_id=row.id
        )
        if agents or workflows:
            parts: list[str] = []
            if agents:
                names = "、".join(a.name for a in agents[:5])
                more = f" 等 {len(agents)} 个" if len(agents) > 5 else ""
                parts.append(f"Agent：{names}{more}")
            if workflows:
                names = "、".join(w.name for w in workflows[:5])
                more = f" 等 {len(workflows)} 个" if len(workflows) > 5 else ""
                parts.append(f"工作流：{names}{more}")
            raise AppError(
                ErrorCode.CONFLICT,
                "请先取消知识库关联后再删除（"
                + "；".join(parts)
                + "）",
            )

        count = await self._session.scalar(
            select(func.count())
            .select_from(KnowledgeDocument)
            .where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.knowledge_base_id == row.id,
            )
        )
        reject_if(
            int(count or 0) > 0,
            code=ErrorCode.CONFLICT,
            message="请先删除知识库下的文档",
        )
        soft_delete(row)
        await self._session.flush()

    # ---------- 文档 ----------

    async def list_documents_page(
        self,
        *,
        workspace_id: str,
        knowledge_base_id: str,
        params: CursorParams,
    ) -> CursorPage[KnowledgeDocumentOut]:
        await self._get_base_entity(workspace_id, knowledge_base_id)
        limit = params.limit
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.workspace_id == workspace_id,
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
        )
        if params.cursor:
            cursor_at, cursor_id = decode_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    KnowledgeDocument.created_at < cursor_at,
                    and_(
                        KnowledgeDocument.created_at == cursor_at,
                        KnowledgeDocument.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            KnowledgeDocument.created_at.desc(),
            KnowledgeDocument.id.desc(),
        ).limit(limit + 1)
        rows = list((await self._session.scalars(stmt)).all())
        counts = await self._chunk_counts(
            workspace_id=workspace_id,
            document_ids=[r.id for r in rows],
        )
        items = [
            self._to_document_out(r, chunk_count=counts.get(r.id, 0))
            for r in rows
        ]
        return build_cursor_page(
            items,
            limit,
            created_at_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    async def get_document(
        self, *, workspace_id: str, document_id: str
    ) -> KnowledgeDocumentOut:
        row = await self._get_document_entity(workspace_id, document_id)
        counts = await self._chunk_counts(
            workspace_id=workspace_id, document_ids=[row.id]
        )
        return self._to_document_out(row, chunk_count=counts.get(row.id, 0))

    async def upload_document(
        self,
        *,
        workspace_id: str,
        user_id: str,
        knowledge_base_id: str,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> KnowledgeDocumentOut:
        """热更新上传：启用中可直接上传；已绑定 Agent 无需解绑，向量就绪后检索即生效。"""
        base = await self._get_base_entity(workspace_id, knowledge_base_id)
        reject_if(
            not bool(base.is_enabled),
            code=ErrorCode.CONFLICT,
            message="知识库已停用，无法上传文档",
        )
        reject_if(
            not data,
            code=ErrorCode.BAD_REQUEST,
            message="上传文件不能为空",
        )
        reject_if(
            len(data) > MAX_UPLOAD_BYTES,
            code=ErrorCode.BAD_REQUEST,
            message=f"文件大小不能超过 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
        )

        display_name = self._normalize_display_name(filename)
        safe_name = self._safe_filename(filename)
        mime = (content_type or "application/octet-stream").strip()[:128] or (
            "application/octet-stream"
        )

        document_id = new_uuid()
        storage_key = (
            f"{workspace_id}/{base.id}/{document_id}/{safe_name}"
        )
        await self._storage.save_bytes(storage_key, data)

        doc = KnowledgeDocument(
            id=document_id,
            workspace_id=workspace_id,
            knowledge_base_id=base.id,
            name=display_name,
            storage_key=storage_key,
            byte_size=len(data),
            content_type=mime,
            status=STATUS_PENDING,
            error_message=None,
            created_by=user_id,
            deleted_at=None,
        )
        self._session.add(doc)
        await self._session.flush()
        # 入队前先提交，避免 worker 抢跑读不到文档
        await self._session.commit()
        await self._enqueue_parse(doc)
        return self._to_document_out(doc, chunk_count=0)

    async def retry_document(
        self, *, workspace_id: str, document_id: str
    ) -> KnowledgeDocumentOut:
        """失败/待处理文档重新入队；清理旧分块与向量后回到 pending。"""
        doc = await self._get_document_entity(workspace_id, document_id)
        reject_if(
            doc.status not in RETRIABLE_STATUSES,
            code=ErrorCode.BAD_REQUEST,
            message=f"当前状态 {doc.status} 不可重试",
        )
        await self._purge_chunks_and_vectors(doc)
        doc.status = STATUS_PENDING
        doc.error_message = None
        await self._session.flush()
        await self._session.commit()
        await self._enqueue_parse(doc)
        return self._to_document_out(doc, chunk_count=0)

    async def delete_document(
        self, *, workspace_id: str, document_id: str
    ) -> None:
        """先硬删 MySQL chunks，再删 Milvus；成功后软删文档。失败标 delete_failed。"""
        doc = await self._get_document_entity(workspace_id, document_id)
        try:
            await self._purge_chunks_and_vectors(doc)
        except Exception as exc:
            logger.exception(
                "delete document vectors failed document_id=%s", doc.id
            )
            doc.status = STATUS_DELETE_FAILED
            doc.error_message = self._clip_error(str(exc) or "删除向量失败")
            # 先落库失败态，再抛错（避免外层 rollback 冲掉标记）
            await self._session.commit()
            raise AppError(
                ErrorCode.SERVICE_UNAVAILABLE,
                "文档向量清理失败，已标记 delete_failed",
            ) from exc

        soft_delete(doc)
        await self._session.flush()
        # 原文件尽力删除，失败不影响软删结果
        try:
            await self._storage.delete(doc.storage_key)
        except Exception:
            logger.exception(
                "delete storage file failed key=%s", doc.storage_key
            )

    # ---------- 分块（管理预览）----------

    async def list_chunks_page(
        self,
        *,
        workspace_id: str,
        document_id: str,
        params: CursorParams,
    ) -> CursorPage[KnowledgeChunkOut]:
        """按文档列分块；keyset 为 seq|id 升序，禁止 OFFSET。"""
        doc = await self._get_document_entity(workspace_id, document_id)
        limit = params.limit
        stmt = select(KnowledgeChunk).where(
            KnowledgeChunk.workspace_id == workspace_id,
            KnowledgeChunk.document_id == doc.id,
        )
        if params.cursor:
            seq, cursor_id = self._decode_seq_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    KnowledgeChunk.seq > seq,
                    and_(
                        KnowledgeChunk.seq == seq,
                        KnowledgeChunk.id > cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            KnowledgeChunk.seq.asc(),
            KnowledgeChunk.id.asc(),
        ).limit(limit + 1)
        rows = list((await self._session.scalars(stmt)).all())
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = [self._to_chunk_out(r) for r in page_rows]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = self._encode_seq_cursor(int(last.seq), last.id)
        return CursorPage(items=items, next_cursor=next_cursor)

    # ---------- 跨模块辅助 ----------

    async def assert_bases_in_workspace(
        self, *, workspace_id: str, knowledge_base_ids: list[str]
    ) -> list[str]:
        """校验知识库均属于当前工作区、未删且启用；返回规范化 id 列表。"""
        if not knowledge_base_ids:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in knowledge_base_ids:
            kid = require_uuid(raw, field="knowledge_base_ids")
            if kid in seen:
                continue
            seen.add(kid)
            normalized.append(kid)
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.id.in_(normalized),
        )
        rows = list((await self._session.scalars(stmt)).all())
        found = {r.id: r for r in rows}
        missing = [x for x in normalized if x not in found]
        if missing:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"知识库不存在或不属于当前工作区: {missing[0]}",
            )
        disabled = [x for x in normalized if not bool(found[x].is_enabled)]
        if disabled:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"知识库已停用，无法绑定: {disabled[0]}",
            )
        return normalized

    # ---------- 内部 ----------

    async def _get_base_entity(
        self, workspace_id: str, knowledge_base_id: str
    ) -> KnowledgeBase:
        knowledge_base_id = require_uuid(knowledge_base_id, field="id")
        row = await self._session.get(KnowledgeBase, knowledge_base_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "知识库不存在")
        if row.workspace_id != workspace_id:
            raise AppError(ErrorCode.FORBIDDEN, "资源不属于当前工作区")
        return row

    async def _get_document_entity(
        self, workspace_id: str, document_id: str
    ) -> KnowledgeDocument:
        document_id = require_uuid(document_id, field="id")
        row = await self._session.get(KnowledgeDocument, document_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "文档不存在")
        if row.workspace_id != workspace_id:
            raise AppError(ErrorCode.FORBIDDEN, "资源不属于当前工作区")
        return row

    async def _assert_base_name_unique(
        self,
        *,
        workspace_id: str,
        name: str,
        exclude_id: str | None = None,
    ) -> None:
        stmt = select(KnowledgeBase.id).where(
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.name == name,
        )
        if exclude_id:
            stmt = stmt.where(KnowledgeBase.id != exclude_id)
        exists = await self._session.scalar(stmt)
        reject_if(
            exists is not None,
            code=ErrorCode.CONFLICT,
            message="知识库名称已存在",
        )

    async def _enqueue_parse(self, doc: KnowledgeDocument) -> None:
        """入队 document_parse；payload 可直接作为 worker IngestJob。"""
        await enqueue(
            QUEUE_DOCUMENT_PARSE,
            job_type=JOB_TYPE_DOCUMENT_PARSE,
            workspace_id=doc.workspace_id,
            payload={
                "document_id": doc.id,
                "workspace_id": doc.workspace_id,
                "knowledge_base_id": doc.knowledge_base_id,
                "storage_key": doc.storage_key,
                "content_type": doc.content_type,
                "name": doc.name,
            },
        )

    async def _purge_chunks_and_vectors(self, doc: KnowledgeDocument) -> None:
        """先删 MySQL chunks，再按 document_id 删 Milvus（未启用则跳过向量）。"""
        await self._session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.workspace_id == doc.workspace_id,
                KnowledgeChunk.document_id == doc.id,
            )
        )
        await self._session.flush()

        if not settings.milvus_enabled:
            return
        store = get_milvus_store()
        await store.connect()
        await store.delete_by_document(document_id=doc.id)

    @staticmethod
    def _normalize_display_name(filename: str) -> str:
        raw = (filename or "").strip() or "untitled"
        # 去掉路径成分
        name = PurePosixPath(raw.replace("\\", "/")).name or "untitled"
        if len(name) > 128:
            name = name[:128]
        return name

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = KnowledgeService._normalize_display_name(filename)
        cleaned = _UNSAFE_NAME_RE.sub("_", name).strip("._") or "file"
        if len(cleaned) > 180:
            cleaned = cleaned[:180]
        return cleaned

    @staticmethod
    def _clip_error(message: str) -> str:
        text = (message or "").strip()
        if len(text) > ERROR_MESSAGE_MAX_LENGTH:
            return text[: ERROR_MESSAGE_MAX_LENGTH - 1] + "…"
        return text

    @staticmethod
    def _encode_seq_cursor(seq: int, entity_id: str) -> str:
        return f"{seq}|{entity_id}"

    @staticmethod
    def _decode_seq_cursor(cursor: str) -> tuple[int, str]:
        if not cursor or "|" not in cursor:
            raise AppError(ErrorCode.BAD_REQUEST, "cursor 格式无效")
        seq_part, entity_id = cursor.rsplit("|", 1)
        if not entity_id.strip():
            raise AppError(ErrorCode.BAD_REQUEST, "cursor 格式无效")
        try:
            seq = int(seq_part)
        except ValueError as exc:
            raise AppError(ErrorCode.BAD_REQUEST, "cursor 格式无效") from exc
        return seq, entity_id.strip()

    async def _load_base_references(
        self, *, workspace_id: str, knowledge_base_id: str
    ) -> tuple[list[KnowledgeBaseRefItemOut], list[KnowledgeBaseRefItemOut]]:
        """只读查询 Agent / 工作流对该库的引用（原生 SQL，避免跨模块 import Model）。"""
        agent_rows = (
            await self._session.execute(
                text(
                    """
SELECT `id`, `name`
FROM `agent_agents`
WHERE `workspace_id` = :ws
  AND `deleted_at` IS NULL
  AND JSON_CONTAINS(
        COALESCE(`knowledge_base_ids`, JSON_ARRAY()),
        JSON_QUOTE(:kb),
        '$'
      )
ORDER BY `created_at` ASC, `id` ASC
LIMIT 50
"""
                ),
                {"ws": workspace_id, "kb": knowledge_base_id},
            )
        ).all()
        agents = [
            KnowledgeBaseRefItemOut(id=str(r.id), name=str(r.name), kind="agent")
            for r in agent_rows
        ]

        workflow_rows = (
            await self._session.execute(
                text(
                    """
SELECT w.`id` AS id, w.`name` AS name
FROM `workflow_workflows` w
WHERE w.`workspace_id` = :ws
  AND w.`deleted_at` IS NULL
  AND EXISTS (
    SELECT 1
    FROM `workflow_nodes` n
    WHERE n.`workflow_id` = w.`id`
      AND n.`workspace_id` = w.`workspace_id`
      AND n.`deleted_at` IS NULL
      AND n.`node_type` = 'knowledge'
      AND JSON_CONTAINS(
            COALESCE(JSON_EXTRACT(n.`config`, '$.knowledge_base_ids'), JSON_ARRAY()),
            JSON_QUOTE(:kb),
            '$'
          )
  )
ORDER BY w.`created_at` ASC, w.`id` ASC
LIMIT 50
"""
                ),
                {"ws": workspace_id, "kb": knowledge_base_id},
            )
        ).all()
        workflows = [
            KnowledgeBaseRefItemOut(
                id=str(r.id), name=str(r.name), kind="workflow"
            )
            for r in workflow_rows
        ]
        return agents, workflows

    async def _document_counts(
        self, *, workspace_id: str, knowledge_base_ids: list[str]
    ) -> dict[str, int]:
        """批量统计各知识库未删文档数。"""
        if not knowledge_base_ids:
            return {}
        stmt = (
            select(
                KnowledgeDocument.knowledge_base_id,
                func.count().label("cnt"),
            )
            .where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.knowledge_base_id.in_(knowledge_base_ids),
            )
            .group_by(KnowledgeDocument.knowledge_base_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(kb_id): int(cnt) for kb_id, cnt in rows}

    async def _chunk_counts(
        self, *, workspace_id: str, document_ids: list[str]
    ) -> dict[str, int]:
        """批量统计各文档分块数。"""
        if not document_ids:
            return {}
        stmt = (
            select(
                KnowledgeChunk.document_id,
                func.count().label("cnt"),
            )
            .where(
                KnowledgeChunk.workspace_id == workspace_id,
                KnowledgeChunk.document_id.in_(document_ids),
            )
            .group_by(KnowledgeChunk.document_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(doc_id): int(cnt) for doc_id, cnt in rows}

    @staticmethod
    def _to_base_out(
        row: KnowledgeBase, *, document_count: int = 0
    ) -> KnowledgeBaseOut:
        return KnowledgeBaseOut(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            description=row.description,
            is_enabled=bool(row.is_enabled),
            created_by=row.created_by,
            document_count=int(document_count or 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_document_out(
        row: KnowledgeDocument, *, chunk_count: int = 0
    ) -> KnowledgeDocumentOut:
        return KnowledgeDocumentOut(
            id=row.id,
            workspace_id=row.workspace_id,
            knowledge_base_id=row.knowledge_base_id,
            name=row.name,
            storage_key=row.storage_key,
            byte_size=int(row.byte_size or 0),
            content_type=row.content_type,
            status=row.status,
            error_message=row.error_message,
            chunk_count=int(chunk_count or 0),
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_chunk_out(row: KnowledgeChunk) -> KnowledgeChunkOut:
        return KnowledgeChunkOut(
            id=row.id,
            workspace_id=row.workspace_id,
            knowledge_base_id=row.knowledge_base_id,
            document_id=row.document_id,
            seq=int(row.seq),
            milvus_pk=row.milvus_pk,
            content=row.content or "",
            token_count=int(row.token_count or 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

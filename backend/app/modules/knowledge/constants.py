"""knowledge 模块常量。"""

from __future__ import annotations

# 文档处理状态（与 CLAUDE.md §4.9 对齐）
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"
STATUS_DELETE_FAILED = "delete_failed"

DOCUMENT_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_PENDING,
        STATUS_PROCESSING,
        STATUS_READY,
        STATUS_FAILED,
        STATUS_DELETE_FAILED,
    }
)

# 可重新入队解析的状态
RETRIABLE_STATUSES: frozenset[str] = frozenset(
    {STATUS_FAILED, STATUS_PENDING}
)

# 上传限制（与前端文档管理页一致）
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB
NAME_MAX_LENGTH = 128
DESCRIPTION_MAX_LENGTH = 512
ERROR_MESSAGE_MAX_LENGTH = 512

# 允许的 MIME（一期）；未知类型仍可存，由 worker 决定能否解析
ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    }
)

# 队列任务类型
JOB_TYPE_DOCUMENT_PARSE = "document_parse"

# 分块 / Embedding 批大小（对齐产品约定）
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64
EMBED_BATCH_SIZE = 100
MILVUS_UPSERT_BATCH = 128

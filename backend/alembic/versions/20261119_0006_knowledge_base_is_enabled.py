"""知识库增加 is_enabled 用户开关。

Revision ID: 20261119_0006
Revises: 20261119_0005
Create Date: 2026-11-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20261119_0006"
down_revision: str | None = "20261119_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # 幂等：列已存在则跳过
    row = conn.execute(
        text(
            """
SELECT COUNT(*) AS cnt
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'knowledge_bases'
  AND COLUMN_NAME = 'is_enabled'
"""
        )
    ).scalar()
    if int(row or 0) == 0:
        conn.execute(
            text(
                """
ALTER TABLE `knowledge_bases`
  ADD COLUMN `is_enabled` TINYINT(1) NOT NULL DEFAULT 1
    COMMENT '用户开关：停用后不可被 Agent 绑定 / 不可上传'
  AFTER `description`
"""
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        text(
            """
SELECT COUNT(*) AS cnt
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'knowledge_bases'
  AND COLUMN_NAME = 'is_enabled'
"""
        )
    ).scalar()
    if int(row or 0) > 0:
        conn.execute(text("ALTER TABLE `knowledge_bases` DROP COLUMN `is_enabled`"))

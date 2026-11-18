"""Provider 健康态：UP/DOWN、fail_count、last_success_at。

Revision ID: 20261118_0003
Revises: 20261118_0002
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20261118_0003"
down_revision: str | None = "20261118_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
ALTER TABLE `model_provider_providers`
  ADD COLUMN `health_fail_count` INT NOT NULL DEFAULT 0
    COMMENT '连续连通失败次数' AFTER `health_message`,
  ADD COLUMN `health_last_success_at` DATETIME(3) NULL
    COMMENT '最近一次连通成功时间 UTC' AFTER `health_fail_count`
"""
        )
    )
    # 旧枚举值迁移到 UP / DOWN / UNKNOWN
    conn.execute(
        text(
            """
UPDATE `model_provider_providers`
SET `health_status` = CASE
  WHEN `health_status` IN ('healthy', 'UP') THEN 'UP'
  WHEN `health_status` IN ('unhealthy', 'DOWN') THEN 'DOWN'
  ELSE 'UNKNOWN'
END
"""
        )
    )
    conn.execute(
        text(
            """
ALTER TABLE `model_provider_providers`
  MODIFY COLUMN `health_status` VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN'
    COMMENT 'UNKNOWN / UP / DOWN'
"""
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
UPDATE `model_provider_providers`
SET `health_status` = CASE
  WHEN `health_status` = 'UP' THEN 'healthy'
  WHEN `health_status` = 'DOWN' THEN 'unhealthy'
  ELSE 'unknown'
END
"""
        )
    )
    conn.execute(
        text(
            """
ALTER TABLE `model_provider_providers`
  MODIFY COLUMN `health_status` VARCHAR(16) NOT NULL DEFAULT 'unknown'
    COMMENT 'unknown/healthy/degraded/unhealthy',
  DROP COLUMN `health_last_success_at`,
  DROP COLUMN `health_fail_count`
"""
        )
    )

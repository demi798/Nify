"""工作流节点 / 边表（图结构拆表存储）。

Revision ID: 20261119_0005
Revises: 20261118_0004
Create Date: 2026-11-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20261119_0005"
down_revision: str | None = "20261118_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
CREATE TABLE IF NOT EXISTS `workflow_nodes` (
  `id`            CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`  CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `workflow_id`   CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `node_key`      VARCHAR(64) NOT NULL COMMENT '图内节点稳定键',
  `node_type`     VARCHAR(32) NOT NULL COMMENT 'start/end/llm/knowledge/condition/tool',
  `name`          VARCHAR(128) NULL,
  `config`        JSON NOT NULL COMMENT '经 NodeConfigParser 校验后的配置',
  `position_x`    DOUBLE NULL,
  `position_y`    DOUBLE NULL,
  `deleted_at`    DATETIME(3) NULL COMMENT '软删时间',
  `alive_node_key` VARCHAR(64)
                    GENERATED ALWAYS AS (IF(`deleted_at` IS NULL, `node_key`, NULL)) STORED,
  `created_at`    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_node_wf_key` (`workflow_id`, `alive_node_key`),
  KEY `idx_node_ws_wf` (`workspace_id`, `workflow_id`, `created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='工作流节点（随工作流软删）'
"""
        )
    )
    conn.execute(
        text(
            """
CREATE TABLE IF NOT EXISTS `workflow_edges` (
  `id`             CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`   CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `workflow_id`    CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `edge_key`       VARCHAR(64) NOT NULL COMMENT '图内边稳定键',
  `source_key`     VARCHAR(64) NOT NULL COMMENT '源 node_key',
  `target_key`     VARCHAR(64) NOT NULL COMMENT '目标 node_key',
  `source_handle`  VARCHAR(64) NULL,
  `target_handle`  VARCHAR(64) NULL,
  `label`          VARCHAR(128) NULL,
  `deleted_at`     DATETIME(3) NULL COMMENT '软删时间',
  `alive_edge_key` VARCHAR(64)
                     GENERATED ALWAYS AS (IF(`deleted_at` IS NULL, `edge_key`, NULL)) STORED,
  `created_at`     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_edge_wf_key` (`workflow_id`, `alive_edge_key`),
  KEY `idx_edge_ws_wf` (`workspace_id`, `workflow_id`, `created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='工作流边（随工作流软删）'
"""
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS `workflow_edges`"))
    conn.execute(text("DROP TABLE IF EXISTS `workflow_nodes`"))

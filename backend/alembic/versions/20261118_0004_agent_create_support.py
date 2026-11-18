"""Agent 创建支持：is_enabled、model_config_id、agent_tool_bindings。

Revision ID: 20261118_0004
Revises: 20261118_0003
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20261118_0004"
down_revision: str | None = "20261118_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # 已有行：model_config_id 先填占位空 UUID，业务创建路径会写真实值
    conn.execute(
        text(
            """
ALTER TABLE `agent_agents`
  ADD COLUMN `model_config_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci
    NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'
    COMMENT '模型目录项 UUID' AFTER `model_name`,
  ADD COLUMN `is_enabled` TINYINT(1) NOT NULL DEFAULT 1
    COMMENT '用户开关' AFTER `config`,
  ADD KEY `idx_agent_ws_model_config` (`workspace_id`, `model_config_id`)
"""
        )
    )
    conn.execute(
        text(
            """
CREATE TABLE IF NOT EXISTS `agent_tool_bindings` (
  `id`             CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`   CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `agent_id`       CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `mcp_server_id`  CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT '对应 toolIds',
  `created_at`     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_tool` (`agent_id`, `mcp_server_id`),
  KEY `idx_agent_tool_ws_mcp` (`workspace_id`, `mcp_server_id`),
  KEY `idx_agent_tool_ws_agent` (`workspace_id`, `agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='Agent 工具绑定（mcp_server_id）'
"""
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS `agent_tool_bindings`"))
    conn.execute(
        text(
            """
ALTER TABLE `agent_agents`
  DROP KEY `idx_agent_ws_model_config`,
  DROP COLUMN `is_enabled`,
  DROP COLUMN `model_config_id`
"""
        )
    )

"""演进 model_provider：统一鉴权字段 + 模型目录表。

Revision ID: 20261118_0002
Revises: 20261117_0001
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20261118_0002"
down_revision: str | None = "20261117_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROVIDERS_DDL = """
CREATE TABLE IF NOT EXISTS `model_provider_providers` (
  `id`                      CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`            CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `name`                    VARCHAR(128) NOT NULL COMMENT '展示名称',
  `provider_type`           VARCHAR(32)  NOT NULL COMMENT 'openai / claude / gemini / ollama',
  `base_url`                VARCHAR(512) NULL COMMENT '可选自定义 API Base；空则用类型默认',
  `auth_scheme`             VARCHAR(32)  NOT NULL DEFAULT 'api_key' COMMENT 'api_key / api_key_header / none',
  `credentials_encrypted`   VARCHAR(1024) NOT NULL COMMENT '加密后的凭证 JSON，禁止明文',
  `auth_extra`              JSON NULL COMMENT '非机密鉴权参数（如 anthropic-version）',
  `default_model_key`       VARCHAR(128) NULL COMMENT '默认模型 key（与 models 表双写）',
  `config`                  JSON NULL COMMENT '超时等额外配置',
  `is_enabled`              TINYINT(1) NOT NULL DEFAULT 1 COMMENT '用户开关',
  `health_status`           VARCHAR(16) NOT NULL DEFAULT 'unknown' COMMENT 'unknown/healthy/degraded/unhealthy',
  `health_checked_at`       DATETIME(3) NULL COMMENT '最近探测时间 UTC',
  `health_latency_ms`       INT NULL COMMENT '探测耗时毫秒',
  `health_error_code`       VARCHAR(32) NULL COMMENT '映射后的错误码',
  `health_message`          VARCHAR(512) NULL COMMENT '健康探测短文案',
  `created_by`              CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `created_at`              DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`              DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_provider_ws` (`workspace_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='模型提供商：连接实例与健康态'
"""

_MODELS_DDL = """
CREATE TABLE IF NOT EXISTS `model_provider_models` (
  `id`                 CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`       CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `provider_id`        CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `model_key`          VARCHAR(128) NOT NULL COMMENT '厂商模型 ID',
  `display_name`       VARCHAR(128) NOT NULL COMMENT '展示名',
  `modality`           VARCHAR(32)  NOT NULL DEFAULT 'chat' COMMENT 'chat / embedding',
  `context_window`     INT NULL,
  `max_output_tokens`  INT NULL,
  `capabilities`       JSON NULL COMMENT 'tools/vision/json_mode/streaming',
  `is_default`         TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否为该 Provider 默认模型',
  `is_enabled`         TINYINT(1) NOT NULL DEFAULT 1,
  `status`             VARCHAR(32) NOT NULL DEFAULT 'available' COMMENT 'available/deprecated/unavailable',
  `created_at`         DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`         DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_mpm_provider_key` (`provider_id`, `model_key`),
  KEY `idx_mpm_ws_provider` (`workspace_id`, `provider_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='模型提供商：模型目录'
"""


def upgrade() -> None:
    conn = op.get_bind()
    # 一期无生产数据依赖：重建 providers，并新建 models
    conn.execute(text("DROP TABLE IF EXISTS `model_provider_models`"))
    conn.execute(text("DROP TABLE IF EXISTS `model_provider_providers`"))
    conn.execute(text(_PROVIDERS_DDL))
    conn.execute(text(_MODELS_DDL))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS `model_provider_models`"))
    conn.execute(text("DROP TABLE IF EXISTS `model_provider_providers`"))
    # 回退到 001 旧结构
    conn.execute(
        text(
            """
CREATE TABLE IF NOT EXISTS `model_provider_providers` (
  `id`                  CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `workspace_id`        CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `name`                VARCHAR(128) NOT NULL,
  `provider`            VARCHAR(32)  NOT NULL,
  `base_url`            VARCHAR(512) NULL,
  `api_key_encrypted`   VARCHAR(512) NOT NULL,
  `default_model`       VARCHAR(128) NOT NULL,
  `config`              JSON NULL,
  `is_enabled`          TINYINT(1) NOT NULL DEFAULT 1,
  `created_by`          CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `created_at`          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_provider_ws` (`workspace_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
"""
        )
    )

-- Nify 一期业务表 DDL（对齐 CLAUDE.md §4）
-- MySQL 8 / InnoDB / utf8mb4_0900_ai_ci
-- 约定：应用生成 UUID v7；默认不加数据库 FK；向量与文件二进制不进 MySQL

CREATE DATABASE IF NOT EXISTS `nify`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `nify`;

-- ---------------------------------------------------------------------------
-- identity
-- ---------------------------------------------------------------------------

-- 用户（无 workspace_id 例外）
CREATE TABLE IF NOT EXISTS `identity_users` (
  `id`            CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `email`         VARCHAR(320) NOT NULL COMMENT '小写邮箱，唯一',
  `password_hash` VARCHAR(128) NOT NULL COMMENT '密码哈希，禁止明文',
  `display_name`  VARCHAR(128) NOT NULL COMMENT '展示名',
  `status`        VARCHAR(32)  NOT NULL COMMENT 'active / disabled',
  `created_at`    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='身份：用户';

-- 工作区（无 workspace_id 例外）
CREATE TABLE IF NOT EXISTS `identity_workspaces` (
  `id`          CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `name`        VARCHAR(128) NOT NULL COMMENT '工作区名称',
  `created_by`  CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT '创建人 user_id',
  `created_at`  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_ws_created` (`created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='身份：工作区';

-- 工作区成员
CREATE TABLE IF NOT EXISTS `identity_workspace_members` (
  `id`           CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `user_id`      CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `role`         VARCHAR(32) NOT NULL COMMENT 'owner / admin / member',
  `created_at`   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_members_ws_user` (`workspace_id`, `user_id`),
  KEY `idx_members_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='身份：工作区成员';

-- ---------------------------------------------------------------------------
-- model_provider
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `model_provider_providers` (
  `id`                  CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`        CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `name`                VARCHAR(128) NOT NULL COMMENT '展示名称',
  `provider`            VARCHAR(32)  NOT NULL COMMENT 'openai / claude / gemini / ollama 等',
  `base_url`            VARCHAR(512) NULL COMMENT '可选自定义 API Base',
  `api_key_encrypted`   VARCHAR(512) NOT NULL COMMENT '加密后的密钥，禁止明文',
  `default_model`       VARCHAR(128) NOT NULL COMMENT '默认模型名',
  `config`              JSON NULL COMMENT '额外厂商配置',
  `is_enabled`          TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  `created_by`          CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `created_at`          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_provider_ws` (`workspace_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='模型提供商：密钥与默认模型';

-- ---------------------------------------------------------------------------
-- agent
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `agent_agents` (
  `id`                   CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`         CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `name`                 VARCHAR(128) NOT NULL,
  `description`          VARCHAR(512) NULL,
  `system_prompt`        TEXT NULL COMMENT '系统提示词',
  `model_provider_id`    CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT '绑定的 provider',
  `model_name`           VARCHAR(128) NOT NULL COMMENT '选用模型名',
  `knowledge_base_ids`   JSON NULL COMMENT '绑定知识库 UUID 列表',
  `mcp_server_ids`       JSON NULL COMMENT '绑定 MCP 服务 UUID 列表',
  `config`               JSON NULL COMMENT '温度等生成参数',
  `created_by`           CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `deleted_at`           DATETIME(3) NULL COMMENT '软删时间；非空表示已删',
  `alive_name`           VARCHAR(128)
                           GENERATED ALWAYS AS (IF(`deleted_at` IS NULL, `name`, NULL)) STORED
                           COMMENT '软删唯一：存活时等于 name',
  `created_at`           DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`           DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_ws_name` (`workspace_id`, `alive_name`),
  KEY `idx_agent_ws_created` (`workspace_id`, `created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='Agent：提示词与工具/知识库绑定';

-- ---------------------------------------------------------------------------
-- conversation
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `conversation_conversations` (
  `id`           CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `agent_id`     CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `title`        VARCHAR(128) NOT NULL COMMENT '会话标题',
  `created_by`   CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `created_at`   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_conv_ws_created` (`workspace_id`, `created_at`, `id`),
  KEY `idx_conv_ws_agent` (`workspace_id`, `agent_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='会话：对话线程';

-- 关键表：字段必须与 CLAUDE.md §4.7 对齐；禁止软删；流式结束一次 INSERT
CREATE TABLE IF NOT EXISTS `conversation_messages` (
  `id`              CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`    CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `conversation_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `role`            VARCHAR(16) NOT NULL COMMENT 'user / assistant / system / tool',
  `status`          VARCHAR(32) NOT NULL COMMENT 'completed / failed / cancelled',
  `content`         TEXT NOT NULL COMMENT '消息正文；流式禁止逐 token UPDATE',
  `token_count`     INT NOT NULL DEFAULT 0 COMMENT 'token 计数',
  `created_at`      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_msg_ws_conv_created` (`workspace_id`, `conversation_id`, `created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='会话消息（大表）；列表禁止 OFFSET';

-- ---------------------------------------------------------------------------
-- knowledge
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `knowledge_bases` (
  `id`           CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `name`         VARCHAR(128) NOT NULL,
  `description`  VARCHAR(512) NULL,
  `created_by`   CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `deleted_at`   DATETIME(3) NULL COMMENT '软删时间',
  `alive_name`   VARCHAR(128)
                   GENERATED ALWAYS AS (IF(`deleted_at` IS NULL, `name`, NULL)) STORED,
  `created_at`   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_kb_ws_name` (`workspace_id`, `alive_name`),
  KEY `idx_kb_ws_created` (`workspace_id`, `created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='知识库';

CREATE TABLE IF NOT EXISTS `knowledge_documents` (
  `id`                CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`      CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `knowledge_base_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `name`              VARCHAR(128) NOT NULL COMMENT '文档展示名',
  `storage_key`       VARCHAR(512) NOT NULL COMMENT '对象存储键；禁止 BLOB',
  `byte_size`         BIGINT NOT NULL DEFAULT 0 COMMENT '原文件字节数',
  `content_type`      VARCHAR(128) NOT NULL COMMENT 'MIME 类型',
  `status`            VARCHAR(32) NOT NULL COMMENT 'pending / processing / ready / failed / delete_failed',
  `error_message`     VARCHAR(512) NULL COMMENT '失败原因摘要',
  `created_by`        CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `deleted_at`        DATETIME(3) NULL COMMENT '软删时间',
  `created_at`        DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`        DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_doc_ws_kb_status` (`workspace_id`, `knowledge_base_id`, `status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='知识库文档元数据（中表）';

-- 关键表：字段必须与 CLAUDE.md §4.7 对齐；禁止软删；正文在 MySQL，向量在 Milvus
CREATE TABLE IF NOT EXISTS `knowledge_chunks` (
  `id`                CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`      CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `knowledge_base_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `document_id`       CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `seq`               INT NOT NULL COMMENT '文档内分块序号，从 0 起',
  `milvus_pk`         CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT '与 Milvus 实体 PK 对齐',
  `content`           TEXT NOT NULL COMMENT '分块正文；Milvus 禁止再存正文',
  `token_count`       INT NOT NULL DEFAULT 0,
  `created_at`        DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`        DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_chunk_milvus` (`milvus_pk`),
  UNIQUE KEY `uk_chunk_doc_seq` (`document_id`, `seq`),
  KEY `idx_chunk_ws_doc` (`workspace_id`, `document_id`, `seq`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='知识库分块（大表）；列表禁止 OFFSET';

-- ---------------------------------------------------------------------------
-- workflow
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `workflow_workflows` (
  `id`           CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id` CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `name`         VARCHAR(128) NOT NULL,
  `description`  VARCHAR(512) NULL,
  `definition`   JSON NOT NULL COMMENT '简版工作流图定义',
  `is_enabled`   TINYINT(1) NOT NULL DEFAULT 1,
  `created_by`   CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `deleted_at`   DATETIME(3) NULL COMMENT '软删时间',
  `alive_name`   VARCHAR(128)
                   GENERATED ALWAYS AS (IF(`deleted_at` IS NULL, `name`, NULL)) STORED,
  `created_at`   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_wf_ws_name` (`workspace_id`, `alive_name`),
  KEY `idx_wf_ws_created` (`workspace_id`, `created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='简版工作流定义';

CREATE TABLE IF NOT EXISTS `workflow_runs` (
  `id`            CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`  CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `workflow_id`   CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `status`        VARCHAR(32) NOT NULL COMMENT 'pending / running / succeeded / failed / cancelled',
  `input`         JSON NULL COMMENT '运行输入',
  `output`        JSON NULL COMMENT '运行输出',
  `error_message` VARCHAR(512) NULL,
  `started_at`    DATETIME(3) NULL,
  `finished_at`   DATETIME(3) NULL,
  `created_by`    CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `created_at`    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  KEY `idx_run_ws_wf_created` (`workspace_id`, `workflow_id`, `created_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='工作流运行记录（中表）；禁止软删；列表禁止 OFFSET';

-- ---------------------------------------------------------------------------
-- mcp
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `mcp_servers` (
  `id`                CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'UUID v7',
  `workspace_id`      CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `name`              VARCHAR(128) NOT NULL,
  `transport`         VARCHAR(32) NOT NULL COMMENT 'stdio / sse / http 等',
  `endpoint`          VARCHAR(512) NOT NULL COMMENT '连接地址或命令入口',
  `auth_encrypted`    VARCHAR(512) NULL COMMENT '加密后的鉴权材料',
  `tool_whitelist`    JSON NULL COMMENT '允许调用的工具名白名单',
  `config`            JSON NULL COMMENT '额外连接配置',
  `is_enabled`        TINYINT(1) NOT NULL DEFAULT 1,
  `created_by`        CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  `deleted_at`        DATETIME(3) NULL COMMENT '软删时间',
  `alive_name`        VARCHAR(128)
                        GENERATED ALWAYS AS (IF(`deleted_at` IS NULL, `name`, NULL)) STORED,
  `created_at`        DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at`        DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_mcp_ws_name` (`workspace_id`, `alive_name`),
  KEY `idx_mcp_ws` (`workspace_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
  COMMENT='MCP 白名单连接';

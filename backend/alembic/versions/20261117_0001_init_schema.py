"""初始化一期业务表（执行 sql/001_init_schema.sql 中的表定义）。

Revision ID: 20261117_0001
Revises:
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision: str = "20261117_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "mcp_servers",
    "workflow_runs",
    "workflow_workflows",
    "knowledge_chunks",
    "knowledge_documents",
    "knowledge_bases",
    "conversation_messages",
    "conversation_conversations",
    "agent_agents",
    "model_provider_models",
    "model_provider_providers",
    "identity_workspace_members",
    "identity_workspaces",
    "identity_users",
)


def _load_table_ddl() -> str:
    """读取建表 SQL，去掉 CREATE DATABASE…; / USE（库由连接串指定）。"""
    sql_path = Path(__file__).resolve().parents[2] / "sql" / "001_init_schema.sql"
    raw = sql_path.read_text(encoding="utf-8")
    lines: list[str] = []
    skipping_create_db = False
    for line in raw.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if skipping_create_db:
            # 跳过 CREATE DATABASE 后续行直到分号结束
            if ";" in stripped:
                skipping_create_db = False
            continue
        if upper.startswith("CREATE DATABASE"):
            skipping_create_db = ";" not in stripped
            continue
        if upper.startswith("USE "):
            continue
        lines.append(line)
    return "\n".join(lines)


def upgrade() -> None:
    ddl = _load_table_ddl()
    # 按分号切分执行；跳过空语句与纯注释块
    statements = [s.strip() for s in ddl.split(";")]
    conn = op.get_bind()
    for stmt in statements:
        if not stmt:
            continue
        # 去掉仅含注释的块
        meaningful = [
            ln
            for ln in stmt.splitlines()
            if ln.strip() and not ln.strip().startswith("--")
        ]
        if not meaningful:
            continue
        conn.execute(text(stmt))


def downgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))

"""数据库基础设施：Base、时间自动填充、逻辑删除。

- MetaObjectHandler 自动填充 created_at / updated_at（CLAUDE.md）
- @TableLogic 逻辑删除
  → SoftDeleteMixin.deleted_at + 查询自动过滤
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    with_loader_criteria,
)

from uuid6 import uuid7

from app.core.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# ---------- 逻辑删除白名单（与 CLAUDE.md 4.9 一致）----------
SOFT_DELETE_TABLES: frozenset[str] = frozenset(
    {
        "agent_agents",
        "knowledge_bases",
        "knowledge_documents",
        "workflow_workflows",
        "workflow_nodes",
        "workflow_edges",
        "mcp_servers",
    }
)


def utc_now() -> datetime:
    """返回 naive UTC 时间，写入 DATETIME(3)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_uuid() -> str:
    """应用层生成 UUID v7 字符串；禁止依赖库内 UUID()。"""
    return str(uuid7())


class Base(DeclarativeBase):
    """ORM 声明基类。"""


class TimestampMixin:
    """自动填充创建/更新时间（对应 createTime / updateTime）。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
        comment="创建时间 UTC",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        comment="更新时间 UTC",
    )


class SoftDeleteMixin:
    """逻辑删除字段；仅白名单表的 Model 可继承。

    查询默认过滤 deleted_at IS NULL；物理删除请用 session.delete（消息/切片等禁用本 Mixin）。
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        default=None,
        comment="逻辑删除时间；NULL 表示未删除",
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class IdMixin:
    """主键 UUID v7（应用层生成；default 便于省略显式赋值）。"""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
        comment="UUID v7",
    )


class WorkspaceMixin:
    """工作区租户列；identity_users / identity_workspaces 禁止使用。"""

    workspace_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=False,
        comment="工作区 ID",
    )


def soft_delete(entity: SoftDeleteMixin) -> None:
    """执行逻辑删除：写入 deleted_at，禁止对非 Mixin 实体调用。"""
    entity.deleted_at = utc_now()


def _register_timestamp_autofill() -> None:
    """before_flush：自动填充 created_at / updated_at。"""

    @event.listens_for(Session, "before_flush")
    def _autofill_timestamps(
        session: Session,
        _flush_context: Any,
        _instances: Any,
    ) -> None:
        if not settings.orm_autofill_enabled:
            return
        now = utc_now()
        for obj in session.new:
            if isinstance(obj, TimestampMixin):
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = now
                obj.updated_at = now
        for obj in session.dirty:
            if isinstance(obj, TimestampMixin) and session.is_modified(
                obj,
                include_collections=False,
            ):
                obj.updated_at = now


def _register_soft_delete_filter() -> None:
    """SELECT 自动附加 deleted_at IS NULL（可用 execution_options(include_deleted=True) 关闭）。"""

    @event.listens_for(Session, "do_orm_execute")
    def _filter_soft_deleted(execute_state: Any) -> None:
        if not settings.orm_logic_delete_enabled:
            return
        if not execute_state.is_select:
            return
        if execute_state.is_column_load or execute_state.is_relationship_load:
            return
        if execute_state.execution_options.get("include_deleted", False):
            return

        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )


_ORM_CONFIGURED = False


def init_engine() -> AsyncEngine:
    """根据配置创建异步引擎与 Session 工厂。"""
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(
            settings.mysql_dsn,
            pool_size=settings.mysql_pool_size,
            max_overflow=settings.mysql_max_overflow,
            pool_recycle=settings.mysql_pool_recycle,
            echo=settings.mysql_echo,
        )
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine


async def close_engine() -> None:
    """关闭数据库引擎。"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends：一请求一 session，结束时统一 commit/rollback。"""
    if _session_factory is None:
        raise RuntimeError("数据库引擎未初始化，请先在 lifespan 中调用 init_engine()")
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def session_context() -> AsyncIterator[AsyncSession]:
    """非请求路径（启动种子等）使用的 session 作用域。"""
    if _session_factory is None:
        raise RuntimeError("数据库引擎未初始化，请先在 lifespan 中调用 init_engine()")
    session = _session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def configure_orm() -> None:
    """在应用启动时调用：注册自动填充与逻辑删除过滤器（幂等）。"""
    global _ORM_CONFIGURED
    if _ORM_CONFIGURED:
        return
    if settings.orm_autofill_enabled:
        _register_timestamp_autofill()
    if settings.orm_logic_delete_enabled:
        _register_soft_delete_filter()
    _ORM_CONFIGURED = True


def assert_soft_delete_allowed(table_name: str) -> None:
    """建 Model / 迁移时校验表是否允许逻辑删除。"""
    if table_name not in SOFT_DELETE_TABLES:
        raise ValueError(
            f"表 {table_name} 不在软删白名单中，禁止使用 SoftDeleteMixin；"
            f"白名单={sorted(SOFT_DELETE_TABLES)}"
        )


class SoftDeleteBase(SoftDeleteMixin):
    """带白名单校验的软删基类；业务 Model 多重继承时优先用 SoftDeleteMixin + 手动 assert。

    推荐写法::

        class Agent(TimestampMixin, SoftDeleteMixin, Base):
            __tablename__ = "agent_agents"

            def __init_subclass__(cls, **kwargs: Any) -> None:
                super().__init_subclass__(**kwargs)
                assert_soft_delete_allowed(cls.__tablename__)
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        table = getattr(cls, "__tablename__", None)
        if table:
            assert_soft_delete_allowed(table)

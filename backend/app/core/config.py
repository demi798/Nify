"""全局配置（启动类读取的唯一配置源）。

说明：按 CLAUDE.md，配置属于 app/core，禁止放在 app/modules（业务模块）下。
「MyBatis-Plus」在本项目对应 SQLAlchemy + 自研分页/自动填充/逻辑删除插件配置。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置；禁止业务代码写连接串或端口魔数。"""

    model_config = SettingsConfigDict(
        env_prefix="NIFY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 服务端口（默认 8080）----------
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    # ---------- MySQL ----------
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "nify"
    mysql_password: str = "nify"
    mysql_database: str = "nify"
    mysql_charset: str = "utf8mb4"
    # 连接池
    mysql_pool_size: int = 10
    mysql_max_overflow: int = 20
    mysql_pool_recycle: int = 3600
    mysql_echo: bool = False

    # ---------- Redis ----------
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_key_prefix: str = "nify:"

    # ---------- 安全 / JWT ----------
    # 生产必须通过环境变量覆盖；用于 JWT 签名与派生数据加密密钥
    secret_key: str = "nify-dev-secret-change-me-32bytes!!"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    # ---------- 演示账号（启动幂等种子；生产请关闭）----------
    seed_demo_account: bool = True
    demo_email: str = "demo@nify.local"
    demo_password: str = "Demo1234!"
    demo_display_name: str = "演示用户"
    demo_workspace_name: str = "演示工作区"

    # ---------- 日志 ----------
    log_level: str = "INFO"
    log_json: bool = False

    # ---------- LLM Gateway 并发（一期 10–25 路对话，上限 50 留余量）----------
    llm_global_concurrency: int = 25
    llm_provider_concurrency: int = 15
    llm_workspace_concurrency: int = 10
    llm_max_concurrency: int = 50
    llm_connect_timeout_sec: float = 10.0
    llm_ttft_timeout_sec: float = 30.0
    llm_idle_timeout_sec: float = 60.0
    llm_total_timeout_sec: float = 300.0
    llm_max_retries: int = 3
    llm_circuit_fail_threshold: int = 5
    llm_circuit_open_sec: float = 30.0

    # ---------- Provider 健康巡检 ----------
    provider_health_enabled: bool = True
    provider_health_interval_sec: int = 60
    provider_health_fail_threshold: int = 3
    # 运行时凭证短缓存 TTL（秒）；0=禁用缓存。改 Key 时写路径会主动失效。
    provider_runtime_cache_ttl_sec: int = 30

    # ---------- 对象存储（本地 Files；后续可换 S3）----------
    storage_root: str = Field(default="./data/files", description="本地文件根目录")

    # ---------- Milvus ----------
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_collection: str = "nify_chunks"
    milvus_embedding_dim: int = 1536
    milvus_enabled: bool = False

    # ---------- Embedding（知识库管线；凭证复用 Provider，不硬编码 Key）----------
    # 优先选用工作区内 modality=embedding 的启用模型；否则用下方 model_key + 自动选 Provider
    embedding_model_key: str = "text-embedding-v3"
    # 可选：固定 Provider UUID；空则自动选启用中的 openai / openai_compatible / fake
    embedding_provider_id: str | None = None

    # ---------- 队列 / worker ----------
    worker_poll_timeout_sec: int = 5
    worker_queues: str = "queue:document_parse"

    # ---------- ORM 插件（对应 MyBatis-Plus 配置）----------
    # 分页
    page_default_limit: int = 20
    page_max_limit: int = 100
    page_max_offset_window: int = 1000
    # 逻辑删除：全局开关（白名单表仍见 db.SOFT_DELETE_TABLES）
    orm_logic_delete_enabled: bool = True
    orm_logic_delete_field: str = "deleted_at"
    # 自动填充字段名（对应 createTime / updateTime）
    orm_create_time_field: str = "created_at"
    orm_update_time_field: str = "updated_at"
    orm_autofill_enabled: bool = True

    @property
    def mysql_dsn(self) -> str:
        """异步 SQLAlchemy DSN（asyncmy）。"""
        return (
            f"mysql+asyncmy://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset={self.mysql_charset}"
        )

    @property
    def mysql_sync_dsn(self) -> str:
        """Alembic 同步迁移用 DSN（pymysql）。"""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset={self.mysql_charset}"
        )

    @property
    def redis_url(self) -> str:
        """Redis 连接 URL。"""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def worker_queue_list(self) -> list[str]:
        """worker 监听的队列名列表（不含 key 前缀）。"""
        return [q.strip() for q in self.worker_queues.split(",") if q.strip()]


@lru_cache
def get_settings() -> Settings:
    """进程内单例配置。"""
    return Settings()


settings = get_settings()

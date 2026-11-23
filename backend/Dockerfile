# Nify API 镜像（多阶段；默认可作 worker：改 CMD 为 python -m app.worker）
# 构建：docker build -t nify-backend -f backend/Dockerfile backend/

# ---------- 构建阶段：安装依赖到独立 venv ----------
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# 编译部分原生依赖（cryptography / asyncmy 等）所需工具
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
COPY app ./app

# 仅装运行时依赖（不含 [dev]）
RUN pip install --upgrade pip \
    && pip install .

# ---------- 运行阶段：精简镜像 + 非 root ----------
FROM python:3.12-slim-bookworm AS runtime

# 运行期系统库（asyncmy / cryptography 可能需要）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libffi8 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 nify \
    && useradd --system --uid 10001 --gid nify --home-dir /app --shell /usr/sbin/nologin nify

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # 容器内默认监听；可用 NIFY_* 覆盖库/Redis 等
    NIFY_SERVER_HOST=0.0.0.0 \
    NIFY_SERVER_PORT=8080 \
    NIFY_STORAGE_ROOT=/app/data/files \
    NIFY_SEED_DEMO_ACCOUNT=false

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# 迁移脚本（app 包已在 venv site-packages）
COPY alembic.ini ./
COPY alembic ./alembic

# 可写数据目录（上传文件 / 日志）
RUN mkdir -p /app/data/files /app/log \
    && chown -R nify:nify /app

USER nify

EXPOSE 8080

# 存活探针：进程起来即可（不依赖 MySQL）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=3)"

# 默认 API；Worker：docker run ... nify-backend python -m app.worker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

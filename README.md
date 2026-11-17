# Nify

内部 AI Agent 开发平台（一期）。形态为**模块化单体**：同一代码库，可拆 `api` / `worker` 进程部署。

目标不是迷你 Dify，而是：可配模型的内部知识问答 Agent + 少量白名单工具 + 简版工作流。

详细编码与架构规范见 [CLAUDE.md](./CLAUDE.md)（唯一规范，改代码前请先读）。

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy(async) / Alembic |
| 前端 | React 18 / Vite / Ant Design / TypeScript |
| 数据 | MySQL 8 / Redis / Milvus Standalone（向量） |
| 规模 | 一期约 20–50 人内网 |

## 目录结构

```text
nify/
├── CLAUDE.md              # 项目规范（唯一）
├── Makefile               # start / stop / build / package …
├── start.sh / stop.sh
├── backend/
│   ├── app/
│   │   ├── main.py        # API 入口（只组装，无业务）
│   │   ├── worker.py      # 异步任务消费入口
│   │   ├── core/          # 基础设施（鉴权、响应、日志、队列…）
│   │   └── modules/       # 业务模块（仅允许 7 个）
│   ├── sql/               # 建表 DDL
│   ├── alembic/           # 数据库迁移
│   ├── log/               # 运行日志（nify-backend.log / nify-frontend.log）
│   └── .env.example
└── frontend/
    └── src/
        ├── app/           # 路由与布局
        ├── shared/        # api-client 等
        └── modules/       # 与后端同名的 7 个业务模块
```

一期业务模块：`identity` · `model_provider` · `agent` · `conversation` · `knowledge` · `workflow` · `mcp`

## 当前进度

已具备：

- 后端 `core` 基础设施（`ApiResult`、鉴权 deps、日志/`request_id`、分页、ORM、队列、SSE 工具、LLMGateway 骨架等）
- 数据库一期 DDL + Alembic 首版迁移
- **identity 演示**：注册 / 登录 + 工作区 CRUD（前后端可联调）
- 一键 `make start` / `make stop`

后续按规范推荐顺序推进：`model_provider` → `conversation` SSE → `knowledge` + worker → …

## 环境要求

- Python ≥ 3.11
- Node.js（建议 18+）与 npm
- MySQL 8（库名默认 `nify`）
- Redis（队列 / 限流）
- （可选）Milvus；默认 `NIFY_MILVUS_ENABLED=false`

## 快速开始

### 1. 配置后端环境变量

```bash
cp backend/.env.example backend/.env
# 按本机修改 NIFY_MYSQL_* / NIFY_REDIS_* / NIFY_SECRET_KEY
```

确保 MySQL 中已创建库与用户，例如：

```sql
CREATE DATABASE IF NOT EXISTS nify
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
-- 再授权给 .env 中配置的账号
```

### 2. 执行迁移

```bash
cd backend
python3 -m pip install -e ".[dev]"
alembic upgrade head
cd ..
```

### 3. 启动前后端

```bash
make start
```

- 后端默认：<http://127.0.0.1:8080>（健康检查 `/api/v1/health`，Swagger `/docs`）
- 前端：Vite 开发服（见终端输出；默认首页跳转工作区 CRUD 演示 `/identity`）
- 日志目录：`backend/log/`

停止：

```bash
make stop
# 或 ./stop.sh
```

### 4. 体验 identity CRUD

1. 打开前端「工作区与登录」页  
2. 注册账号 → 登录  
3. 创建 / 编辑 / 删除工作区  

接口前缀：

- `POST /api/v1/auth/register` · `POST /api/v1/auth/login`
- `GET|POST /api/v1/workspaces` · `GET|PATCH|DELETE /api/v1/workspaces/{id}`

写接口需请求头：`Authorization: Bearer <token>`。工作区作用域业务后续还需 `X-Workspace-Id`。

## Make 命令

| 命令 | 说明 |
|------|------|
| `make start` | 检查 MySQL/Redis，启动后端 + 前端 |
| `make stop` | 优雅停止 |
| `make restart` | 先停再启 |
| `make build` | 安装后端依赖 + 构建前端生产包 |
| `make clean` | 清理构建产物与日志等（保留 `node_modules` / `.venv`） |
| `make package` | 打包到 `dist/nify-0.1.0.tar.gz` |
| `make help` | 查看说明 |

## Worker（可选）

知识库解析 / embedding 等异步任务：

```bash
cd backend
python3 -m app.worker
```

与 API 同代码库；任务经 Redis 队列投递（见 `app/core/queue.py`）。

## 接口约定（摘要）

- 非 SSE 的 `/api/v1/*` 统一信封：`{ "code", "message", "data" }`，成功 `code` 为 `"0"`
- 失败由 `AppError` → 全局 handler，`data` 恒为 `null`
- 大表列表用游标分页 `CursorPage`，禁止无必要的 `COUNT(*)` / OFFSET
- 对话流式用 SSE（`fetch` + Bearer + POST），**不要**用浏览器 `EventSource`

完整规则以 [CLAUDE.md](./CLAUDE.md) 为准。

## 许可证

Proprietary（内部项目）

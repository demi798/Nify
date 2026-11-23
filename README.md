# Nify

内部 AI Agent 开发平台（一期）。形态为**模块化单体**：同一代码库，可拆 `api` / `worker` 进程部署。

目标不是迷你 Dify，而是：可配模型的内部知识问答 Agent + 少量白名单工具 + 简版工作流。

详细编码与架构规范见 [CLAUDE.md](./CLAUDE.md)（唯一规范，改代码前请先读）。  
单元 / 集成测试约定见 [FIX.md](./FIX.md)。

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy(async) / Alembic |
| 前端 | React 18 / Vite / Ant Design / TypeScript |
| 数据 | MySQL 8 / Redis / Milvus Standalone（向量） |
| 测试 | pytest + pytest-asyncio（`should_*_when_*` 命名） 

## 目录结构

```text
nify/
├── CLAUDE.md              # 项目规范（唯一）
├── fix.md                 # 单元 / 集成测试规范与用例清单
├── Makefile               # start / stop / build / package …
├── start.sh / stop.sh
├── backend/
│   ├── app/
│   │   ├── main.py        # API 入口（只组装，无业务）
│   │   ├── worker.py      # 异步任务消费入口
│   │   ├── core/          # 基础设施（鉴权、响应、日志、队列…）
│   │   ├── shared/        # 跨模块契约（如 llm ChatMessage）
│   │   └── modules/       # 业务模块（仅允许 7 个）
│   ├── tests/             # 单测 modules/ + 集成冒烟 integration/
│   ├── sql/               # 建表 DDL（001_init_schema.sql）
│   ├── alembic/           # 数据库迁移
│   ├── docker-compose.yml # 本地 MySQL（宿主机 3307）
│   ├── log/               # 运行日志
│   └── .env.example
└── frontend/
    └── src/
        ├── app/           # 路由与布局
        ├── shared/        # api-client、公共组件、hooks、notify…
        └── views/         # 与后端 modules 同名；页面 API 在各自 api.ts
```

一期业务模块：`identity` · `model_provider` · `agent` · `conversation` · `knowledge` · `workflow` · `mcp`

> 前端约定：业务 HTTP 放在 `views/<module>/api.ts`；跨页组件放 `shared/`，禁止再散落顶层 `src/api` / `src/components`。

## 当前进度

### 已具备

| 模块 | 能力 |
|------|------|
| **core** | `ApiResult`、鉴权 deps、**工作区成员校验**（`X-Workspace-Id` + 成员表）、日志/`request_id`、游标分页、ORM（软删白名单）、队列、本地文件存储、SSE、`commit_before_external_io` |
| **identity** | 注册 / 登录、工作区 CRUD；启动幂等演示账号 |
| **model_provider** | Provider / 模型目录 CRUD；API Key Fernet 加密；连通性测试；健康巡检；Adapters：`openai` / `openai_compatible` / `claude` / `gemini` / `ollama` / `fake`；运行时凭证短缓存；`get_runtime_credentials`（disabled / DOWN 拒绝新请求）；tools 透传 |
| **agent** | Agent CRUD（软删）；`model_config_id` 跨模块校验；MCP `agent_tool_bindings`；知识库多选绑定；列表缓存失效；前端管理页 |
| **conversation** | 会话 CRUD（点查带 `workspace_id`）；消息游标列表；非流式 `chat` / SSE `stream`；经 Agent + Gateway；**MCP tool_calls 回合**（首次非流式 → `call_tool` → 二次补全；失败回传 `role=tool`） |
| **knowledge** | 知识库 CRUD；文档上传 / 列表 / 删除 / 重试；异步 ingest；启用中热更新；删除前引用校验；卡片列表前端 |
| **workflow** | 工作流 CRUD + nodes/edges；`NodeConfigParser`；简版 run（start→llm→end 等）；前端列表 / 创建页 |
| **mcp** | Server CRUD；连通性 `test`；**tool_whitelist**（list / call / debug 一致）；`list_bound_tools`；`POST /{id}/debug`；前端列表 + 详情（含调试 Tab） |
| **运维** | `make start` / `make stop`；Docker Compose MySQL；可选 `python -m app.worker` |

### 前端已联调页面

- `/login` · `/register` · `/identity`（工作区）
- `/model-providers`（模型提供商）
- `/agents`（模型、MCP 工具、知识库多选）
- `/conversation`（选 Agent、建会话、流式发消息；绑定工具时可触发 MCP）
- `/knowledge-bases` · `/knowledge-bases/:kbId/documents`
- `/workflows` · `/workflows/create`
- `/mcp` · `/mcp/:serverId`（列表调试入口 + 详情调试 Tab）

### 后续推荐顺序

对话侧 RAG 检索串联 → 工作流画布 / 更完整节点执行 → 集成测扩到 chat/SSE（fix.md I-P0-04~08）→ …

## 环境要求

- Python ≥ 3.11
- Node.js（建议 18+）与 npm
- MySQL 8（库名默认 `nify`）
- Redis（队列 / 限流）
- （可选）Milvus；默认 `NIFY_MILVUS_ENABLED=false`

## 快速开始

### 1. 启动本地 MySQL（推荐 Docker）

宿主机 **3306** 常被占用，本项目 Compose 映射为 **3307**：

```bash
cd backend
docker compose up -d
# 容器名 nify-mysql；账号/库均为 nify / nify
```

### 2. 配置后端环境变量

```bash
cp backend/.env.example backend/.env
# 按本机修改；Docker MySQL 时常用：
#   NIFY_MYSQL_HOST=127.0.0.1
#   NIFY_MYSQL_PORT=3307
#   NIFY_MYSQL_USER=nify
#   NIFY_MYSQL_PASSWORD=nify
# 并设置足够长的 NIFY_SECRET_KEY（凭证加密依赖）
```

若不用 Docker，需自行建库：

```sql
CREATE DATABASE IF NOT EXISTS nify
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
```

### 3. 执行迁移

```bash
cd backend
python3 -m pip install -e ".[dev]"
alembic upgrade head
cd ..
```

主要 revision：`0001` 初表 → `0002` model_provider v2 → `0003` 健康字段 → `0004` Agent（`is_enabled` / `model_config_id` / `agent_tool_bindings`）→ `0005` `workflow_nodes` / `workflow_edges` → `0006` 知识库 `is_enabled`。

### 4. 启动前后端

#### 方式 A：一键启动（推荐）

```bash
make start
```

- 后端默认：<http://127.0.0.1:8080>（健康检查 `/api/v1/health`，Swagger `/docs`）
- 前端：Vite 开发服（默认 <http://127.0.0.1:5173>；登录后进 `/conversation`）
- 日志目录：`backend/log/`

停止：

```bash
make stop
# 或 ./stop.sh
```

#### 方式 B：单独启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python3 -m pip install -e ".[dev]"
alembic upgrade head

export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

#### 方式 C：单独启动前端

```bash
cd frontend
npm install
npm run dev
```

- Vite 将 `/api` 代理到 `http://localhost:8080`（见 `frontend/vite.config.ts`）
- 也可设置 `frontend/.env` 中的 `VITE_API_BASE_URL`

### 5. 演示账号与联调路径

启动且 `NIFY_SEED_DEMO_ACCOUNT=true`（默认）时，幂等写入：

| 项 | 值 |
|----|-----|
| 邮箱 | `demo@nify.local` |
| 密码 | `Demo1234!` |
| 工作区 | `演示工作区`（owner） |

建议体验顺序：

1. `/login` 登录（表单可预填演示账号）
2. 「工作区」页点「使用」选中当前工作区（请求头会带 `X-Workspace-Id`；**非成员会被拒绝**）
3. 「模型」页新增 Provider（含 `fake` 可离线联调），填 Key；可「连通性测试」；知识库向量化需可用的 **embedding** 模型
4. 「MCP」页创建 Server（如本地退款 MCP `streamable_http`），配置白名单，可「测试」与「调试」调用工具
5. 「知识库」页新建 → 文档页上传（需另开 **worker**）
6. 「Agent」页绑定模型、知识库与 MCP Server
7. 「对话」页发消息；若模型返回 `tool_calls`，会走 MCP 执行后再回复

> Provider 健康态为 **DOWN** 或已禁用时，**新对话**会被拒绝；进行中的流不会因巡检被取消。  
> MCP：`tool_whitelist` 非空时，列表与 `call_tool` / debug **一律**只允许白名单内工具。  
> 知识库启用中可直接编辑/上传；删除前须取消 Agent/工作流关联并清空文档。

## 主要 API（摘要）

统一信封：`{ "code", "message", "data" }`，成功 `code === "0"`。鉴权：`Authorization: Bearer <token>`；工作区业务另需 `X-Workspace-Id`（且调用方须为该工作区成员）。

| 模块 | 前缀 | 说明 |
|------|------|------|
| identity | `/api/v1/auth` · `/api/v1/workspaces` | 注册登录、工作区 |
| model_provider | `/api/v1/model-providers` | Provider CRUD、`POST /{id}/test-connection`、`/{id}/models` |
| agent | `/api/v1/agents` | Agent CRUD（含知识库 / MCP 绑定） |
| conversation | `/api/v1/conversations` | 会话 CRUD、消息列表、`/{id}/chat`、`/{id}/chat/stream`（SSE） |
| knowledge | `/api/v1/knowledge` | bases / documents / chunks / references |
| workflow | `/api/v1/workflows` | 工作流 CRUD（含 nodes/edges）；run 相关 |
| mcp | `/api/v1/mcp` | Server CRUD、`POST /{id}/test`、`POST /{id}/debug`、选项列表 |
| health | `/api/v1/health` | 存活检查 |

大表列表用游标分页 `CursorPage`；对话流式用 SSE（`fetch` + Bearer + POST），**不要**用浏览器 `EventSource`。

完整规则以 [CLAUDE.md](./CLAUDE.md) 为准。

## 测试

约定见 [fix.md](./fix.md)。P0 单测门禁（工作区成员、会话隔离、tool_loop、MCP 白名单、凭证 DOWN/disabled）+ 轻量 HTTP 冒烟，默认可离线跑（LLM / MCP / Milvus mock）。

```bash
cd backend
python3 -m pip install -e ".[dev]"   # 含 pytest、pytest-asyncio
python3 -m pytest tests/ -q
```

- 用例命名：`should_[期望]_when_[条件]`（`pyproject.toml` 已配置收集 `should_*`）
- 路径：`tests/modules/<module>/`、`tests/integration/`
- 禁止单测打真实厂商 / 生产库；完整 chat/SSE 集成见 fix.md §11

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

## Worker（知识库文档解析）

上传文档后状态为 `pending`，需消费 Redis 队列才能完成解析 → 分块 → embedding → 写入 MySQL / Milvus：

```bash
cd backend
# 需已配置 Redis；Milvus 可选（NIFY_MILVUS_ENABLED）
python3 -m app.worker
```

与 API 同代码库；队列名见 `app/core/queue.py`（`document_parse`）。文档状态：`pending` → `processing` → `ready` / `failed`（前端文档页会轮询；失败可「重试」）。

## 许可证

MIT

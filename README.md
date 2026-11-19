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
│   ├── sql/               # 建表 DDL（001_init_schema.sql）
│   ├── alembic/           # 数据库迁移
│   ├── docker-compose.yml # 本地 MySQL（宿主机 3307）
│   ├── log/               # 运行日志
│   └── .env.example
└── frontend/
    └── src/
        ├── app/           # 路由与布局
        ├── api/           # 跨页复用的 HTTP 封装（如 provider / agent）
        ├── components/    # NifyTable / NifyFormDialog 等
        ├── shared/        # api-client 等
        └── views/         # 与后端 modules 同名的 7 个业务视图
```

一期业务模块：`identity` · `model_provider` · `agent` · `conversation` · `knowledge` · `workflow` · `mcp`

## 当前进度

### 已具备

| 模块 | 能力 |
|------|------|
| **core** | `ApiResult`、鉴权 deps、日志/`request_id`、游标分页、ORM（软删白名单含 `workflow_nodes` / `workflow_edges`）、队列、本地文件存储、SSE 工具、LLMGateway 骨架 |
| **identity** | 注册 / 登录、工作区 CRUD；启动幂等演示账号 |
| **model_provider** | Provider / 模型目录 CRUD；API Key Fernet 加密；连通性测试；健康巡检（UP / DEGRADED / DOWN）；Adapters：`openai` / `openai_compatible` / `claude` / `gemini` / `ollama`；运行时凭证短缓存 + 写路径失效；跨模块 `get_enabled_model_binding` / `get_runtime_credentials`（含 embedding） |
| **agent** | Agent CRUD（软删）；`model_config_id` 跨模块校验；MCP `agent_tool_bindings`；**知识库多选绑定**（`knowledge_base_ids`）；列表返回 `knowledge_bases` 简述；列表缓存失效；前端管理页 |
| **conversation** | 会话 CRUD；消息游标列表；`POST /{id}/chat` 非流式；`POST /{id}/chat/stream` SSE（meta/delta/error/done）；经 Agent + Gateway；调 LLM 前 commit 用户消息 |
| **knowledge** | 知识库 CRUD（`is_enabled`、软删）；文档上传 / 列表 / 删除 / 失败重试；分块预览；异步 ingest（解析→分块→embedding→MySQL chunks + Milvus）；**启用中可热更新**（无需先停用/解绑）；删除前校验 Agent/工作流引用（`GET .../references`）；卡片列表前端 |
| **workflow** | 工作流 CRUD；创建/更新同事务写 `workflow` + 批量 `nodes` + 批量 `edges`；详情三表组装；更新整图替换（软删旧图再插）；删除级联软删节点/边；`NodeConfigParser`（start/end/llm/knowledge/condition/tool） |
| **mcp** | 一期：启用中的 MCP 服务选项列表（供 Agent 工具多选） |
| **运维** | `make start` / `make stop`；Docker Compose MySQL；可选 `python -m app.worker` 消费文档解析队列 |

### 前端已联调页面

- `/login` · `/register` · `/identity`（工作区）
- `/model-providers`（模型提供商：列表 / 新增编辑 / 连通性测试 / 展开模型）
- `/agents`（列表含绑定知识库 Tag；新建编辑：模型分组、MCP 工具、**知识库多选**）
- `/conversation`（选 Agent、建会话、流式发消息）
- `/knowledge-bases`（**卡片列表**：启用/停用、编辑、删除；点击进文档页）
- `/knowledge-bases/:kbId/documents`（上传 TXT/MD/PDF、状态轮询、分块预览、失败重试）
- 占位页：`/workflows` · `/mcp`（后端 workflow CRUD 已就绪，前端管理页待接）

### 后续推荐顺序

工作流前端画布 / 执行 → MCP 完整能力 → 对话侧 RAG 检索串联 → …

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
2. 「工作区」页点「使用」选中当前工作区（请求头会带 `X-Workspace-Id`）
3. 「模型」页新增 Provider（OpenAI / OpenAI 兼容 / Claude / Gemini / Ollama），填 Key；可「连通性测试」；若要跑知识库向量化需可用的 **embedding** 模型
4. 「知识库」页新建知识库 → 点击卡片进入文档页上传 TXT / MD / PDF（需另开 **worker** 消费解析队列）
5. 「Agent」页新建 Agent：选模型、写 System Prompt、调参数、多选绑定知识库与 MCP 工具；列表可看到绑定的知识库名称
6. 「对话」页选 Agent 发消息（流式）

> Provider 健康态为 **DOWN** 时，**新建** Agent 绑定该模型会被拒绝；进行中的对话流不会因巡检被取消（仅拦新请求）。编辑 Agent 若未更换模型，可跳过健康再校验。  
> 知识库**启用中可直接编辑/上传**（热更新）；**删除**前须在 Agent（或工作流）中取消关联，并清空文档。停用后不可再绑定、不可上传。

## 主要 API（摘要）

统一信封：`{ "code", "message", "data" }`，成功 `code === "0"`。鉴权：`Authorization: Bearer <token>`；工作区业务另需 `X-Workspace-Id`。

| 模块 | 前缀 | 说明 |
|------|------|------|
| identity | `/api/v1/auth` · `/api/v1/workspaces` | 注册登录、工作区 |
| model_provider | `/api/v1/model-providers` | Provider CRUD、`POST /{id}/test-connection`、`/{id}/models` |
| agent | `/api/v1/agents` | Agent CRUD（列表含 `knowledge_bases`；创建/更新可传 `knowledge_base_ids`；软删） |
| conversation | `/api/v1/conversations` | 会话 CRUD、消息列表、`/{id}/chat`、`/{id}/chat/stream`（SSE） |
| knowledge | `/api/v1/knowledge` | `/bases` CRUD + `is_enabled`；`/bases/options`；`/bases/{id}/references`；`/bases/{id}/documents` 上传与列表；`/documents/{id}` 详情/删除/retry/chunks |
| workflow | `/api/v1/workflows` | 工作流 CRUD（含 nodes/edges；更新整图替换；软删级联） |
| mcp | `/api/v1/mcp-servers` | 启用中的 MCP 选项列表（Agent 工具多选） |
| health | `/api/v1/health` | 存活检查 |

大表列表用游标分页 `CursorPage`；对话流式用 SSE（`fetch` + Bearer + POST），**不要**用浏览器 `EventSource`。

完整规则以 [CLAUDE.md](./CLAUDE.md) 为准。

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

Proprietary（内部项目）

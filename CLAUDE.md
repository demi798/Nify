# Nify CLAUDE.md（唯一规范）

本文件是 Nify 的项目规范。写代码、改代码、审查代码、建表时必须遵守。  
违反「禁止」条款即不合格。

编码条款提炼自阿里巴巴开发手册精神，按 Python + FastAPI 改写。

---

## 0. 产品与约束

| 项 | 决策 |
|----|------|
| 产品 | **Nify** 内部 AI Agent 开发平台 |
| 人力 | 一人开发 |
| 规模 | 一期 **20–50 人**内网；可扩到几千人，一期不做微服务 |
| 形态 | **模块化单体**；部署可分 `api` / `worker` 进程，同一代码库 |
| 技术栈 | **FastAPI** + **React Ant Design** + **MySQL 8** + **Milvus Standalone** + **Redis** |
| 部署 | Docker；生产 **K8s** |
| 注释 | 中文；**UTF-8**；中文乱码必须修正 |

### 0.1 一期必须做（P0）

- 登录与工作区、模型提供商、Agent 配置  
- 对话引擎 + **SSE 流式**  
- 单套知识库 RAG（上传 → 分块 → embedding → Milvus）  
- 简版工作流、MCP 白名单工具（不做任意代码沙箱）  
- Web、运行日志、Docker/K8s 可部署  

### 0.2 一期禁止做

- 微服务、插件 Marketplace、双知识库、可视化 Knowledge Pipeline  
- 强沙箱任意命令、人工审核流、SSO/SAML、Cloud 多租户  
- MySQL 读写分离 / 分库分表；未达第 4.6 红线前禁止分区  
- Milvus Cluster、按工作区动态建集合  
- 用 `EventSource` 做对话（必须 `fetch` + Bearer + POST）  

### 0.3 产品形状

Nify v1 = 可配模型的内部知识问答 Agent + 少量白名单工具 + 简版工作流；不是迷你 Dify。

---

## 1. 仓库与模块结构

```text
nify/
  CLAUDE.md                 # 本文件（唯一规范）
  backend/
    pyproject.toml
    app/
      main.py               # 只组装 App，无业务
      worker.py             # 同镜像；解析/embedding；禁止复制业务代码
      core/                 # 基础设施，禁止业务实体名出现在业务函数中
        config.py db.py security.py deps.py exceptions.py error_codes.py
        logging.py          # 含 request 上下文 contextvars + request_id 中间件
        pagination.py response.py   # response 含 ApiResult / AppJSONResponse / 时间序列化
        schemas.py fields.py rules.py
        redis_client.py queue.py storage.py sse.py health.py
      shared/               # 跨模块契约；默认尽量空
        schemas.py types.py events.py   # 可选；符号至少被 2 个模块使用才可放入
      modules/<name>/       # 唯一放业务
    tests/modules/<name>/
  frontend/
    package.json
    src/
      app/                  # 含 routes.tsx
      shared/               # api-client、公共组件
      views/<同名>/          # 前端业务视图（与后端 modules 7 名对齐）
```

### 1.1 一期仅允许 7 个业务模块

| 模块 | URL 前缀 | 职责 |
|------|----------|------|
| `identity` | `/api/v1/auth`, `/api/v1/workspaces` | 登录、用户、工作区、成员角色 |
| `model_provider` | `/api/v1/model-providers` | Provider、密钥、LLMGateway |
| `agent` | `/api/v1/agents` | Agent、提示词、工具/知识库绑定 |
| `conversation` | `/api/v1/conversations` | 会话、消息、对话引擎、SSE |
| `knowledge` | `/api/v1/knowledge` | 知识库、文档、分块、检索 |
| `workflow` | `/api/v1/workflows` | 简版工作流定义与执行 |
| `mcp` | `/api/v1/mcp` | MCP 连接与工具调用 |

新能力优先归入上表；无法归入且跨 ≥3 个模块才允许新增目录，**必须先改本文件模块表与依赖白名单再写代码**。

其他模块通过 `core.deps.get_current_user` 取用户/工作区，**不调** `identity` service（改成员权限仅在 identity 管理 API 内完成）。

### 1.2 模块内文件模板

```text
modules/<module>/
  __init__.py          # 导出 router
  router.py            # 必需
  schemas.py           # 必需
  service.py           # 必需；跨模块只许调这里
  models.py            # 有持久化则必需
  deps.py exceptions.py constants.py   # 可选
  repository.py        # 仅当 service.py>300 行或查询明显复用时才加
  adapters/<vendor>.py # 外部 SDK
  internal/<helper>.py # 本模块私有
```

禁止目录/文件：`controllers/` `handlers/` `usecases/` `domain/` `application/` `infrastructure/` `services/` `utils.py`。  
`service.py` >500 行：私有逻辑进 `internal/`，对外仍只从 `service.py` 导出。  
Nify 统一采用 **`class XxxService`**（禁止同模块混用「模块级函数风格」）。

### 1.3 层职责

| 层 | 允许 | 禁止 |
|----|------|------|
| `router` | 本模块 service / schemas / deps；用 `ApiResult.ok(data)` 包装成功响应；SSE | 查库；调 LLM/MCP/Milvus/文件系统；业务分支；裸 dict 跨层返回；手写 fail 当控制流；import 他模块 models/repo/internal/adapters |
| `schemas` | 本模块 Pydantic；命名 `<Entity>Create`/`Update`/`Out`/`ListOut`（仅 `data` 内业务体） | ORM；IO；他模块 schema；后缀混用 Schema/DTO/Request；在业务 schemas 里重复定义 ApiResult |
| `models` | 本模块表与表内 relationship | HTTP/schema；业务用例；跨模块 relationship |
| `service` | 用例编排；本模块内部；他模块 Service **公开方法**；注入 session | 定义路由；import 他模块 models/router/repo/internal/adapters/schemas |
| `repository` | `get_by_id`/`list_by_workspace`/`save`/`delete` | 业务规则；adapters；他模块；HTTP。有 repo 后 service 禁止散落重复查询 |
| `adapters` | 第三方 SDK；只接受原生参数 | 业务权限；`import modules.*`；被 router 直调；重试/熔断 |
| `internal` | 本模块私有算法 | 被其他 `modules/*` import |
| `deps` | 组装 Service Depends | 业务逻辑。禁止在业务函数内散落 `XxxService(session)`（测试除外） |
| `exceptions` | 继承 `AppError`，稳定 `code` + HTTP status；由全局 handler 转成 `ApiResult` 失败体 | router 二次包装或 `return ApiResult.fail(...)` 代替抛错 |

`core/` 禁止出现 Agent/Knowledge 等业务用例。  
`shared/` 新增符号门槛：至少 2 个模块使用。  
`ApiResult` / `CursorPage` 只放在 `core/response.py`、`core/pagination.py`，禁止拷贝到各业务模块。

### 1.4 跨模块调用

```text
router → 本模块 service → 本模块 models/repo/internal/adapters
                       ↘ 其他模块 XxxService 公开方法
                       ↘ core.* / shared.*
```

禁止 import 他模块：`models` `repository` `router` `internal` `adapters` `schemas`。  
禁止 A↔B 互相调 Service；改为编排上移到 `conversation`/`workflow`，或 `shared/events.py`（发布方不 import 订阅方）。  
跨模块只存对方资源 **UUID**，需要详情调对方 `service.get`，禁止 join 对方表。

依赖白名单（不在表内禁止）：

| 调用方 | 可调 |
|--------|------|
| `identity` / `model_provider` / `mcp` | （无） |
| `knowledge` | `model_provider` |
| `agent` | `model_provider`, `knowledge`, `mcp` |
| `workflow` / `conversation` | `model_provider`, `knowledge`, `mcp`, `agent` |

事务：一请求一 session；service **禁止 `commit()`**（测试除外），允许 `flush()`；由 `core.db` 统一提交。跨模块多次写入同一 session。

合法调用链示例：

```text
conversation/router → ConversationService.chat
  → AgentService.get / KnowledgeService.retrieve / ModelProviderService（经 Gateway）
禁止：from app.modules.knowledge.models import Document
禁止：from app.modules.knowledge.adapters.xxx import search
```

### 1.5 `main.py` 组装

只注册 exception handlers（输出统一 `ApiResult` 失败体）与 7 个模块 `router`。禁止写业务。  
`modules/<m>/__init__.py` 导出 `router`。

### 1.6 统一接口响应（强制）

所有 **非 SSE** 的 `/api/v1/*` JSON 接口，成功与失败均使用同一信封：

```json
{
  "code": "0",
  "message": "ok",
  "data": {}
}
```

| 字段 | 类型 | 规则 |
|------|------|------|
| `code` | `string` | 成功固定 `"0"`；失败为稳定业务码（`A*` 用户 / `B*` 本系统 / `C*` 第三方） |
| `message` | `string` | 给人看的短句；成功默认 `"ok"`；禁止把堆栈写入 message |
| `data` | `object` / `array` / `null` | 成功：业务体或分页对象；失败：**必须为 `null`** |

实现约定（放 `app/core/response.py`）：

- 类型名：`ApiResult[T]`（Pydantic Generic）。  
- 提供 `ApiResult.ok(data: T, message: str = "ok") -> ApiResult[T]`。  
- 提供 `ApiResult.fail(code: str, message: str) -> ApiResult[None]`（**仅**全局 exception handler / 框架层使用）。  
- `router` 成功路径：`return ApiResult.ok(await svc.xxx(...))`，`response_model` 使用 `ApiResult[XxxOut]` 或 `ApiResult[CursorPage[XxxOut]]`。  
- `router` / `service` **禁止**用 `ApiResult.fail(...)` 代替抛错；业务失败一律 `raise AppError`，由 handler 转成同结构 JSON，并设置对应 HTTP status（4xx/5xx）。  
- 成功 HTTP status：默认 **200**；创建资源可用 **201**，body 仍为 `ApiResult`。  
- 失败时 HTTP status 与 `AppError` 一致，**同时** body 含 `code/message/data=null`（不是裸 `{detail: ...}`）。  
- ValidationError（请求体校验失败）也必须转成同一信封，`code` 用用户侧码（如 `A0001`），`data=null`。

分页时 `data` 为游标页（见 4.8），**不是**在信封外再加 `total/page/size`，也 **禁止** `PageResult` 继承 `ApiResult` 并携带 `total/page/size`：

```json
{
  "code": "0",
  "message": "ok",
  "data": {
    "items": [],
    "next_cursor": "2026-11-02T10:00:00.000Z|<uuid>"
  }
}
```

**SSE 例外：** `/chat/stream` 等 `text/event-stream` **不**使用 `ApiResult` 包裹每个 event；仍按第 2.3 节 `meta/delta/error/done`。其中 `event: error` 的 `data` JSON 字段应包含与 REST 一致的 `code`、`message`（可无外层信封）。

### 1.7 前端

```text
frontend/src/views/<module>/
  pages/  components/  api.ts  types.ts  hooks.ts(可选)  index.ts
```

| 文件 | 允许 | 禁止 |
|------|------|------|
| `pages/*` | 组合 UI、调 hooks/api | 直接 `fetch`；复杂业务计算 |
| `components/*` | 本模块展示 | 调其他模块 `api.ts` |
| `api.ts` | 经 `shared/api-client`；path 与后端 prefix 一致 | 硬编码完整域名（baseURL 来自环境变量） |
| `types.ts` | 类型 | 运行时逻辑 |

路由统一 `frontend/src/app/routes.tsx`。禁止跨模块引用 components；复用进 `shared/components`。前后端模块名必须 7 名对齐。

`shared/api-client` 必须：

1. 解析 JSON 为 `{code,message,data}`；  
2. `code === "0"` 时把 `data` 交给业务层；  
3. `code !== "0"` 或非 2xx 时抛出带 `code/message` 的前端错误（禁止假设 body 为裸业务对象）。

### 1.8 测试

- 路径：`backend/tests/modules/<module>/test_service.py`  
- 外部 adapters **必须 mock**  
- 跨模块只 mock 对方 `XxxService` 公开方法；禁止 fixture 插对方表抄近路（identity 集成测除外）  
- HTTP 集成测断言：成功 `code=="0"` 且业务字段在 `data` 下；失败 `data is null` 且存在 `code/message`  

---

## 2. LLM、容错与 SSE

### 2.1 统一出口

- 模型调用只经 `model_provider.internal.gateway.LLMGateway`。  
- `conversation`/`agent`/`workflow`/`knowledge` 禁止直连厂商 SDK。  
- adapters（openai/claude/gemini/ollama）只做协议与错误映射，**不重试、不熔断**。

### 2.2 Gateway

- 三级限流：全局 Semaphore + per-provider + per-workspace。  
- 分层超时：connect / TTFT / idle / total；超时必须 `aclose`。  
- 重试：最多 3 次、指数退避 + full jitter；仅连接失败、未产出超时、408/429/502/503/504。  
- **已推送 delta：禁止服务端整段自动重试。**  
- 每 provider 熔断；Open 时 fail-fast。  
- **持有 DB 事务 / asyncio.Lock 时禁止调 LLM/MCP/对象存储。**

### 2.3 SSE

```text
event: meta | delta | tool_call | error | done
data: <JSON>
: ping    # ~15s
```

头：`text/event-stream`、`Cache-Control: no-cache`、`X-Accel-Buffering: no`。  
正文内存拼接；结束/取消/失败 **一次** INSERT `conversation_messages`。  
断开：`CancelledError` → `status=cancelled`；`finally` 释放 Semaphore。  
**不**用 `ApiResult` 包裹整条流或每个 delta；`event: error` 的 JSON 至少含 `code`、`message`（与 REST 失败码语义一致）。

### 2.4 知识库异步

上传 → Files → MySQL `pending` → Redis 入队 → 立即返回。  
worker：解析/分块/embed → Milvus → MySQL `ready`/`failed`。  
禁止在 api 内做大文件解析与批量 embedding。

---

## 3. 部署

```text
Browser → Ingress → web(/*) | api(/api，含 SSE)
api → MySQL / Redis / Milvus / Files / 外部 LLM
api → Redis 队列 → worker → MySQL / Milvus / Files / embedding
```

| 组件 | 职责 |
|------|------|
| Ingress | TLS、路由、SSE 关缓冲与长读超时 |
| web | 静态前端 |
| api | 同步业务与 SSE |
| worker | 文档与 embedding |
| MySQL | 元数据与正文（无向量、无文件二进制） |
| Redis | 队列、限流 |
| Milvus Standalone | 向量（自带 etcd/minio 勿当业务网盘） |
| Files | 用户上传原文件 |

一期 api 1～2、worker 1。主瓶颈是外部 LLM。

---

## 4. 数据库规范（建表必遵）

适用 MySQL 8 InnoDB + Milvus Standalone。一期不分区、不分库、不读写分离。

### 4.1 库表默认

```sql
-- 库：utf8mb4 / utf8mb4_0900_ai_ci
-- 每表：ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
```

禁止：MyISAM、MEMORY 业务表、三字节 utf8、表级 ENUM。

### 4.2 主键与通用列

```sql
id            CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
workspace_id  CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,  -- 见例外
created_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
updated_at    DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
PRIMARY KEY (id)
```

- 应用生成 **UUID v7**。禁止库内 `UUID()`、禁止自增业务主键。  
- 外键列同类型，名 `<entity>_id`；**默认不加数据库 FK**（跨模块禁止 FK）；列上必须有索引。  
- 无 `workspace_id` 仅允许：`identity_users`、`identity_workspaces`。  
- 可选列名固定：`created_by`、`status VARCHAR(32)`、`deleted_at`（仅软删白名单表）。  
- 时间一律 `DATETIME(3)` UTC。禁止 `TIMESTAMP`、禁止用 `DATE` 存时间点。

### 4.3 类型字典

| 语义 | 类型 |
|------|------|
| UUID | `CHAR(36) ascii` |
| 状态/短码 | `VARCHAR(16)`/`VARCHAR(32)` NOT NULL |
| 名称 | `VARCHAR(128)` |
| 邮箱 | `VARCHAR(320)` 小写唯一 |
| 布尔 | `TINYINT(1) NOT NULL`（禁止 BIT、禁止 NULL 布尔） |
| 计数 | `INT`；字节大小 `BIGINT` |
| 正文 | `TEXT`（禁止默认 LONGTEXT） |
| 配置 | `JSON`（禁止整列普通索引） |
| 文件 | **禁止 BLOB**；只存 `storage_key VARCHAR(512)` |
| 向量 | **禁止进 MySQL** |

单行除正文 TEXT 外目标 ≤8KB。禁止 `VARCHAR(255)` 滥用。

### 4.4 命名

- 表：`<module>_<复数实体>`（如 `conversation_messages`）。  
- 索引：`idx_<简名>_<列…>`；唯一：`uk_<简名>_<列>`。

### 4.5 索引

算法（左→右）：`workspace_id` → 其他等值列（高选择性优先）→ `created_at, id`。  
必须：主键；含 workspace 的查询至少一索引以 `workspace_id` 最左；列表排序列进复合索引；唯一业务键 `UNIQUE`。

禁止：单列低基数（单独 status/deleted_at/provider）；TEXT/JSON 普通索引；一期 FULLTEXT；重复前缀索引；每列单索引；索引含 `VARCHAR(512)+`；列表 `SELECT *`。  
二级索引 ≤5；大表 ≤6。

软删唯一（生成列）：

```sql
alive_name VARCHAR(128) AS (IF(deleted_at IS NULL, name, NULL)) STORED,
UNIQUE KEY uk_xxx_ws_name (workspace_id, alive_name)
```

一期预置索引（建表直接抄）：

| 表 | 索引 |
|----|------|
| `identity_users` | `uk_users_email (email)` |
| `identity_workspace_members` | `uk_members_ws_user (workspace_id, user_id)`；`idx_members_user (user_id)` |
| `model_provider_providers` | `idx_provider_ws (workspace_id, created_at)` |
| `model_provider_models` | `uk_mpm_provider_key (provider_id, model_key)`；`idx_mpm_ws_provider (workspace_id, provider_id, created_at)` |
| `agent_agents` | `idx_agent_ws_created (workspace_id, created_at, id)` |
| `conversation_conversations` | `idx_conv_ws_created (workspace_id, created_at, id)`；`idx_conv_ws_agent (workspace_id, agent_id, created_at)` |
| `conversation_messages` | `idx_msg_ws_conv_created (workspace_id, conversation_id, created_at, id)` |
| `knowledge_bases` | `idx_kb_ws_created (workspace_id, created_at, id)` |
| `knowledge_documents` | `idx_doc_ws_kb_status (workspace_id, knowledge_base_id, status, created_at)` |
| `knowledge_chunks` | `idx_chunk_ws_doc (workspace_id, document_id, seq)`；`uk_chunk_milvus (milvus_pk)`；`uk_chunk_doc_seq (document_id, seq)` |
| `workflow_workflows` | `idx_wf_ws_created (workspace_id, created_at, id)` |
| `workflow_nodes` | `idx_node_ws_wf (workspace_id, workflow_id, created_at, id)`；`uk_node_wf_key (workflow_id, alive_node_key)` |
| `workflow_edges` | `idx_edge_ws_wf (workspace_id, workflow_id, created_at, id)`；`uk_edge_wf_key (workflow_id, alive_edge_key)` |
| `workflow_runs` | `idx_run_ws_wf_created (workspace_id, workflow_id, created_at, id)` |
| `mcp_servers` | `idx_mcp_ws (workspace_id, created_at)` |

新表：先写 3 条最热 SQL 再配索引，禁止先建后补。

### 4.6 大表与红线

| 级 | 表 |
|----|-----|
| L 大表 | `conversation_messages`、`knowledge_chunks` |
| M 中表 | conversations、documents、workflow_runs |

禁止把流式 token、每次 HTTP 重试日志落库。审计表一期不建。

| 动作 | 触发 | 一期 |
|------|------|------|
| 禁止 OFFSET | 大/中表列表 | 必须 |
| 消息一次落库 | 流式 | 必须 |
| 归档 | 单表 >500 万行或 >20GB | 达线后做（180 天迁 `*_archive`） |
| 分区 / 分库 / 读写分离 | — | 禁止（分区仅红线后且查询皆带时间） |

慢查询 >200ms 且 QPS>1 连续 1 天：只许按本节算法加索引。  
`knowledge_chunks` 与 Milvus entity 数差 >1%：停写并对账。

### 4.7 关键表结构（必须对齐）

`conversation_messages`：`id, workspace_id, conversation_id, role, status, content TEXT, token_count, created_at, updated_at` + 上表索引。  
流式禁止逐 token UPDATE。

`knowledge_chunks`：`id, workspace_id, knowledge_base_id, document_id, seq, milvus_pk, content TEXT, token_count, created_at, updated_at` + 上表唯一/索引。  
删文档：先删 MySQL chunk，再删 Milvus；失败标 `knowledge_documents.status=delete_failed`，禁止只删一边。

### 4.8 分页

- `limit` 默认 20、最大 100。  
- 大/中表用 `cursor`；小表可用 `page` 且 `page*limit<=1000`。  
- **禁止 OFFSET**：`conversation_messages`、`knowledge_chunks`、`workflow_runs`、任何 >10 万行表。  
- 禁止分页 `COUNT(*)`；`len(items)==limit` 表示可能还有下一页。  
- 分页业务体（放入 `ApiResult.data`）形状固定为 `CursorPage`：

```json
{ "items": [], "next_cursor": "<iso>|<uuid>" }
```

`next_cursor` 为空或 `null` 表示没有下一页。完整 HTTP 响应仍为：

```json
{ "code": "0", "message": "ok", "data": { "items": [], "next_cursor": null } }
```

禁止：`PageResult` 继承信封并带 `total`/`page`/`size`；禁止为分页打 `COUNT(*)`。

Keyset 倒序：

```sql
-- 首页
WHERE workspace_id=? AND conversation_id=?
ORDER BY created_at DESC, id DESC LIMIT :limit;

-- 下一页
AND (created_at < :c_at OR (created_at = :c_at AND id < :c_id))
ORDER BY created_at DESC, id DESC LIMIT :limit;
```

WHERE 强制：业务查询带 `workspace_id`（登录查邮箱除外）；软删默认 `deleted_at IS NULL`；禁止 `DATE(created_at)`、禁止对索引列 `LOWER()`（邮箱入库前小写）。  
点查：`WHERE workspace_id=? AND id=? LIMIT 1`。

### 4.9 软删与状态枚举

软删白名单仅：`agent_agents`、`knowledge_bases`、`knowledge_documents`、`workflow_workflows`、`workflow_nodes`、`workflow_edges`、`mcp_servers`。  
消息/切片/运行记录禁止软删。节点与边随工作流定义替换时整批软删再插入。

| 列 | 允许值 |
|----|--------|
| `knowledge_documents.status` | `pending` `processing` `ready` `failed` `delete_failed` |
| `conversation_messages.status` | `completed` `failed` `cancelled` |
| `conversation_messages.role` | `user` `assistant` `system` `tool` |
| `workflow_runs.status` | `pending` `running` `succeeded` `failed` `cancelled` |

新增枚举值必须先改本表。业务必填 `NOT NULL`；禁止空串表示未知状态。

### 4.10 Milvus

- 一期仅集合 `nify_chunks`。禁止按工作区/文档动态建集合。  
- 字段：`milvus_pk`(PK)=MySQL `milvus_pk`；`workspace_id`；`knowledge_base_id`；`document_id`；`embedding FLOAT_VECTOR(dim)`（dim 写死，换模型=新集合）。  
- **禁止**在 Milvus 再存正文。  
- 索引：HNSW，COSINE，`M=16`，`efConstruction=200`，search `ef=64`；向量入库前 L2 归一化。  
- `top_k` 默认 5、最大 20；filter 必含 `workspace_id`（知识库再加 `knowledge_base_id`）；禁止 Milvus 深翻页。  
- 命中后 `milvus_pk IN (...)` 回表 MySQL 取 `content`。  
- 批量 upsert 64～128；先写 MySQL chunk，再写 Milvus，成功后文档 `ready`；重建以 `document_id` 删旧再整篇写。

### 4.11 建表自检

1. InnoDB/utf8mb4/DYNAMIC？ 2. UUID v7 ascii id？ 3. workspace_id（除两例外）？  
4. created_at/updated_at DATETIME(3)？ 5. 无文件/向量入库？ 6. 二级索引≤5/6 且最左 workspace？  
7. 排序列在索引内？ 8. 大表无 OFFSET？ 9. 切片有 milvus_pk 唯一且集合对齐？ 10. status 取值合法？  

任一项否：不得提交该表。

---

## 5. Python 编码规范

### 5.1 命名

1. 有意义英文 ASCII；禁止拼音、中英混、无意义缩写（循环 `i/j/k` 除外）。  
2. 模块/函数/变量 `snake_case`；类 `PascalCase`；常量 `UPPER_SNAKE`。  
3. 函数动宾：`get_agent`/`create_agent`；禁止 `handle`/`process`/`do_it`。  
4. 类后缀：`XxxService`/`XxxError`/`XxxAdapter`；Router 变量名固定 `router`；adapter 文件供应商小写。  
5. 布尔 `is_`/`has_`/`can_`；集合复数 `agents`。  
6. 私有 `_foo`；禁止滥用 `__foo`；跨模块禁止调 `_` 方法。  
7. 文件目录全小写蛇形；禁止模块内 `utils.py`。

### 5.2 格式、类型与集合

8. PEP 8：顶层类/函数间空两行；文件末换行；禁止默认可变参数。  
9. 公开函数必须类型注解。  
10. `list[str]` 等；跨层契约用 Pydantic，禁止裸 dict。  
11. 字典用 `.items()`；空判断 `if not xs`。  
12. 禁止魔数 → `core/config.py` 或模块 `constants.py`。

### 5.3 异常

13. 禁止裸 `except:` / `except Exception: pass` / 吞掉后 `return None`。  
14. 禁止用异常做正常控制流；预检查优于 catch。找不到资源统一抛 NotFound 类 `AppError`。  
15. `try` 最小化。  
16. 业务错继承 `AppError`（稳定 `code` + HTTP status）；SDK 异常在 adapter/service 边界映射。  
17. 错误码简化：成功 `"0"`；失败 `A*` 用户、`B*` 本系统、`C*` 第三方；禁止堆栈当用户提示。  
18. `raise AppError(...) from exc`；禁止丢因果。  
19. 禁止长期保存 `sys.exc_info()`/traceback 对象。  
20. router 不二次包装业务异常、不用 `ApiResult.fail` 代替抛错；全局 handler 输出 `{code,message,data:null}`；`CancelledError` 不得静默。  
21. 资源用 `async with`/`finally`；SSE 必须释放 Semaphore 并关闭上游。

### 5.4 日志

22. 禁止 `print`；`logging.getLogger(__name__)`。  
23. 惰性插值 `%s` 或 `extra=`；大对象先 `isEnabledFor`。  
24. 上下文：`request_id`/`workspace_id`/`user_id`；LLM 加 `provider`/`model`/`latency_ms`/`attempt`。  
25. DEBUG/INFO/WARNING/ERROR 语义固定；禁止每 token INFO。  
26. 禁止日志输出密钥、密码、Authorization、完整手机号；prompt 默认不进 INFO。

### 5.5 并发

27. IO 用 `async def`；禁止协程内 `time.sleep`/`requests`/未封装同步 SDK。  
28. 同步 SDK → `asyncio.to_thread` 并计入 Semaphore；CPU 重活进 worker。  
29. httpx `AsyncClient` 按 provider 单例；禁止每次新建。  
30. 禁止无保护模块级可变全局缓存；多 worker 限流用 Redis。  
31. 任务必有超时与回收；禁止 fire-and-forget；后台进队列。  
32. 锁外调 LLM/MCP/存储；service 禁止自行 `commit()`。  
33. 若用线程池必须命名；主路径以 asyncio 为准。

### 5.6 安全与注释

34. 写操作与点查校验 `workspace_id`。  
35. SQL 参数绑定；提示词/工具参数长度与白名单。  
36. 密钥加密存储；导出默认无明文。  
37. 中文注释写「为什么」；禁止乱码与无意义注释。  
38. TODO 带负责人或意图；禁止大段注释代码提交。

### 5.7 import

39. 顺序：标准库 → 第三方 → 本项目；禁止 `import *`。  
40. 循环依赖先改白名单/分层；函数内 import 仅最后手段并注释原因。

---

## 6. 实现检查清单

**架构**

- [ ] 落在正确路径：后端 `modules/<name>/`、前端 `views/<name>/`，7 名对齐  
- [ ] router 只调本模块 service；跨模块仅 Service 公开方法且在白名单  
- [ ] 无禁止目录名；无直连厂商 SDK  
- [ ] JSON 接口成功/失败均为 `{code,message,data}`；成功 `ApiResult.ok`；失败靠 `AppError`+handler  

**LLM / SSE / 任务**

- [ ] 超时、Semaphore、`finally` 释放  
- [ ] 已产出 delta 无整段重试  
- [ ] 重任务在 worker；消息一次落库  
- [ ] SSE 未误用 `ApiResult` 包每一帧  

**数据库**

- [ ] UUID v7、workspace_id、索引算法、大表 keyset（`data.items/next_cursor`）  
- [ ] 无文件/向量进 MySQL；状态枚举合法；Milvus 单集合对齐  

**编码**

- [ ] 命名/无裸 except/无 print；日志带 id、无密钥  
- [ ] async 无阻塞；锁外调 LLM；中文 UTF-8 无乱码  

---

## 7. 推荐实现顺序

1. `core` + `identity`  
2. `model_provider`（LLMGateway + adapter）  
3. `conversation` SSE（可先无 RAG）  
4. `knowledge` + worker  
5. `agent` 绑定  
6. `mcp` → `workflow`  
7. 前端同名模块  

先跑通：登录 → 配模型 → 对话流式 → 上传文档可检索。

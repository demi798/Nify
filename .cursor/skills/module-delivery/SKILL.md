---
name: module-delivery
description: >
  Delivers a Nify backend+frontend business module end-to-end using the
  model-provider proven workflow: consult design → schema → layered backend →
  stepwise verify → frontend real API → full acceptance. Use when the user
  asks to 交付模块、落地新模块、按 model-provider 流程实现、module delivery、
  或从 0 到 1 做 CRUD+健康检查类模块。
---

# Nify 模块交付流程（源自 model-provider）

将咨询设计 → 表结构 → 后端 → 前端 → 验收 固化为可复用交付流程。  
**硬约束**：遵守仓库根目录 `CLAUDE.md`；每步有产出物与验证；标了「等待用户确认」的决策点不得自行拍板。

> 路径说明：Cursor Skill 标准为 `.cursor/skills/<name>/SKILL.md`。  
> 本 Skill 位于 `.cursor/skills/module-delivery/SKILL.md`（勿写成单文件 `module-delivery.md`，否则可能无法被发现）。

---

## 0. 开始前

1. 确认模块名与一期边界（对照 `CLAUDE.md` 七大模块与依赖方向）。
2. 确认本地依赖可用：MySQL（本项目 Docker 常映射 **3307**）、后端 venv、前端 node。
3. 打开/遵守 `CLAUDE.md`：`ApiResult` 信封、游标分页 `CursorPage`、禁止 router 写业务、凭证禁止明文落库等。

**产出物**：模块名、依赖模块列表、本期不做清单（一句话）。  
**验证**：与用户口头对齐后再进入 Step 1。

---

## Step 1 — 咨询模式：选型 / 数据模型 / 边界

### 做什么

- 供应商或领域对象选型（如 LLM Provider 类型）。
- 表与字段设计：主键 UUID v7、`workspace_id`、时间戳、索引。
- 边界问题显式讨论并落结论（示例见下「关键决策点」）。

### 关键决策点（等待用户确认）

对下列问题给出方案对比与推荐，**暂停等待用户确认**后再改库表：

| 决策 | 说明（model-provider 经验） |
|------|------------------------------|
| 健康态语义 | UP / DEGRADED / DOWN / UNKNOWN；连续失败阈值（如 3 次 → DOWN） |
| DOWN 与进行中对话 | **只拦新请求**，不取消进行中的 stream |
| 凭证与缓存 | 加密入库；改 Key 写路径主动 `invalidate`；短 TTL 兜底 |
| API 形态 | 列表 CursorPage；详情嵌套字段；更新用 PUT 还是 PATCH |
| 兼容类型 | 如 `openai_compatible` 是否强制 Base URL + 真实 model id |

### 产出物

- 简短设计纪要（可写在对话中，用户要求时再落 md）。
- 表清单 + 字段字典 + 索引。
- 接口清单草稿：`POST/GET/GET{id}/PUT/DELETE` + 领域动作（如 `test-connection`）。

### 验证

- 用户明确回复「按此方案做」或等效确认。
- 依赖方向不违反 `CLAUDE.md`（如 conversation → model_provider，禁止反向）。

---

## Step 2 — 更新 schema / 迁移

### 做什么

- 更新 `backend/sql/001_init_schema.sql`（或模块对应 DDL 段落）。
- 新增 Alembic revision；本地执行 `alembic upgrade head`。
- ORM `models.py` 与 DDL 对齐。

### 产出物

- DDL 变更、Alembic 文件、`models.py`。

### 验证

```bash
cd backend && alembic upgrade head
# 抽查关键列是否存在（示例）
docker exec nify-mysql mysql -unify -pnify nify -e "SHOW COLUMNS FROM <table> LIKE 'health%';"
```

### 注意事项（踩坑）

- MySQL 账号/端口搞错会 1045；本项目 Docker 常见 **宿主机 3307**，配置在 `backend/.env`，**不要**写进 `frontend/.env`。
- 宿主机 3306 常被占用；容器名冲突先处理旧容器。
- Alembic 多语句/脏注释可能导致执行异常；保持 revision 干净。
- 迁移未升完就启动健康巡检，会出现 `Unknown column`；先 `upgrade head` 再依赖新字段。

---

## Step 3 — 后端分层实现（核对后的准确描述）

> **核对结论（相对「CRUD + 连通性测试 + 模型同步 + 健康检查」）**  
> 准确表述应为：  
> **Provider CRUD + 连通性测试 + 模型目录（预置默认模型 + CRUD）+ 健康巡检**。  
> 「模型同步」若指从上游 `/models` 拉取目录，**本期 model-provider 未做**；不要在未实现时写进验收清单。若用户明确要求上游同步，单开一步并等待确认。

### 3.1 骨架

- `schemas` / `models` / `service` / `router` / `deps` / `constants`
- 成功：`return ApiResult.ok(...)`；失败：`raise AppError`（禁止业务里 `ApiResult.fail`）

### 3.2 Provider CRUD

- `POST` 创建（201）、`GET` 列表（**CursorPage**）、`GET/{id}` 详情、`PUT/{id}` 更新、`DELETE/{id}`
- 入参校验：`extra=forbid`、枚举、URL、必填字段

### 3.3 连通性测试

- `POST /{id}/test-connection`
- 成功：UP + latency + last_success_at + fail_count=0
- 失败：fail_count+1；未达阈值 DEGRADED；达阈值 DOWN

### 3.4 模型目录

- 创建 Provider 时按类型预置默认模型；支持 `/{id}/models` CRUD
- `openai_compatible`：**强制** Base URL + `default_model_key`（上游真实 model id）

### 3.5 健康巡检

- lifespan 启动定时任务；遍历 `is_enabled`，调同一套连通性逻辑
- **只更新库内健康态**；禁止取消进行中的 LLMGateway stream
- 新请求入口（如 `get_runtime_credentials`）：`DOWN` / 禁用 → 拒绝

### 3.6 凭证

- Fernet 加密写入 `credentials_encrypted`；对外只暴露 `has_api_key`
- 改 api_key / base_url / 禁用 / 删除：调用 `invalidate_provider_runtime`

### 产出物

- 可运行的模块代码 + 路由挂到 `main.py` +（如有）adapter 注册

### 验证（每完成一小块就测，通过再往下）

```bash
cd backend && python -m compileall -q app/modules/<module>
# 登录拿 token + 带 X-Workspace-Id
curl -s -X POST "$BASE/api/v1/<prefix>" -H "Authorization: Bearer $TOKEN" \
  -H "X-Workspace-Id: $WS" -H "Content-Type: application/json" -d '{...}'
curl -s "$BASE/api/v1/<prefix>?limit=20" -H "Authorization: Bearer $TOKEN" \
  -H "X-Workspace-Id: $WS"
# 断言：code=="0"；列表 data 为 {items,next_cursor}；失败 data==null
```

### 注意事项（踩坑）

- 路径 `{id}` 必须是真实 UUID；字面量 `{id}` 或把 `test-connection` 当 id → `A0001 id 格式无效`。
- OpenAPI/curl 别漏 `Authorization` 与 `X-Workspace-Id`。
- 列表不要返回裸数组（违反分页规范时）；前端 `NifyTable` 要吃 `items`。
- 兼容端点默认模型不能瞎填 `gpt-4o-mini`（阿里云等会 `model_not_found`）；必须填控制台真实 model id。
- 403/`C0005` 多半是 Key；`model_not_found` 是模型名。

**决策点（等待用户确认）**：是否实现「上游模型列表同步」；默认不做。

---

## Step 4 — 逐步编译 / curl 门禁

### 规则

- **禁止**在上一步验证失败时进入下一步。
- 顺序建议：migrate → compileall → 创建 → 列表 → 详情 → 更新 → 连通测试 → 删除（或禁用）。

### 产出物

- 每步验证记录（命令 + 关键响应字段：`code` / `health.status` / `id`）。

### 验证

- 创建返回 201 + `code=0` + 业务 id。
- 连通测试返回嵌套 `health`（若模块约定如此）。
- 改 Key 后新请求不再用旧凭证（缓存已失效）。

---

## Step 5 — 前端对接

### 做什么

1. 在约定位置创建/更新 API 模块（model-provider：`src/api/provider.ts`，经 `shared/api-client`）。
2. 页面 `NifyTable` 的 `api` 从 mock 换成真实列表（`getProviderList` 等）。
3. `NifyFormDialog` submit → create / update（PUT）。
4. 删除 → `confirmDelete` + delete API。
5. 领域列：健康态 Tag（UP 绿 / DEGRADED 黄 / DOWN 红 / UNKNOWN 灰）+ 延迟；操作列连通测试；模型数可展开。
6. 类型与后端出参对齐（嵌套 `modelConfig` / `health` 时不要读扁平旧字段）。

### 产出物

- `api` 方法、`types`、页面无 mock。

### 验证

```bash
cd frontend && npx tsc --noEmit
# 浏览器：登录 → 选工作区 → 模块页增删改 → 连通测试提示
```

### 注意事项（踩坑）

- `api-client` 已解包 `data`；业务层不要再当成整包信封。
- 必须带工作区：未选 workspace 先提示，而不是裸 400。
- 游标分页与 `NifyTable` 的 page 模式不完全同构：小表可 `limit=pageSize` 拉一页；不要假定有 `total` COUNT。

---

## Step 6 — 完整验收

### 后端 curl 清单

- [ ] 创建 / 列表（CursorPage）/ 详情 / 更新 / 删除
- [ ] 领域动作（如 test-connection）
- [ ] 失败用例：缺头、非法 id、校验失败 → `code != 0` 且 `data=null`
- [ ] （若有）定时巡检日志：`health sweep done ...`

### 浏览器清单

- [ ] 登录 + 工作区
- [ ] 列表展示健康态 / 模型数
- [ ] 新增（含兼容类型必填项）
- [ ] 编辑（含默认模型）
- [ ] 连通测试成功/失败提示
- [ ] 删除确认

### 产出物

- 验收勾选结果；已知问题列表（若有）。

### 验证

- 以上清单全部勾选或与用户确认「可接受遗留」。

**决策点（等待用户确认）**：是否提交 git / 写 README；用户未要求则不提交、不主动写 md。

---

## 代理执行清单（复制跟踪）

```text
Module Delivery Progress:
- [ ] Step 1 设计纪要（等待用户确认关键决策）
- [ ] Step 2 DDL + 迁移 + ORM（alembic upgrade 通过）
- [ ] Step 3.1 骨架 compile 通过
- [ ] Step 3.2 CRUD curl 通过
- [ ] Step 3.3 连通性 curl 通过
- [ ] Step 3.4 模型目录（非上游同步，除非用户确认）
- [ ] Step 3.5 健康巡检日志正常
- [ ] Step 3.6 凭证加密 + 写路径 invalidate
- [ ] Step 4 门禁记录齐全
- [ ] Step 5 前端 tsc + 浏览器主路径
- [ ] Step 6 验收清单勾选
```

---

## 与 CLAUDE.md 的关系

- 本 Skill = **交付 SOP**（怎么一步步做完一个模块）。
- `CLAUDE.md` = **项目法**（分层、信封、分页、依赖方向等）。
- 冲突时以 `CLAUDE.md` 为准；本 Skill 只补充流程、门禁与踩坑。

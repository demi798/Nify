# Nify 单元测试规范（fix.md）

> 依据：核心链路（流式/非流式对话、工作区门禁、知识入库检索、MCP 绑定与执行）与风险地图（越权、工具白名单、静默降级、并发落库、双写一致性）。  
> 配套：`CLAUDE.md` §1.8；冲突时以本文件「禁止事项」与「必须单测」为准，细则实现仍服从模块边界。

---

## 0. 总则

| 项 | 约定 |
|----|------|
| 路径 | `backend/tests/modules/<module>/test_*.py` |
| 框架 | `pytest` + `pytest-asyncio` |
| 命名 | 用例函数：`should_[期望结果]_when_[输入条件]` |
| 结构 | Given → When → Then（可用注释分段） |
| 断言 | 必须绑定业务语义（见 §6） |
| 外部依赖 | LLM / MCP / Milvus / 对象存储 / 真实厂商 HTTP **默认 mock** |

一期人力有限：**先覆盖风险地图 P0/P1，再扩面。**

---

## 1. 哪些代码必须写单测（结合核心链路）

### 1.1 按链路强制覆盖

| 核心链路 | 必须单测的单元（公开行为） | 最低场景 |
|----------|---------------------------|----------|
| C 身份与工作区 | `get_current_workspace`（或抽出的成员校验函数） | 非成员 → 403；成员 → 通过；缺 Header → 4xx |
| A/B 对话主路径 | `ConversationService.chat` / `stream_chat` 编排中的**可测切片**（prepare、失败落库、工具回合） | 无工具成功；`tool_calls`→`call_tool`→二次回复；Agent 禁用拒绝；Provider DOWN 拒绝 |
| A/B 工具回合 | `conversation.internal.tool_loop` | 合法 tool_calls；非法 JSON；`call_tool` 抛错回传 tool 消息且不向外抛导致 500 |
| E MCP | `McpService.call_tool` / `debug_call` | 白名单外拒绝；白名单内调用；Server 停用拒绝 |
| E MCP 降级可观测 | `list_bound_tools` 与对话 prepare 的契约 | `tool_ids` 非空且全部失败时**不得静默当无工具**（按产品选定：抛错或返回 degrade 标记，测该契约） |
| D 知识 | `KnowledgeService.retrieve` 的校验与空结果分支；pipeline 状态迁移的纯逻辑 | query 空拒绝；milvus 关闭返回空；失败写 `failed` |
| 凭证门禁 | `ModelProviderService.get_runtime_credentials` | disabled / health=DOWN 拒绝；正常返回字段形状（api_key 可用假值） |

### 1.2 按风险点强制覆盖

| 风险 | 必须有的用例意图 |
|------|------------------|
| 跨租户越权 | workspace 门禁 + 会话 `workspace_id` 点查隔离 |
| 工具白名单绕过 | 执行路径与 list 路径一致拒绝 |
| 静默无工具 | 绑定失败可被测试断言到 |
| 半截落库 | LLM 失败后用户消息在、assistant `failed`（mock DB 或测试 session） |
| 参数非 object | tool 入参 array/string → 错误 tool 消息，不默默 `{}` 执行 |

### 1.3 「必须单测」的代码形态

- 模块 **Service 公开方法**的业务分支（权限、状态机、校验、错误码）。  
- `internal/` 中带业务规则的纯函数/协程（如 `tool_loop`、chunk 切分规则、白名单过滤）。  
- `core` 中门禁、错误映射、分页 cursor 编解码。  

---

## 2. 哪些不写单测、用集成测试替代（外部依赖特点）

Nify 外部依赖特点：**LLM 厂商不稳定、MCP 进程外协议、Milvus/Redis/MySQL 有状态、SSE 长连接。**

### 2.1 单测不要测、改为集成测（或契约测）的部分

| 对象 | 原因 | 替代 |
|------|------|------|
| `LLMGateway` 真实重试/熔断/限流时序 | 需时钟与多请求；单测易碎 | 集成：fake provider + 注入可控 httpx/mock transport；或专门 gateway 集成套件 |
| 各厂商 `adapters/*` 真实 HTTP | 网络与厂商变更 | **必须 mock**；仅保留「请求体形状 / 错误码映射」的窄单测（可选） |
| `mcp.adapters.client` 真实 SSE/HTTP/stdio | 进程与协议 | mock `list_tools`/`call_tool`；另备 1 条本地 fake MCP 冒烟（手工或 CI job，不算单测门禁） |
| Milvus 真实 search/upsert | 环境重 | mock `MilvusStore`；集成环境有 Milvus 再跑 `tests/integration` |
| 完整 SSE 帧时序 + 真实 Uvicorn | 偏 E2E | `httpx.AsyncClient` + ASGI 集成测；或前端 E2E 少量冒烟 |
| Worker 消费 Redis 全链路 | 多进程 | 集成：入队 → 调 `pipeline.process_document`（队列可假） |
| Alembic / 真实多迁移 | 慢 | CI 用测试库 `upgrade head` 一次即可 |

### 2.2 单测里允许「带 DB」的边界

- 可用 **SQLite/测试 MySQL + 事务回滚** 测 Service 落库与 `workspace_id` 隔离（仍算模块测，不是厂商集成）。  
- 禁止单测连生产库、禁止依赖本机已启动的退款 MCP/真实 OpenAI。

### 2.3 跨模块

- 单测 **只 mock 对方 `XxxService` 公开方法**（`CLAUDE.md` §1.8）。  
- 禁止 fixture 插入他模块表「抄近路」（identity 登录集成除外）。

---

## 3. 测试命名规范

### 3.1 函数名

```text
should_[期望结果]_when_[输入条件]
```

- 全小写蛇形；期望结果用业务词，不用 `ok`/`works`。  
- 条件要可判定（谁、什么状态、什么入参）。

**示例（合格）：**

```python
async def should_reject_chat_when_caller_not_workspace_member():
    ...

async def should_return_tool_error_message_when_mcp_call_raises():
    ...

async def should_refuse_call_tool_when_name_not_in_whitelist():
    ...
```

**示例（不合格）：**

```python
def test_chat():  # 无期望、无条件
def should_work_when_normal():  # 空泛
def test_1():  # 无意义
```

### 3.2 文件名

```text
tests/modules/<module>/test_<单元>.py
```

例：`test_conversation_service.py`、`test_tool_loop.py`、`test_mcp_call_tool.py`、`test_workspace_deps.py`。

---

## 4. 测试结构：Given-When-Then

每个用例正文用注释或空行分成三段：

```python
async def should_mark_assistant_failed_when_llm_raises():
    # Given：已登录工作区成员、会话存在；Gateway.chat 抛错
    ...

    # When：调用非流式 chat
    ...

    # Then：抛出业务错误；库中存在 failed 的 assistant 消息；用户消息仍在
    ...
```

要求：

- **Given** 只准备状态与依赖（含 mock 返回值）。  
- **When** 只触发一个主要行为（一次 Service 调用或一次 deps 解析）。  
- **Then** 只断言与本用例意图相关的结果（见 §6），不顺带断言无关字段大全。

异步用例统一：`@pytest.mark.asyncio`。

---

## 5. Mock 使用规范

### 5.1 必须 mock

| 依赖 | 方式 |
|------|------|
| LLM 厂商 / `LLMGateway` | mock `chat` / `stream_chat` / `embed` 返回值或抛错 |
| MCP 远端 | mock `mcp.adapters.client.list_tools` / `call_tool`，或 mock `McpService` 中外呼 |
| Milvus | mock store `search` / `upsert` / `delete` |
| 对象存储读大文件 | mock `get_file_storage()` |
| 跨模块 Service | mock `AgentService.get_agent`、`ModelProviderService.get_runtime_credentials` 等 **公开方法** |
| 时间/随机（若影响状态机） | 可 freeze；非必须 |

### 5.2 不要 mock

| 对象 | 原因 |
|------|------|
| 被测模块自己的业务分支逻辑 | mock 掉就等于没测 |
| 纯函数（cursor 编解码、白名单 filter、chunk 切分） | 直接测真实实现 |
| Pydantic schema 校验 | 直接构造合法/非法入参 |
| 内存态简单结构（`ChatMessage` 等 shared 类型） | 真实对象即可 |

### 5.3 禁止的 mock 用法

- Mock 他模块 `models` / `internal` / `adapters` 后在本模块断言实现细节。  
- 在单测里 `AsyncMock` 掉被测函数自身再「断言调用了自己」。  
- 用 mock 吞掉本应暴露的 `AppError` 码（除非测的就是「调用方如何处理」）。

---

## 6. 断言规范（是否适配本项目）

**结论：适配，且对本项目是强制的。**

Nify 统一响应与错误模型是 `{code, message, data}` + `AppError`。无意义断言（只 `assert result is not None`）无法锁住越权码、落库 status、工具白名单等风险点。

### 6.1 有意义断言（要求）

优先断言：

1. **错误码 / 异常类型**：`exc.code == ErrorCode.FORBIDDEN.value`（或项目约定字段）。  
2. **业务状态**：消息 `status == "failed"`；文档 `status == "ready"`。  
3. **隔离结果**：他工作区资源查询为空或 NotFound。  
4. **副作用契约**：`call_tool` 被调用次数与参数（工具名、server_id）；白名单外 **未被** 调用。  
5. **可观测降级**：若定义 `tools_degraded` / 特定错误码，必须断言该字段或码。

### 6.2 弱断言（单独使用不合格）

```python
assert result is not None
assert True
assert len(items) >= 0
assert response  # 真值即可
```

可与强断言组合，不能作为唯一 Then。

### 6.3 HTTP/集成层

- 成功：`body["code"] == "0"` 且业务字段在 `data` 下。  
- 失败：`data is None` 且存在 `code` / `message`（与 `CLAUDE.md` §1.8 一致）。

---

## 7. 禁止事项

1. **禁止** 无 `should_..._when_...` 命名的新增用例（旧代码迁移可暂留，新增必须合规）。  
2. **禁止** 单测访问真实 OpenAI/Anthropic/线上 MCP/生产 MySQL/Milvus。  
3. **禁止** 为过线而写空测、`assert True`、只测「能 import」。  
4. **禁止** 在单测中 `time.sleep` 等待真实网络；异步等待用可控 mock / 立即返回。  
5. **禁止** 跨模块单测直接 import 他模块 `internal`/`adapters`/`models` 拼数据（除非 `shared` 契约）。  
6. **禁止** 在单元测试里启动完整多 worker + 真实 Redis 消费作为门禁（放到集成 job）。  
7. **禁止** 断言厂商响应原文长快照（易碎）；断言映射后的 `AppError` 与关键字段即可。  
8. **禁止** 用集成环境偶然成功掩盖未 mock 的外呼（CI 必须可离线跑单测集合）。  
9. **禁止** 测试中打印密钥、完整 Authorization、真实 api_key。  
10. **禁止** 以「覆盖率数字」替代风险场景：未覆盖 §1 强制场景，即使行覆盖率高也不算达标。

---

## 8. 落地清单（与测试精力对齐）

```text
P0 单测门禁（合并前必须绿）
  - workspace 成员校验
  - conversation workspace 隔离（点查/chat）
  - tool_loop：成功 / MCP 失败回传
  - call_tool：白名单拒绝
  - credentials：DOWN/disabled 拒绝

P1 单测（迭代补齐）
  - list_bound_tools 全失败可观测
  - chat/stream 失败落库 status
  - retrieve 空 query / milvus off
  - tool 参数非 dict 不执行

集成测试清单见 §11（P0/P1/P2）；单测门禁与集成 job 分离。
```

---

## 9. 用例模板（复制用）

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def should_refuse_call_tool_when_name_not_in_whitelist(
    mcp_service,  # fixture：真实 Service + 测试 session
    monkeypatch,
):
    # Given：Server 启用且 whitelist=["safe_tool"]；远端 call_tool 可追踪
    remote = AsyncMock()
    monkeypatch.setattr(..., remote)  # 仅 mock 外呼

    # When / Then
    with pytest.raises(AppError) as ei:
        await mcp_service.call_tool(
            workspace_id=ws,
            mcp_server_id=server_id,
            tool_name="not_allowed",
            arguments={},
        )
    assert ei.value.code == ErrorCode.BAD_REQUEST.value  # 或项目约定码
    remote.assert_not_awaited()
```

---

## 10. 修订记录

| 版本 | 说明 |
|------|------|
| 2026-11-23 | 首版：对齐核心链路与风险地图；明确 must/skip、命名、GWT、mock、断言、禁止项 |
| 2026-11-23 | 增补 §11 集成测试清单（P0/P1/P2），对齐核心链路与风险地图 |

---

## 11. 集成测试清单

> 依据：`CLAUDE.md` 一期主路径（登录 → 模型 → SSE 对话 → 知识可检索 → MCP 白名单工具）及本文件前述**核心链路 / 风险地图**。  
> 运行形态：测试库 MySQL（或 CI 容器）+ ASGI `httpx.AsyncClient`；LLM / 远端 MCP / Milvus **默认用 fake 或 mock transport**，仅 P1/P2 标明「需真实依赖」的条目才连外部。  
> 与单测分工：集成测验证**跨模块编排 + HTTP 契约 + 落库结果**；不替代 §1 的纯逻辑单测。

### 11.0 环境约定（集成）

| 项 | 约定 |
|----|------|
| 入口 | `POST /api/v1/auth/login` 拿 token；业务请求带 `Authorization` + `X-Workspace-Id` |
| 成功断言 | `code == "0"` 且业务在 `data`；失败 `data is null` 且有 `code`/`message` |
| SSE | `POST .../chat/stream`，断言 `event: meta/delta/error/done`；**禁止**用 `EventSource` |
| Provider | 优先 `fake` 或可注入的 mock Gateway，避免打真实厂商 |
| 隔离 | 每用例独立 workspace 或事务回滚；禁止污染共享 demo 数据当唯一依据 |

命名建议（集成）：`should_[期望]_when_[条件]_via_http`（可与单测同一句式，文件放 `tests/integration/` 或 `tests/modules/*/test_*_api.py`）。

---

### 11.1 P0 — 核心链路，必须覆盖

合并 / 发版门禁级。任一条失败视为集成未过。

| ID | 测什么 | 验证什么 | 为什么是 P0 |
|----|--------|----------|-------------|
| I-P0-01 | **登录 → 选工作区 → 带 Header 调业务 API** | 登录返回 token；缺 `X-Workspace-Id` → 业务码失败；合法成员可 `GET` 会话列表 `code=0` | 所有核心链路的门禁；对应风险「工作区上下文」 |
| I-P0-02 | **工作区成员隔离（越权）** | 用户 A 的 token + 用户 B 的 `workspace_id`（或非成员 UUID）访问 conversations/mcp → **403/拒绝**，且 `data=null` | 风险地图最高：跨租户读写 |
| I-P0-03 | **会话 workspace 隔离** | 在 WS-A 创建会话后，用 WS-B 成员 token 对同一 `conversation_id` 做 get/chat → NotFound/Forbidden | 对话核心链路数据面；防 IDOR |
| I-P0-04 | **配置 fake Provider + 创建 Agent → 非流式 chat** | `POST .../chat` 成功；`data` 含 user/assistant 消息；库中两轮 `status=completed` | 链路 B 端到端；不依赖真实 LLM |
| I-P0-05 | **同一会话 SSE 流式对话** | 收到 `meta` → 至少一个 `delta` → `done`；`done` 含 assistant_message_id；消息表有对应助手行 | 链路 A 产品主路径；`CLAUDE.md` 强制 fetch+SSE |
| I-P0-06 | **SSE / chat 失败落库** | mock LLM 抛错后：HTTP/SSE 带 `code`+`message`；用户消息仍在；存在 `status=failed`（或约定等价）的 assistant | 风险「半截历史 / 静默失败」 |
| I-P0-07 | **MCP 白名单执行（HTTP debug 或对话工具）** | 配置 whitelist 后：白名单外 `POST .../mcp/{id}/debug` 失败且未执行；白名单内成功返回 `result`/`elapsed_ms` | 链路 E + 风险「call_tool 绕过白名单」 |
| I-P0-08 | **Agent 绑定 MCP → 对话触发 tool_calls（mock LLM）** | 第一次 LLM 返回 tool_calls；MCP mock 被调用；最终助手有回复且 HTTP/SSE 成功收尾 | 链路 A/B 与 E 交汇；工具主价值路径 |

---

### 11.2 P1 — 主要功能，应该覆盖

迭代内应具备；可与 P0 分 job，但进主分支前建议绿灯。

| ID | 测什么 | 验证什么 | 为什么是 P1 |
|----|--------|----------|-------------|
| I-P1-01 | **Provider 禁用 / health=DOWN 拒绝对话** | 禁用或标 DOWN 后 chat/stream 失败，业务码为 Forbidden/LLM_UNAVAILABLE 类；不落「假成功」助手 completed | 凭证门禁；避免打坏密钥与无效外呼 |
| I-P1-02 | **Agent 禁用拒绝对话** | `is_enabled=false` 后对该 Agent 会话 chat → 明确错误 | 编排前置条件 |
| I-P1-03 | **会话 CRUD + 消息游标分页** | 创建/列表/详情/删除；messages 游标翻页 `next_cursor` 行为正确；删会话后消息不可再读 | 对话配套主功能；分页契约 |
| I-P1-04 | **MCP CRUD + 连通性 test** | 创建 → `POST .../test` → `status=UP`（mock list_tools）→ 详情含 tools；删除前若 Agent 绑定则 CONFLICT | 链路 E 管理面 |
| I-P1-05 | **绑定工具不可用时的可观测降级** | Agent 绑了 MCP 但 list_tools 全失败：对话不得「静默当无工具成功」——须错误码或 meta/日志可断言的 degrade 信号 | 风险「静默失败」 |
| I-P1-06 | **知识库上传 → 状态机（mock worker/pipeline）** | 上传返回 pending/processing；触发处理（同步调 pipeline 或测队列投递）后文档 `ready` 或 `failed` 可查 | 链路 D；`CLAUDE.md` 异步入库 |
| I-P1-07 | **retrieve 跨模块调用面** | 有 ready 数据（或 mock Milvus+chunks）时 `retrieve`/工作流 knowledge 节点返回命中；milvus 关闭时稳定空结果不 500 | 检索主功能；工作流依赖 |
| I-P1-08 | **工具执行失败回传对话** | MCP `call_tool` 抛错：对话仍结束为可解析回复（SSE done 或 chat 200），且不把未处理 500 甩给客户端 | tool_loop 集成行为 |
| I-P1-09 | **ApiResult 信封一致性（抽样）** | 任意 P0/P1 失败用例：`data is null`；校验失败（非法 body）也走统一信封 | `CLAUDE.md` §1.6 强制 |

---

### 11.3 P2 — 边缘场景，有余力再做

不阻塞发版；用于加固与压测前排查。

| ID | 测什么 | 验证什么 | 为什么是 P2 |
|----|--------|----------|-------------|
| I-P2-01 | **同会话并发双 chat/stream** | 第二次被拒绝/排队，或结果可证明不交错（以产品策略为准） | 并发风险真实但策略未定时易 flake |
| I-P2-02 | **客户端中断 SSE** | 取消后助手 `cancelled`（或约定状态）；Gateway 限流名额可再次获取（不泄漏） | 长连接资源；需精细取消模拟 |
| I-P2-03 | **超长用户输入边界** | 达/超 `CONTENT_MAX_LENGTH` 的校验错误信封；近上限时请求可完成或明确失败 | 边界条件；成本高 |
| I-P2-04 | **stdio MCP 禁用或拒绝（若生产策略禁止）** | 创建/调用 stdio transport 被拒 | 安全加固；视部署策略 |
| I-P2-05 | **真实（或 testcontainers）Milvus 入库+检索一条** | upsert 后 retrieve 命中正文与 score；删文档后不可检索 | 需重依赖；单测已 mock 时降为环境测 |
| I-P2-06 | **Worker 真消费 Redis 队列一条** | 上传后仅入队，worker 进程处理后文档 ready | 多进程；适合独立 nightly |
| I-P2-07 | **简版工作流 run：start→llm→end** | run 状态 succeeded；输出变量可读（fake LLM） | 非对话主路径；有余力对齐 CLAUDE 工作流 |
| I-P2-08 | **工作流 knowledge/tool 节点各 1 条** | 节点读检索/调工具结果写入 pool | 组合爆炸，保持最小集 |
| I-P2-09 | **多 MCP Server 绑定串行 list_tools 超时/部分失败** | 部分失败时的产品契约（报错或 degrade）稳定 | 性能/韧性边缘 |
| I-P2-10 | **Gateway 限流打满** | 并发超限返回 LLM_UNAVAILABLE；不拖死进程 | 需压测级并发，非日常 |

---

### 11.4 优先级与核心链路对照

```text
链路 C 身份工作区     → I-P0-01, I-P0-02
链路 A/B 对话         → I-P0-04, I-P0-05, I-P0-06, I-P1-01~03, I-P1-08, I-P2-01~03
链路 E MCP            → I-P0-07, I-P0-08, I-P1-04~05, I-P2-04, I-P2-09
链路 D 知识           → I-P1-06~07, I-P2-05~06
工作流（扩展）        → I-P2-07~08
横切契约/韧性         → I-P1-09, I-P2-10
```

### 11.5 执行建议

1. **CI 门禁：** 仅 P0（fake LLM + mock MCP/Milvus）。  
2. **Nightly / 预发：** P0 + P1；P2 按环境能力选修。  
3. **禁止：** 用真实付费厂商 Key 跑 P0；P0 失败时用「跳过」充绿。  
4. **与单测关系：** P0 集成不过时，先查对应 §1/§8 单测是否缺场景，再查编排与 HTTP 层。

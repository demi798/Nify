---
name: provider-adapter
description: >
  Adds a new LLM provider adapter to Nify model_provider: analyze vendor API,
  implement Adapter (+ probe), register to LLMGateway, update constants/frontend,
  then verify stream and connectivity. Use when 加新供应商、新增 Adapter、
  provider-adapter、openai/claude 以外的厂商接入、或扩展 provider_type。
---

# Nify 新供应商 Adapter 接入流程

将「分析 API → 实现 Adapter → 注册 → 验证」固化为可重复流程。  
遵守 `CLAUDE.md`：Adapter **只做协议与 C\* 错误映射**；**禁止**在 Adapter 内重试/熔断/鉴权业务。

> **路径**：Claude/Cursor 可发现格式为 `.claude/skills/provider-adapter/SKILL.md`。  
> （勿仅放单文件 `provider-adapter.md`，否则可能无法作为 Skill 加载。）

---

## 0. 先核对：流程在本仓库 Python 里是否合理？

| 你描述的步骤 | 本仓库实际对应 | 结论 |
|--------------|----------------|------|
| 分析 API | 读厂商文档，定 base_url / 鉴权头 / 流式协议 / 错误码 | ✅ 合理，必须做 |
| 实现 Adapter | `adapters/<name>.py`，实现 `LLMAdapter`：`provider` + `stream_chat` | ✅ 合理 |
| 注册到 Factory | **没有独立 Factory 类**；是 `LLMGateway.register_adapter` + `register_default_adapters()` | ⚠️ 表述应改为「注册到 Gateway」 |
| 验证 | compile + 连通测试 +（可选）stream 冒烟 | ✅ 合理 |

**推荐固定流程（已按代码校正）**：

1. 分析 API（含是否可复用 OpenAI 兼容协议）  
2. 实现 Adapter（+ 连通性 `_probe` 分支，如需要）  
3. 注册到 **LLMGateway**（`register_default_adapters`）并补齐 **constants / schemas / 前端选项**  
4. 验证（编译 → 创建 Provider → `test-connection` → 必要时 stream）

**决策点（等待用户确认）**：

- 新厂商能否走 OpenAI Compatible（`openai_compatible` 或复用 `openai_compat.py`）？能则优先扩展兼容，而不是新协议。
- `provider_type` 字符串命名（小写+下划线，如 `azure_openai`）。

---

## Step 1 — 分析 API

### 做什么

对照现有实现分类：

| 类型 | 代表 | 复用 |
|------|------|------|
| OpenAI Chat Completions 兼容 | openai / gemini(openai态) / ollama / openai_compatible | `internal/openai_compat.py` |
| Anthropic Messages | claude | `adapters/claude.py` 模式 |
| 全新协议 | 无 | 新建 Adapter，仍只映射到 `StreamDelta` / `AppError(C*)` |

记录清楚：

- 默认 Base URL、是否允许自定义
- 鉴权：`Authorization: Bearer` / `x-api-key` / query（**禁止**把 key 放 URL 日志）
- 流式：SSE 事件形态、结束标记
- 连通性最小请求（chat completions max_tokens=1 或等价）
- 错误：401/403→`C0005`，429→`C0002`，5xx/超时→`C0001`/`C0003` 等

### 产出物

- 一页分析笔记：协议类型、鉴权、probe 方式、默认 model 示例。

### 验证

- 用户确认「走兼容协议」或「新协议 Adapter」。

### 注意事项

- 兼容协议厂商仍可能 **模型 id 完全不同**；默认模型不要抄 `gpt-4o-mini`。
- 分析阶段不要改代码。

---

## Step 2 — 实现 Adapter

### 做什么

1. 新增 `backend/app/modules/model_provider/adapters/<name>.py`  
2. 实现协议（与 `OpenAIAdapter` / `ClaudeAdapter` 同级）：

```python
class XxxAdapter:
    provider = "xxx"  # 必须与 provider_type 一致（小写）

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[StreamDelta]:
        ...
```

3. **连通性探测**：`service._probe` 目前对非 `claude` 走 `probe_chat_completions`。  
   - 若新厂商也是 Chat Completions 兼容 → 通常 **不必改 _probe**（靠 `provider_type` 传给 httpx 客户端键）。  
   - 若为 Claude 类或全新协议 → 在 `_probe` 增加分支，或抽 `probe_xxx()`，**等待用户确认**后再改探测逻辑。

4. 错误映射：只抛 `AppError` + `ErrorCode`（C\*）；不重试。

### 产出物

- `adapters/<name>.py`（及必要的 `probe_*` 辅助函数）。

### 验证

```bash
cd backend && python -m compileall -q app/modules/model_provider/adapters
```

### 注意事项

- Adapter **禁止** `import` 业务 service / 查库 / 做权限。
- 持有 DB 事务或 Lock 时禁止调 Gateway（CLAUDE.md）；Adapter 本身也不要碰 DB。
- 可复用 `openai_compat.stream_chat_completions` / `auth_headers_for_bearer` 就复用，避免复制粘贴。

---

## Step 3 — 注册到 LLMGateway（不是 Factory）

### 做什么

1. **Gateway 注册**  
   在 `adapters/__init__.py` 的 `register_default_adapters()` 中实例化并：

   ```python
   gw.register_adapter(XxxAdapter())
   ```

   启动路径：`main.py` lifespan → `register_default_adapters()`。

2. **类型白名单与默认值**（缺一会无法创建 Provider）  
   更新 `constants.py`：
   - `PROVIDER_TYPES`
   - `DEFAULT_BASE_URLS`
   - `DEFAULT_AUTH_SCHEMES`
   - `DEFAULT_MODELS`

3. **Schema / 前端**  
   - `schemas.py` 中 `ProviderTypeLiteral`（若有）  
   - 前端 `MODEL_PROVIDER_TYPE_OPTIONS` / `LABEL`  
   - 特殊必填（如兼容类型强制 Base URL + default_model_key）在 service 校验中补齐

4. 导出：`adapters/__init__.py` 的 `__all__`（可选但建议）

### 产出物

- 注册代码 + constants + 前端选项 +（如需）校验逻辑。

### 验证

```bash
cd backend && python -c "
from app.modules.model_provider.adapters import register_default_adapters
from app.modules.model_provider.internal.gateway import get_llm_gateway
register_default_adapters()
gw = get_llm_gateway()
assert gw._get_adapter('xxx') is not None
print('registered ok')
"
```

### 注意事项

- **不要**引入新的 Factory 抽象，除非用户明确要求重构；当前扩展点就是 `register_adapter`。
- `provider` 字符串必须与库内 `provider_type`、前端 value **完全一致**。
- 只改 Adapter 不改 `PROVIDER_TYPES` → 创建接口会校验失败。

**决策点（等待用户确认）**：是否同时改 SQL 注释枚举文案；一般不必迁库（`provider_type` 已是 VARCHAR）。

---

## Step 4 — 验证

### 门禁顺序（失败则停下）

1. `compileall` / 导入注册断言  
2. 重启或热重载 API 进程  
3. 登录 + `X-Workspace-Id`  
4. `POST /api/v1/model-providers` 创建该 `provider_type`  
5. `POST /api/v1/model-providers/{id}/test-connection`  
6. （可选）经 `get_runtime_credentials` + `LLMGateway.stream_chat` 冒烟

### 产出物

- curl 响应摘录：`code`、`health.status`、`latency_ms` 或错误码。

### 验证通过标准

- 创建成功；连通测试在正确 Key+模型下为 `UP`（或预期的鉴权/模型错误码，而非未注册 Adapter）。
- Gateway `_get_adapter(provider_type)` 不再报「未注册的模型提供商」。

### 注意事项（踩坑）

- curl 路径里的 id 必须是真实 UUID。  
- `model_not_found` → 改 `default_model_key`，不是改 Adapter 注册。  
- `C0005`/403 → Key/权限。  
- 热重载后确认 lifespan 再次执行了 `register_default_adapters`。  
- 多 worker 时每个进程各自注册；不要依赖「只在一个进程注册过」。

---

## 代理执行清单

```text
Provider Adapter Progress:
- [ ] Step 1 API 分析（等待用户确认：兼容 vs 新协议）
- [ ] Step 2 Adapter (+ probe 分支若需要) compile 通过
- [ ] Step 3 Gateway 注册 + constants + 前端选项
- [ ] Step 4 创建 Provider + test-connection 验证通过
```

---

## 与相关文件速查

| 文件 | 作用 |
|------|------|
| `adapters/base.py` | `LLMAdapter` / `ChatRequest` / `StreamDelta` |
| `adapters/<name>.py` | 厂商实现 |
| `adapters/__init__.py` | `register_default_adapters` |
| `internal/gateway.py` | `register_adapter` / `stream_chat` |
| `internal/openai_compat.py` | 兼容协议流式 + probe |
| `constants.py` | 类型白名单与默认值 |
| `service.py` `_probe` | 连通性探测分支 |
| 前端 `types.ts` | 下拉选项 |

---

## 与 module-delivery Skill 的关系

- `module-delivery`：整模块从设计到前后端验收。  
- `provider-adapter`：模块已存在时，**只扩展一个新 `provider_type`**。  
- 若同时「新模块 + 新厂商」，先 module-delivery，再在本 Skill 加厂商。

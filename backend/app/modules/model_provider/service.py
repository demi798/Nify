"""model_provider 用例：Provider / Model CRUD、健康探测、供 Gateway 取凭证。"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import new_uuid, utc_now
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.pagination import (
    CursorPage,
    CursorParams,
    build_cursor_page,
    decode_cursor,
)
from app.core.rules import (
    reject_if,
    require_in,
    require_non_blank,
    require_true,
    require_uuid,
    require_workspace_match,
)
from app.modules.model_provider.adapters.claude import probe_claude
from app.modules.model_provider.constants import (
    ANTHROPIC_VERSION,
    AUTH_SCHEMES,
    DEFAULT_AUTH_SCHEMES,
    DEFAULT_BASE_URLS,
    DEFAULT_MODELS,
    HEALTH_FAIL_THRESHOLD,
    HEALTH_STATUS_DEGRADED,
    HEALTH_STATUS_DOWN,
    HEALTH_STATUS_UNKNOWN,
    HEALTH_STATUS_UP,
    HEALTH_STATUSES,
    MODALITIES,
    MODEL_STATUSES,
    PROVIDER_TYPES,
)
from app.modules.model_provider.internal.credentials import (
    credentials_has_api_key,
    get_api_key,
    pack_credentials,
)
from app.modules.model_provider.internal.runtime_cache import (
    get_cached_runtime,
    invalidate_provider_runtime,
    put_cached_runtime,
)
from app.modules.model_provider.internal.openai_compat import (
    auth_headers_for_bearer,
    probe_chat_completions,
)
from app.modules.model_provider.models import Provider, ProviderModel
from app.modules.model_provider.schemas import (
    EnabledModelBinding,
    ModelConfigOut,
    ProviderCreate,
    ProviderHealthInfo,
    ProviderHealthOut,
    ProviderModelCreate,
    ProviderModelOut,
    ProviderModelUpdate,
    ProviderOut,
    ProviderUpdate,
)


class ModelProviderService:
    """模型提供商与模型目录服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------- Provider CRUD ----------

    async def list_providers_page(
        self, *, workspace_id: str, params: CursorParams
    ) -> CursorPage[ProviderOut]:
        """工作区 Provider 游标分页列表（倒序 created_at,id）。"""
        limit = params.limit
        stmt = select(Provider).where(Provider.workspace_id == workspace_id)
        if params.cursor:
            cursor_at, cursor_id = decode_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    Provider.created_at < cursor_at,
                    and_(
                        Provider.created_at == cursor_at,
                        Provider.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(Provider.created_at.desc(), Provider.id.desc()).limit(
            limit + 1
        )
        rows = list((await self._session.scalars(stmt)).all())
        models_map = await self._load_models_map(
            workspace_id, [p.id for p in rows]
        )
        items = [
            self._to_provider_out(p, models=models_map.get(p.id)) for p in rows
        ]
        return build_cursor_page(
            items,
            limit,
            created_at_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    async def list_providers(self, *, workspace_id: str) -> list[ProviderOut]:
        """不分页全量列表（内部/兼容用）。"""
        page = await self.list_providers_page(
            workspace_id=workspace_id,
            params=CursorParams(cursor=None, limit=100),
        )
        return page.items

    async def get_provider(
        self,
        *,
        workspace_id: str,
        provider_id: str,
        include_models: bool = True,
    ) -> ProviderOut:
        """详情：含 modelConfig（可带 models）与 health。"""
        provider = await self._get_provider_entity(workspace_id, provider_id)
        models: list[ProviderModelOut] | None = None
        if include_models:
            models = await self.list_models(
                workspace_id=workspace_id, provider_id=provider_id
            )
        return self._to_provider_out(provider, models=models)

    async def create_provider(
        self,
        *,
        workspace_id: str,
        user_id: str,
        body: ProviderCreate,
    ) -> ProviderOut:
        provider_type = require_in(
            body.provider_type.strip().lower(), PROVIDER_TYPES, field="provider_type"
        )
        name = require_non_blank(body.name, field="name")
        auth_scheme = (body.auth_scheme or DEFAULT_AUTH_SCHEMES[provider_type]).strip()
        require_in(auth_scheme, AUTH_SCHEMES, field="auth_scheme")
        self._validate_auth(provider_type, auth_scheme, body.api_key)

        base_url = (body.base_url.strip() if body.base_url else None) or None
        # OpenAI 兼容类型必须自定义 Base URL 与模型名
        if provider_type == "openai_compatible":
            require_true(
                bool(base_url),
                code=ErrorCode.BAD_REQUEST,
                message="OpenAI 兼容类型必须填写 Base URL",
            )
            require_true(
                bool(body.default_model_key and body.default_model_key.strip()),
                code=ErrorCode.BAD_REQUEST,
                message="OpenAI 兼容类型必须填写默认模型（上游真实 model id）",
            )

        default_key = (
            body.default_model_key.strip()
            if body.default_model_key and body.default_model_key.strip()
            else None
        )
        if not default_key:
            default_key = DEFAULT_MODELS[provider_type][0]

        provider = Provider(
            id=new_uuid(),
            workspace_id=workspace_id,
            name=name,
            provider_type=provider_type,
            base_url=base_url,
            auth_scheme=auth_scheme,
            credentials_encrypted=pack_credentials(api_key=body.api_key),
            auth_extra=body.auth_extra,
            default_model_key=default_key,
            config=body.config,
            is_enabled=body.is_enabled,
            health_status=HEALTH_STATUS_UNKNOWN,
            health_fail_count=0,
            created_by=user_id,
        )
        self._session.add(provider)
        await self._session.flush()

        seed_models = body.models
        if seed_models:
            for item in seed_models:
                await self._insert_model(
                    workspace_id=workspace_id,
                    provider=provider,
                    body=item,
                )
        else:
            preset_key, preset_display = DEFAULT_MODELS[provider_type]
            key = default_key
            display = (
                key if key != preset_key else preset_display
            )
            await self._insert_model(
                workspace_id=workspace_id,
                provider=provider,
                body=ProviderModelCreate(
                    model_key=key,
                    display_name=display,
                    is_default=True,
                ),
            )
            provider.default_model_key = key

        await self._session.flush()
        return await self.get_provider(
            workspace_id=workspace_id, provider_id=provider.id
        )

    async def update_provider(
        self,
        *,
        workspace_id: str,
        provider_id: str,
        body: ProviderUpdate,
    ) -> ProviderOut:
        provider = await self._get_provider_entity(workspace_id, provider_id)
        changes = body.changed_fields()

        if "name" in changes and changes["name"] is not None:
            provider.name = require_non_blank(changes["name"], field="name")
        if "base_url" in changes:
            raw = changes["base_url"]
            next_url = (
                raw.strip() if isinstance(raw, str) and raw.strip() else None
            )
            if provider.provider_type == "openai_compatible":
                require_true(
                    bool(next_url),
                    code=ErrorCode.BAD_REQUEST,
                    message="OpenAI 兼容类型必须填写 Base URL",
                )
            provider.base_url = next_url
        if "auth_scheme" in changes and changes["auth_scheme"] is not None:
            scheme = require_in(
                str(changes["auth_scheme"]).strip(), AUTH_SCHEMES, field="auth_scheme"
            )
            provider.auth_scheme = scheme
        runtime_dirty = False
        if "base_url" in changes or "auth_scheme" in changes or "auth_extra" in changes:
            runtime_dirty = True
        if "api_key" in changes:
            api_key = changes["api_key"]
            # 显式传空串：仅 ollama/none 允许清空
            if api_key is None or (isinstance(api_key, str) and not api_key.strip()):
                require_true(
                    provider.auth_scheme == "none"
                    or provider.provider_type == "ollama",
                    code=ErrorCode.BAD_REQUEST,
                    message="该供应商不允许清空 API Key",
                )
                provider.credentials_encrypted = pack_credentials(api_key=None)
            else:
                provider.credentials_encrypted = pack_credentials(api_key=str(api_key))
            provider.health_status = HEALTH_STATUS_UNKNOWN
            provider.health_checked_at = None
            provider.health_fail_count = 0
            provider.health_message = "凭证已更新，待重新探测"
            runtime_dirty = True
        if "auth_extra" in changes:
            provider.auth_extra = changes["auth_extra"]
        if "default_model_key" in changes and changes["default_model_key"]:
            key = require_non_blank(
                changes["default_model_key"], field="default_model_key"
            )
            await self._upsert_default_model_key(
                workspace_id=workspace_id, provider=provider, model_key=key
            )
            runtime_dirty = True
        if "config" in changes:
            provider.config = changes["config"]
            runtime_dirty = True
        if "is_enabled" in changes and changes["is_enabled"] is not None:
            provider.is_enabled = bool(changes["is_enabled"])
            runtime_dirty = True

        await self._session.flush()
        # 写路径主动失效，避免对话服务继续命中旧 Key / 旧路由
        if runtime_dirty:
            invalidate_provider_runtime(provider.id)
        return await self.get_provider(
            workspace_id=workspace_id, provider_id=provider.id
        )

    async def delete_provider(self, *, workspace_id: str, provider_id: str) -> None:
        provider = await self._get_provider_entity(workspace_id, provider_id)
        models = (
            await self._session.scalars(
                select(ProviderModel).where(
                    ProviderModel.workspace_id == workspace_id,
                    ProviderModel.provider_id == provider_id,
                )
            )
        ).all()
        for m in models:
            await self._session.delete(m)
        await self._session.delete(provider)
        await self._session.flush()
        invalidate_provider_runtime(provider_id)

    # ---------- Model CRUD ----------

    async def list_models(
        self, *, workspace_id: str, provider_id: str
    ) -> list[ProviderModelOut]:
        await self._get_provider_entity(workspace_id, provider_id)
        stmt = (
            select(ProviderModel)
            .where(
                ProviderModel.workspace_id == workspace_id,
                ProviderModel.provider_id == provider_id,
            )
            .order_by(ProviderModel.created_at.asc(), ProviderModel.id.asc())
        )
        rows = (await self._session.scalars(stmt)).all()
        return [self._to_model_out(m) for m in rows]

    async def create_model(
        self,
        *,
        workspace_id: str,
        provider_id: str,
        body: ProviderModelCreate,
    ) -> ProviderModelOut:
        provider = await self._get_provider_entity(workspace_id, provider_id)
        model = await self._insert_model(
            workspace_id=workspace_id, provider=provider, body=body
        )
        await self._session.flush()
        return self._to_model_out(model)

    async def update_model(
        self,
        *,
        workspace_id: str,
        provider_id: str,
        model_id: str,
        body: ProviderModelUpdate,
    ) -> ProviderModelOut:
        provider = await self._get_provider_entity(workspace_id, provider_id)
        model = await self._get_model_entity(workspace_id, provider_id, model_id)
        changes = body.changed_fields()

        if "display_name" in changes and changes["display_name"] is not None:
            model.display_name = require_non_blank(
                changes["display_name"], field="display_name"
            )
        if "modality" in changes and changes["modality"] is not None:
            model.modality = require_in(
                changes["modality"], MODALITIES, field="modality"
            )
        if "context_window" in changes:
            model.context_window = changes["context_window"]
        if "max_output_tokens" in changes:
            model.max_output_tokens = changes["max_output_tokens"]
        if "capabilities" in changes:
            model.capabilities = changes["capabilities"]
        if "is_enabled" in changes and changes["is_enabled"] is not None:
            model.is_enabled = bool(changes["is_enabled"])
        if "status" in changes and changes["status"] is not None:
            model.status = require_in(
                changes["status"], MODEL_STATUSES, field="status"
            )
        if "is_default" in changes and changes["is_default"]:
            await self._set_default_model(
                workspace_id=workspace_id,
                provider=provider,
                model_key=model.model_key,
            )

        await self._session.flush()
        return self._to_model_out(model)

    async def delete_model(
        self, *, workspace_id: str, provider_id: str, model_id: str
    ) -> None:
        provider = await self._get_provider_entity(workspace_id, provider_id)
        model = await self._get_model_entity(workspace_id, provider_id, model_id)
        was_default = model.is_default
        await self._session.delete(model)
        await self._session.flush()
        if was_default:
            remaining = (
                await self._session.scalars(
                    select(ProviderModel)
                    .where(
                        ProviderModel.workspace_id == workspace_id,
                        ProviderModel.provider_id == provider_id,
                    )
                    .order_by(ProviderModel.created_at.asc())
                    .limit(1)
                )
            ).first()
            if remaining is not None:
                remaining.is_default = True
                provider.default_model_key = remaining.model_key
            else:
                provider.default_model_key = None
            await self._session.flush()

    # ---------- Health / 连通性 ----------

    async def check_health(
        self, *, workspace_id: str, provider_id: str
    ) -> ProviderHealthOut:
        """手动连通性测试（工作区作用域）。"""
        provider = await self._get_provider_entity(workspace_id, provider_id)
        return await self.test_connectivity(provider)

    async def test_connectivity(self, provider: Provider) -> ProviderHealthOut:
        """连通性测试并写回 provider 健康字段。

        成功：status=UP、latency_ms、last_success_at、fail_count=0。
        失败：fail_count+1；连续失败达阈值则 status=DOWN。
        """
        model_key = provider.default_model_key
        if not model_key:
            raise AppError(ErrorCode.BAD_REQUEST, "请先配置默认模型后再探测")

        base_url = self.resolve_base_url(provider)
        api_key = get_api_key(provider.credentials_encrypted)
        started = time.perf_counter()
        now = utc_now()
        threshold = max(
            1, int(settings.provider_health_fail_threshold or HEALTH_FAIL_THRESHOLD)
        )

        try:
            await self._probe(
                provider, base_url=base_url, api_key=api_key, model=model_key
            )
            latency = int((time.perf_counter() - started) * 1000)
            provider.health_status = HEALTH_STATUS_UP
            provider.health_checked_at = now
            provider.health_latency_ms = latency
            provider.health_error_code = None
            provider.health_message = "连通正常"
            provider.health_fail_count = 0
            provider.health_last_success_at = now
        except AppError as exc:
            latency = int((time.perf_counter() - started) * 1000)
            fail_count = int(provider.health_fail_count or 0) + 1
            provider.health_fail_count = fail_count
            provider.health_checked_at = now
            provider.health_latency_ms = latency
            provider.health_error_code = exc.code
            provider.health_message = (exc.message or "连通失败")[:512]
            if fail_count >= threshold:
                provider.health_status = HEALTH_STATUS_DOWN
            else:
                # 未达阈值：标记降级，便于前端黄标展示
                provider.health_status = HEALTH_STATUS_DEGRADED

        require_in(provider.health_status, HEALTH_STATUSES, field="health_status")
        await self._session.flush()
        # 健康态变更影响新请求准入；不取消进行中的 stream，但使运行时缓存失效
        invalidate_provider_runtime(provider.id)
        return self._to_health_out(provider)

    async def run_enabled_health_checks(self) -> dict[str, int]:
        """巡检全部 is_enabled 的 Provider（跨工作区，供定时任务调用）。"""
        stmt = (
            select(Provider)
            .where(Provider.is_enabled.is_(True))
            .order_by(Provider.created_at.asc(), Provider.id.asc())
        )
        rows = list((await self._session.scalars(stmt)).all())
        ok = 0
        fail = 0
        skip = 0
        for provider in rows:
            if not provider.default_model_key:
                skip += 1
                continue
            try:
                result = await self.test_connectivity(provider)
                if result.health.status == HEALTH_STATUS_UP:
                    ok += 1
                else:
                    fail += 1
            except AppError:
                fail += 1
            except Exception:
                fail += 1
        return {"total": len(rows), "ok": ok, "fail": fail, "skip": skip}

    # ---------- 供他模块 / Gateway ----------

    async def get_enabled_model_binding(
        self, *, workspace_id: str, model_id: str
    ) -> EnabledModelBinding:
        """跨模块公开接口：按模型目录 UUID 校验可用并返回绑定信息。

        校验：模型属于本工作区、已启用、状态 available；
        所属 Provider 已启用且健康态非 DOWN。
        禁止他模块直接查 ``ProviderModel`` / ``Provider`` 表。
        """
        model_id = require_uuid(model_id, field="model_config_id")
        model = await self._session.get(ProviderModel, model_id)
        if model is None:
            raise AppError(ErrorCode.NOT_FOUND, "模型配置不存在")
        require_workspace_match(model.workspace_id, workspace_id, message="模型不属于当前工作区")
        require_true(
            model.is_enabled,
            code=ErrorCode.BAD_REQUEST,
            message="模型已禁用，无法绑定",
        )
        require_true(
            model.status == "available",
            code=ErrorCode.BAD_REQUEST,
            message=f"模型状态不可用（{model.status}）",
        )

        provider = await self._get_provider_entity(workspace_id, model.provider_id)
        require_true(
            provider.is_enabled,
            code=ErrorCode.FORBIDDEN,
            message="提供商已禁用，无法绑定",
        )
        if provider.health_status == HEALTH_STATUS_DOWN:
            raise AppError(
                ErrorCode.LLM_UNAVAILABLE,
                "提供商健康检查为 DOWN，暂不可绑定该模型",
            )

        return EnabledModelBinding(
            model_id=model.id,
            provider_id=provider.id,
            model_key=model.model_key,
            display_name=model.display_name,
            provider_name=provider.name,
            provider_type=provider.provider_type,
            is_enabled=model.is_enabled,
            health_status=provider.health_status or HEALTH_STATUS_UNKNOWN,
        )

    async def get_runtime_credentials(
        self, *, workspace_id: str, provider_id: str
    ) -> dict[str, Any]:
        """返回调用所需原生参数（含明文 api_key，仅内存短用）。

        约定（新请求入口）：
        - ``is_enabled=false`` / ``health=DOWN`` → 拒绝发起新调用
        - 进行中的 LLMGateway stream **不**因健康巡检被取消
        - 短缓存带 ``updated_at`` 版本；写路径会 ``invalidate_provider_runtime``
        """
        provider = await self._get_provider_entity(workspace_id, provider_id)
        require_true(
            provider.is_enabled,
            code=ErrorCode.FORBIDDEN,
            message="提供商已禁用",
        )
        # 仅拦截新请求；不取消已在飞的对话流
        if provider.health_status == HEALTH_STATUS_DOWN:
            raise AppError(
                ErrorCode.LLM_UNAVAILABLE,
                "提供商健康检查为 DOWN，暂不可发起新对话",
            )

        rev = (
            provider.updated_at.isoformat(timespec="milliseconds")
            if provider.updated_at
            else ""
        )
        cached = get_cached_runtime(provider.id)
        if cached is not None and cached.get("_rev") == rev:
            return {k: v for k, v in cached.items() if k != "_rev"}

        payload: dict[str, Any] = {
            "provider_id": provider.id,
            "provider_type": provider.provider_type,
            "base_url": self.resolve_base_url(provider),
            "auth_scheme": provider.auth_scheme,
            "api_key": get_api_key(provider.credentials_encrypted),
            "auth_extra": provider.auth_extra or {},
            "default_model_key": provider.default_model_key,
            "config": provider.config or {},
        }
        put_cached_runtime(provider.id, {**payload, "_rev": rev})
        return payload

    async def get_embedding_runtime(
        self, *, workspace_id: str
    ) -> dict[str, Any]:
        """供 knowledge 管线取 Embedding 参数（复用 Provider 凭证，禁止硬编码 Key）。

        解析顺序：
        1. ``NIFY_EMBEDDING_PROVIDER_ID``（若配置）
        2. 工作区内 ``modality=embedding`` 且启用的模型
        3. 启用中的 openai / openai_compatible / fake + ``NIFY_EMBEDDING_MODEL_KEY``
        """
        fixed_pid = (settings.embedding_provider_id or "").strip() or None
        if fixed_pid:
            provider = await self._get_provider_entity(workspace_id, fixed_pid)
            model_key = await self._resolve_embedding_model_key(
                workspace_id=workspace_id, provider_id=provider.id
            )
            creds = await self.get_runtime_credentials(
                workspace_id=workspace_id, provider_id=provider.id
            )
            return {
                "provider_id": provider.id,
                "provider_type": str(creds["provider_type"]),
                "model": model_key,
                "api_key": str(creds.get("api_key") or ""),
                "base_url": creds.get("base_url"),
            }

        # 优先专用 embedding 模型目录
        stmt = (
            select(ProviderModel, Provider)
            .join(Provider, Provider.id == ProviderModel.provider_id)
            .where(
                ProviderModel.workspace_id == workspace_id,
                ProviderModel.modality == "embedding",
                ProviderModel.is_enabled.is_(True),
                Provider.is_enabled.is_(True),
            )
            .order_by(
                ProviderModel.is_default.desc(),
                ProviderModel.created_at.asc(),
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).first()
        if row is not None:
            model, provider = row
            if provider.health_status == HEALTH_STATUS_DOWN:
                raise AppError(
                    ErrorCode.LLM_UNAVAILABLE,
                    "Embedding 提供商健康检查为 DOWN",
                )
            creds = await self.get_runtime_credentials(
                workspace_id=workspace_id, provider_id=provider.id
            )
            return {
                "provider_id": provider.id,
                "provider_type": str(creds["provider_type"]),
                "model": model.model_key,
                "api_key": str(creds.get("api_key") or ""),
                "base_url": creds.get("base_url"),
            }

        # 回退：兼容聊天 Provider + 全局 embedding model_key
        providers = list(
            (
                await self._session.scalars(
                    select(Provider)
                    .where(
                        Provider.workspace_id == workspace_id,
                        Provider.is_enabled.is_(True),
                        Provider.provider_type.in_(
                            ("fake", "openai", "openai_compatible")
                        ),
                    )
                    .order_by(Provider.created_at.asc())
                )
            ).all()
        )
        providers = [
            p for p in providers if p.health_status != HEALTH_STATUS_DOWN
        ]
        reject_if(
            not providers,
            code=ErrorCode.BAD_REQUEST,
            message="无可用 Embedding 提供商，请先配置 openai_compatible / fake Provider",
        )
        provider = providers[0]
        model_key = require_non_blank(
            settings.embedding_model_key, field="embedding_model_key"
        )
        creds = await self.get_runtime_credentials(
            workspace_id=workspace_id, provider_id=provider.id
        )
        return {
            "provider_id": provider.id,
            "provider_type": str(creds["provider_type"]),
            "model": model_key,
            "api_key": str(creds.get("api_key") or ""),
            "base_url": creds.get("base_url"),
        }

    async def _resolve_embedding_model_key(
        self, *, workspace_id: str, provider_id: str
    ) -> str:
        """固定 Provider 下选 embedding 模型 key。"""
        emb = await self._session.scalar(
            select(ProviderModel.model_key)
            .where(
                ProviderModel.workspace_id == workspace_id,
                ProviderModel.provider_id == provider_id,
                ProviderModel.modality == "embedding",
                ProviderModel.is_enabled.is_(True),
            )
            .order_by(ProviderModel.is_default.desc())
            .limit(1)
        )
        if emb:
            return str(emb)
        return require_non_blank(
            settings.embedding_model_key, field="embedding_model_key"
        )

    @staticmethod
    def resolve_base_url(provider: Provider) -> str:
        if provider.base_url and provider.base_url.strip():
            return provider.base_url.strip().rstrip("/")
        default = DEFAULT_BASE_URLS.get(provider.provider_type) or ""
        if not default:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                "请先配置 Base URL",
            )
        return default.rstrip("/")

    # ---------- 内部 ----------

    async def _probe(
        self,
        provider: Provider,
        *,
        base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        ptype = provider.provider_type
        if ptype == "claude":
            version = str(
                (provider.auth_extra or {}).get("anthropic_version") or ANTHROPIC_VERSION
            )
            await probe_claude(
                base_url=base_url,
                api_key=api_key,
                model=model,
                anthropic_version=version,
            )
            return
        headers = auth_headers_for_bearer(api_key if api_key else "ollama")
        await probe_chat_completions(
            provider=ptype,
            base_url=base_url,
            headers=headers,
            model=model,
        )

    async def _insert_model(
        self,
        *,
        workspace_id: str,
        provider: Provider,
        body: ProviderModelCreate,
    ) -> ProviderModel:
        key = require_non_blank(body.model_key, field="model_key")
        display = require_non_blank(body.display_name, field="display_name")
        modality = require_in(body.modality, MODALITIES, field="modality")
        status = require_in(body.status, MODEL_STATUSES, field="status")

        exists = await self._session.scalar(
            select(ProviderModel.id).where(
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_key == key,
            )
        )
        reject_if(exists is not None, code=ErrorCode.CONFLICT, message="模型 key 已存在")

        is_default = bool(body.is_default)
        if is_default:
            await self._clear_defaults(workspace_id, provider.id)

        model = ProviderModel(
            id=new_uuid(),
            workspace_id=workspace_id,
            provider_id=provider.id,
            model_key=key,
            display_name=display,
            modality=modality,
            context_window=body.context_window,
            max_output_tokens=body.max_output_tokens,
            capabilities=body.capabilities,
            is_default=is_default,
            is_enabled=body.is_enabled,
            status=status,
        )
        self._session.add(model)
        if is_default:
            provider.default_model_key = key
        return model

    async def _set_default_model(
        self, *, workspace_id: str, provider: Provider, model_key: str
    ) -> None:
        model = await self._session.scalar(
            select(ProviderModel).where(
                ProviderModel.workspace_id == workspace_id,
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_key == model_key,
            )
        )
        if model is None:
            raise AppError(ErrorCode.NOT_FOUND, "默认模型不存在于该提供商目录")
        await self._clear_defaults(workspace_id, provider.id)
        model.is_default = True
        provider.default_model_key = model_key

    async def _upsert_default_model_key(
        self,
        *,
        workspace_id: str,
        provider: Provider,
        model_key: str,
    ) -> None:
        """更新默认模型 key：目录已有则切换；否则改写当前默认项或新建。"""
        existing = await self._session.scalar(
            select(ProviderModel).where(
                ProviderModel.workspace_id == workspace_id,
                ProviderModel.provider_id == provider.id,
                ProviderModel.model_key == model_key,
            )
        )
        if existing is not None:
            await self._set_default_model(
                workspace_id=workspace_id, provider=provider, model_key=model_key
            )
            return

        current_default = await self._session.scalar(
            select(ProviderModel).where(
                ProviderModel.workspace_id == workspace_id,
                ProviderModel.provider_id == provider.id,
                ProviderModel.is_default.is_(True),
            )
        )
        if current_default is not None:
            current_default.model_key = model_key
            current_default.display_name = model_key
            provider.default_model_key = model_key
            return

        await self._insert_model(
            workspace_id=workspace_id,
            provider=provider,
            body=ProviderModelCreate(
                model_key=model_key,
                display_name=model_key,
                is_default=True,
            ),
        )
        provider.default_model_key = model_key

    async def _clear_defaults(self, workspace_id: str, provider_id: str) -> None:
        rows = (
            await self._session.scalars(
                select(ProviderModel).where(
                    ProviderModel.workspace_id == workspace_id,
                    ProviderModel.provider_id == provider_id,
                    ProviderModel.is_default.is_(True),
                )
            )
        ).all()
        for row in rows:
            row.is_default = False

    async def _load_models_map(
        self, workspace_id: str, provider_ids: list[str]
    ) -> dict[str, list[ProviderModelOut]]:
        """按 provider_id 批量加载模型目录（供列表展开/计数）。"""
        if not provider_ids:
            return {}
        stmt = (
            select(ProviderModel)
            .where(
                ProviderModel.workspace_id == workspace_id,
                ProviderModel.provider_id.in_(provider_ids),
            )
            .order_by(
                ProviderModel.provider_id.asc(),
                ProviderModel.created_at.asc(),
                ProviderModel.id.asc(),
            )
        )
        rows = list((await self._session.scalars(stmt)).all())
        result: dict[str, list[ProviderModelOut]] = {
            pid: [] for pid in provider_ids
        }
        for model in rows:
            result.setdefault(model.provider_id, []).append(
                self._to_model_out(model)
            )
        return result

    async def _get_provider_entity(self, workspace_id: str, provider_id: str) -> Provider:
        provider = await self._session.get(Provider, provider_id)
        if provider is None:
            raise AppError(ErrorCode.NOT_FOUND, "提供商不存在")
        require_workspace_match(provider.workspace_id, workspace_id)
        return provider

    async def _get_model_entity(
        self, workspace_id: str, provider_id: str, model_id: str
    ) -> ProviderModel:
        model = await self._session.get(ProviderModel, model_id)
        if model is None or model.provider_id != provider_id:
            raise AppError(ErrorCode.NOT_FOUND, "模型不存在")
        require_workspace_match(model.workspace_id, workspace_id)
        return model

    @staticmethod
    def _validate_auth(provider_type: str, auth_scheme: str, api_key: str | None) -> None:
        if auth_scheme == "none" or provider_type == "ollama":
            return
        require_true(
            bool(api_key and api_key.strip()),
            code=ErrorCode.BAD_REQUEST,
            message="请填写 API Key",
        )

    def _to_provider_out(
        self,
        provider: Provider,
        *,
        models: list[ProviderModelOut] | None = None,
    ) -> ProviderOut:
        return ProviderOut(
            id=provider.id,
            workspace_id=provider.workspace_id,
            name=provider.name,
            provider_type=provider.provider_type,
            is_enabled=provider.is_enabled,
            modelConfig=self._to_model_config_out(provider, models=models),
            health=self._to_health_info(provider),
            created_by=provider.created_by,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    @staticmethod
    def _to_model_config_out(
        provider: Provider,
        *,
        models: list[ProviderModelOut] | None = None,
    ) -> ModelConfigOut:
        return ModelConfigOut(
            base_url=provider.base_url,
            auth_scheme=provider.auth_scheme,
            has_api_key=credentials_has_api_key(provider.credentials_encrypted),
            auth_extra=provider.auth_extra,
            default_model_key=provider.default_model_key,
            config=provider.config,
            models=models,
        )

    @staticmethod
    def _to_health_info(provider: Provider) -> ProviderHealthInfo:
        status = provider.health_status or HEALTH_STATUS_UNKNOWN
        if status not in HEALTH_STATUSES:
            status = HEALTH_STATUS_UNKNOWN
        return ProviderHealthInfo(
            status=status,  # type: ignore[arg-type]
            latency_ms=provider.health_latency_ms,
            last_success_at=provider.health_last_success_at,
            fail_count=int(provider.health_fail_count or 0),
            checked_at=provider.health_checked_at,
            error_code=provider.health_error_code,
            message=provider.health_message,
        )

    def _to_health_out(self, provider: Provider) -> ProviderHealthOut:
        return ProviderHealthOut(
            id=provider.id,
            health=self._to_health_info(provider),
        )

    @staticmethod
    def _to_model_out(model: ProviderModel) -> ProviderModelOut:
        return ProviderModelOut(
            id=model.id,
            workspace_id=model.workspace_id,
            provider_id=model.provider_id,
            model_key=model.model_key,
            display_name=model.display_name,
            modality=model.modality,
            context_window=model.context_window,
            max_output_tokens=model.max_output_tokens,
            capabilities=model.capabilities,
            is_default=model.is_default,
            is_enabled=model.is_enabled,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

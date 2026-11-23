"""mcp 用例：Server CRUD + 连通性测试 + Agent 绑定选项。

跨模块：删除前用原生 SQL 检查 agent_tool_bindings（禁止 import agent models）。
MCP SDK 仅经 adapters.client；禁止在持有长事务时阻塞探测（读实体后调远端）。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import new_uuid, soft_delete, utc_now
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.pagination import (
    CursorPage,
    CursorParams,
    build_cursor_page,
    decode_cursor,
)
from app.core.rules import reject_if, require_non_blank, require_uuid
from app.modules.mcp.adapters import client as mcp_client
from app.modules.mcp.constants import (
    TEST_STATUS_DOWN,
    TEST_STATUS_UP,
    TRANSPORTS,
)
from app.modules.mcp.internal.credentials import (
    auth_has_token,
    get_auth_token,
    pack_auth,
)
from app.modules.mcp.models import McpServer
from app.modules.mcp.schemas import (
    McpBoundToolOut,
    McpServerCreate,
    McpServerDebugIn,
    McpServerDebugOut,
    McpServerDetailOut,
    McpServerListItemOut,
    McpServerOptionOut,
    McpServerTestOut,
    McpServerUpdate,
    McpToolOut,
    infer_transport,
)

logger = logging.getLogger(__name__)


class McpService:
    """MCP Server 管理与选项查询。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------- 选项（Agent 绑定）----------

    async def list_enabled_options(
        self, *, workspace_id: str
    ) -> list[McpServerOptionOut]:
        """返回工作区已启用且未软删的 MCP 服务。"""
        stmt = (
            select(McpServer)
            .where(
                McpServer.workspace_id == workspace_id,
                McpServer.is_enabled.is_(True),
            )
            .order_by(McpServer.created_at.asc(), McpServer.id.asc())
        )
        rows = list((await self._session.scalars(stmt)).all())
        return [
            McpServerOptionOut(
                id=row.id,
                name=row.name,
                transport=row.transport,
                is_enabled=bool(row.is_enabled),
            )
            for row in rows
        ]

    async def list_bound_tools(
        self, *, workspace_id: str, server_ids: list[str]
    ) -> list[McpBoundToolOut]:
        """按 Agent 绑定的 mcp_server_id 列表拉取工具 schema。

        对应课程「agent_tool 关联 mcp_tool」：现网用实时 list_tools 代替 mcp_tool 表。
        单 Server 拉取失败则跳过该 Server（不中断整次对话准备）。
        """
        if not server_ids:
            return []
        out: list[McpBoundToolOut] = []
        seen_names: set[str] = set()
        for raw_id in server_ids:
            try:
                sid = require_uuid(raw_id, field="tool_ids")
            except AppError:
                continue
            try:
                row = await self._get_server_entity(workspace_id, sid)
            except AppError:
                continue
            if not row.is_enabled:
                continue
            try:
                token = get_auth_token(row.auth_encrypted)
                remote = await mcp_client.list_tools(
                    transport=row.transport,
                    endpoint=row.endpoint,
                    auth_token=token,
                    config=dict(row.config) if isinstance(row.config, dict) else None,
                )
            except Exception as exc:  # noqa: BLE001 — 准备阶段容错
                logger.warning(
                    "list_bound_tools skip server=%s err=%s", sid, exc
                )
                continue
            filtered = self._filter_tools(
                [
                    McpToolOut(
                        name=t.name,
                        description=t.description,
                        input_schema=t.input_schema,
                    )
                    for t in remote
                ],
                row.tool_whitelist,
            )
            for tool in filtered:
                # 重名时加 server 前缀，保证 LLM tools.name 唯一
                llm_name = tool.name
                if llm_name in seen_names:
                    llm_name = f"{sid[:8]}_{tool.name}"
                if llm_name in seen_names:
                    continue
                seen_names.add(llm_name)
                out.append(
                    McpBoundToolOut(
                        name=llm_name,
                        description=tool.description,
                        input_schema=dict(tool.input_schema or {"type": "object"}),
                        mcp_server_id=sid,
                        original_name=tool.name,
                    )
                )
        return out

    async def call_tool(
        self,
        *,
        workspace_id: str,
        mcp_server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> str:
        """执行 MCP 工具；成功返回文本结果。

        若配置了 tool_whitelist，执行前必须命中白名单（与 list/debug 一致）。
        """
        row = await self._get_server_entity(workspace_id, mcp_server_id)
        if not row.is_enabled:
            raise AppError(ErrorCode.BAD_REQUEST, "MCP Server 已停用")
        name = require_non_blank(tool_name, field="tool_name")
        self._assert_tool_allowed(row.tool_whitelist, name)
        token = get_auth_token(row.auth_encrypted)
        return await mcp_client.call_tool(
            transport=row.transport,
            endpoint=row.endpoint,
            tool_name=name,
            arguments=arguments,
            auth_token=token,
            config=dict(row.config) if isinstance(row.config, dict) else None,
        )

    async def assert_servers_enabled_for_binding(
        self, *, workspace_id: str, server_ids: list[str]
    ) -> list[str]:
        """校验 MCP Server 均存在、属当前工作区且启用；返回规范化 id 列表。

        供 Agent 工具绑定：一期 toolId = mcp_server_id。
        """
        if not server_ids:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in server_ids:
            sid = require_uuid(raw, field="tool_ids")
            if sid in seen:
                continue
            seen.add(sid)
            normalized.append(sid)

        stmt = select(McpServer).where(
            McpServer.workspace_id == workspace_id,
            McpServer.id.in_(normalized),
        )
        rows = list((await self._session.scalars(stmt)).all())
        found = {r.id: r for r in rows}
        missing = [x for x in normalized if x not in found]
        if missing:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"工具不存在或不属于当前工作区: {missing[0]}",
            )
        disabled = [x for x in normalized if not bool(found[x].is_enabled)]
        if disabled:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"MCP Server 已停用，无法绑定: {disabled[0]}",
            )
        return normalized

    # ---------- CRUD ----------

    async def list_servers_page(
        self, *, workspace_id: str, params: CursorParams
    ) -> CursorPage[McpServerListItemOut]:
        limit = params.limit
        stmt = select(McpServer).where(McpServer.workspace_id == workspace_id)
        if params.cursor:
            cursor_at, cursor_id = decode_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    McpServer.created_at < cursor_at,
                    and_(
                        McpServer.created_at == cursor_at,
                        McpServer.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            McpServer.created_at.desc(), McpServer.id.desc()
        ).limit(limit + 1)
        rows = list((await self._session.scalars(stmt)).all())
        items = [self._to_list_item(r) for r in rows]
        return build_cursor_page(
            items,
            limit,
            created_at_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    async def get_server(
        self, *, workspace_id: str, server_id: str, fetch_tools: bool = True
    ) -> McpServerDetailOut:
        row = await self._get_server_entity(workspace_id, server_id)
        tools: list[McpToolOut] = []
        tools_error: str | None = None
        if fetch_tools:
            tools, tools_error = await self._safe_list_tools(row)
        return self._to_detail(row, tools=tools, tools_error=tools_error)

    async def create_server(
        self,
        *,
        workspace_id: str,
        user_id: str,
        body: McpServerCreate,
    ) -> McpServerDetailOut:
        name = require_non_blank(body.name, field="name")
        endpoint = require_non_blank(body.endpoint, field="endpoint")
        await self._assert_name_unique(workspace_id=workspace_id, name=name)

        transport = (body.transport or infer_transport(endpoint)).strip().lower()
        if transport not in TRANSPORTS:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"transport 须为 {sorted(TRANSPORTS)} 之一",
            )
        self._validate_endpoint_for_transport(transport, endpoint)

        row = McpServer(
            id=new_uuid(),
            workspace_id=workspace_id,
            name=name,
            transport=transport,
            endpoint=endpoint,
            auth_encrypted=pack_auth(token=body.auth_token),
            tool_whitelist=list(body.tool_whitelist)
            if body.tool_whitelist is not None
            else None,
            config=dict(body.config) if body.config else None,
            is_enabled=bool(body.is_enabled),
            created_by=user_id,
            deleted_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return await self.get_server(
            workspace_id=workspace_id, server_id=row.id, fetch_tools=False
        )

    async def update_server(
        self,
        *,
        workspace_id: str,
        server_id: str,
        body: McpServerUpdate,
    ) -> McpServerDetailOut:
        row = await self._get_server_entity(workspace_id, server_id)
        changes = body.changed_fields()

        if "name" in changes and changes["name"] is not None:
            name = require_non_blank(changes["name"], field="name")
            if name != row.name:
                await self._assert_name_unique(
                    workspace_id=workspace_id, name=name, exclude_id=row.id
                )
            row.name = name

        if "endpoint" in changes and changes["endpoint"] is not None:
            row.endpoint = require_non_blank(changes["endpoint"], field="endpoint")

        if "transport" in changes and changes["transport"] is not None:
            row.transport = str(changes["transport"]).strip().lower()

        if "endpoint" in changes or "transport" in changes:
            self._validate_endpoint_for_transport(row.transport, row.endpoint)

        if "is_enabled" in changes and changes["is_enabled"] is not None:
            row.is_enabled = bool(changes["is_enabled"])

        if "auth_token" in changes:
            # 显式传空串/null → 清空鉴权
            row.auth_encrypted = pack_auth(token=changes.get("auth_token"))

        if "tool_whitelist" in changes:
            wl = changes["tool_whitelist"]
            row.tool_whitelist = list(wl) if wl is not None else None

        if "config" in changes:
            cfg = changes["config"]
            row.config = dict(cfg) if isinstance(cfg, dict) else cfg

        await self._session.flush()
        return await self.get_server(
            workspace_id=workspace_id, server_id=row.id, fetch_tools=False
        )

    async def delete_server(self, *, workspace_id: str, server_id: str) -> None:
        """软删；若 Agent 仍绑定该 Server 则拒绝。"""
        row = await self._get_server_entity(workspace_id, server_id)
        refs = await self._load_agent_refs(
            workspace_id=workspace_id, mcp_server_id=row.id
        )
        if refs:
            names = "、".join(r["name"] for r in refs[:5])
            more = f" 等 {len(refs)} 个" if len(refs) > 5 else ""
            raise AppError(
                ErrorCode.CONFLICT,
                f"请先取消 Agent 工具绑定后再删除（Agent：{names}{more}）",
            )
        soft_delete(row)
        await self._session.flush()

    async def test_server(
        self, *, workspace_id: str, server_id: str
    ) -> McpServerTestOut:
        """连通性测试：list_tools 成功记 UP。"""
        row = await self._get_server_entity(workspace_id, server_id)
        token = get_auth_token(row.auth_encrypted)
        result = await mcp_client.test_connection(
            transport=row.transport,
            endpoint=row.endpoint,
            auth_token=token,
            config=dict(row.config) if isinstance(row.config, dict) else None,
        )
        tools = [
            McpToolOut(
                name=t.name,
                description=t.description,
                input_schema=t.input_schema,
            )
            for t in result.tools
        ]
        # 白名单过滤（仅展示允许的工具）
        tools = self._filter_tools(tools, row.tool_whitelist)
        return McpServerTestOut(
            status=TEST_STATUS_UP if result.ok else TEST_STATUS_DOWN,
            latency_ms=result.latency_ms,
            tool_count=len(tools),
            tools=tools,
            message=None if result.ok else (result.error_message or "连通失败"),
            checked_at=utc_now(),
        )

    async def debug_call(
        self,
        *,
        workspace_id: str,
        server_id: str,
        body: McpServerDebugIn,
    ) -> McpServerDebugOut:
        """调试单次工具调用：复用 call_tool，返回结果与耗时。"""
        tool_name = require_non_blank(body.tool_name, field="tool_name")
        arguments = dict(body.arguments or {})
        started = time.perf_counter()
        try:
            result = await self.call_tool(
                workspace_id=workspace_id,
                mcp_server_id=server_id,
                tool_name=tool_name,
                arguments=arguments,
            )
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 — 映射为外部服务错误
            logger.warning(
                "mcp debug_call failed server=%s tool=%s err=%s",
                server_id,
                tool_name,
                exc,
            )
            raise AppError(
                ErrorCode.EXTERNAL_SERVICE_ERROR,
                f"工具调用失败：{exc}",
            ) from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return McpServerDebugOut(result=result or "", elapsed_ms=elapsed_ms)

    # ---------- 内部 ----------

    async def _safe_list_tools(
        self, row: McpServer
    ) -> tuple[list[McpToolOut], str | None]:
        try:
            token = get_auth_token(row.auth_encrypted)
            remote = await mcp_client.list_tools(
                transport=row.transport,
                endpoint=row.endpoint,
                auth_token=token,
                config=dict(row.config) if isinstance(row.config, dict) else None,
            )
            tools = [
                McpToolOut(
                    name=t.name,
                    description=t.description,
                    input_schema=t.input_schema,
                )
                for t in remote
            ]
            return self._filter_tools(tools, row.tool_whitelist), None
        except AppError as exc:
            logger.info(
                "mcp detail list_tools failed id=%s msg=%s", row.id, exc.message
            )
            return [], exc.message
        except Exception as exc:  # noqa: BLE001
            logger.warning("mcp detail list_tools unexpected: %s", exc)
            return [], str(exc) or "拉取工具失败"

    @staticmethod
    def _filter_tools(
        tools: list[McpToolOut], whitelist: list[Any] | None
    ) -> list[McpToolOut]:
        if not whitelist:
            return tools
        allowed = {str(x).strip() for x in whitelist if str(x).strip()}
        if not allowed:
            return tools
        return [t for t in tools if t.name in allowed]

    @staticmethod
    def _assert_tool_allowed(
        whitelist: list[Any] | None, tool_name: str
    ) -> None:
        """whitelist 为空/None 表示不限制；非空则必须命中。"""
        if not whitelist:
            return
        allowed = {str(x).strip() for x in whitelist if str(x).strip()}
        if not allowed:
            return
        if tool_name not in allowed:
            raise AppError(
                ErrorCode.FORBIDDEN,
                f"工具不在白名单中：{tool_name}",
            )

    async def _load_agent_refs(
        self, *, workspace_id: str, mcp_server_id: str
    ) -> list[dict[str, str]]:
        """只读查询仍绑定该 MCP 的 Agent（原生 SQL）。"""
        rows = (
            await self._session.execute(
                text(
                    """
SELECT a.`id` AS id, a.`name` AS name
FROM `agent_agents` a
INNER JOIN `agent_tool_bindings` b
  ON b.`agent_id` = a.`id`
 AND b.`workspace_id` = a.`workspace_id`
WHERE a.`workspace_id` = :ws
  AND a.`deleted_at` IS NULL
  AND b.`mcp_server_id` = :mcp
ORDER BY a.`created_at` ASC, a.`id` ASC
LIMIT 50
"""
                ),
                {"ws": workspace_id, "mcp": mcp_server_id},
            )
        ).all()
        return [{"id": str(r.id), "name": str(r.name)} for r in rows]

    async def _get_server_entity(
        self, workspace_id: str, server_id: str
    ) -> McpServer:
        server_id = require_uuid(server_id, field="id")
        stmt = (
            select(McpServer)
            .where(
                McpServer.workspace_id == workspace_id,
                McpServer.id == server_id,
            )
            .limit(1)
        )
        row = await self._session.scalar(stmt)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "MCP Server 不存在")
        return row

    async def _assert_name_unique(
        self,
        *,
        workspace_id: str,
        name: str,
        exclude_id: str | None = None,
    ) -> None:
        stmt = select(McpServer.id).where(
            McpServer.workspace_id == workspace_id,
            McpServer.name == name,
        )
        if exclude_id:
            stmt = stmt.where(McpServer.id != exclude_id)
        exists = await self._session.scalar(stmt)
        reject_if(
            exists is not None,
            code=ErrorCode.CONFLICT,
            message="MCP Server 名称已存在",
        )

    @staticmethod
    def _validate_endpoint_for_transport(transport: str, endpoint: str) -> None:
        if transport in {"http", "sse"}:
            from urllib.parse import urlparse

            parsed = urlparse(endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise AppError(
                    ErrorCode.BAD_REQUEST,
                    f"{transport} 类型的 endpoint 须为 http(s):// 地址",
                )
        elif transport == "stdio":
            if not endpoint.strip():
                raise AppError(ErrorCode.BAD_REQUEST, "stdio endpoint 不能为空")

    @staticmethod
    def _to_list_item(row: McpServer) -> McpServerListItemOut:
        wl = row.tool_whitelist
        return McpServerListItemOut(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            transport=row.transport,
            endpoint=row.endpoint,
            is_enabled=bool(row.is_enabled),
            has_auth=auth_has_token(row.auth_encrypted),
            tool_whitelist=[str(x) for x in wl] if isinstance(wl, list) else None,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_detail(
        row: McpServer,
        *,
        tools: list[McpToolOut],
        tools_error: str | None,
    ) -> McpServerDetailOut:
        wl = row.tool_whitelist
        return McpServerDetailOut(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            transport=row.transport,
            endpoint=row.endpoint,
            is_enabled=bool(row.is_enabled),
            has_auth=auth_has_token(row.auth_encrypted),
            tool_whitelist=[str(x) for x in wl] if isinstance(wl, list) else None,
            config=dict(row.config) if isinstance(row.config, dict) else row.config,
            tools=tools,
            tools_error=tools_error,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

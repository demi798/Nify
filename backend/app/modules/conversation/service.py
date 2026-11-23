"""conversation 用例：会话 CRUD + chat / stream_chat。

跨模块仅调 AgentService / ModelProviderService / McpService 公开方法与 LLMGateway。
SSE 长连接：写库拆独立方法；调 LLM / MCP 前必须 commit，禁止长事务持有期间外调。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import commit_before_external_io, new_uuid
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.pagination import (
    CursorPage,
    CursorParams,
    build_cursor_page,
    decode_cursor,
)
from app.core.rules import require_non_blank, require_uuid
from app.core.sse import format_sse, format_sse_error
from app.modules.agent.service import AgentService
from app.modules.conversation.constants import (
    DEFAULT_CONVERSATION_TITLE,
    ROLE_ASSISTANT,
    ROLE_SYSTEM,
    ROLE_USER,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from app.modules.conversation.internal.tool_loop import (
    append_tool_results,
    chat_with_tools,
)
from app.modules.conversation.models import Conversation, ConversationMessage
from app.modules.conversation.schemas import (
    ChatIn,
    ChatOut,
    ConversationCreate,
    ConversationOut,
    MessageOut,
)
from app.modules.mcp.service import McpBoundToolOut, McpService
from app.modules.model_provider.service import (
    ChatMessage,
    ModelProviderService,
    get_llm_gateway,
)

logger = logging.getLogger(__name__)


class ConversationService:
    """会话与对话引擎。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        agent_service: AgentService,
        model_provider_service: ModelProviderService,
        mcp_service: McpService | None = None,
    ) -> None:
        self._session = session
        self._agents = agent_service
        self._providers = model_provider_service
        self._mcp = mcp_service or McpService(session)

    # ---------- 会话 CRUD ----------

    async def create_conversation(
        self,
        *,
        workspace_id: str,
        user_id: str,
        body: ConversationCreate,
    ) -> ConversationOut:
        agent_id = require_uuid(body.agent_id, field="agent_id")
        # 校验 Agent 属于本工作区且未删
        agent = await self._agents.get_agent(
            workspace_id=workspace_id, agent_id=agent_id
        )
        title = (body.title or "").strip() or agent.name or DEFAULT_CONVERSATION_TITLE
        if len(title) > 128:
            title = title[:128]

        row = Conversation(
            id=new_uuid(),
            workspace_id=workspace_id,
            agent_id=agent.id,
            title=title,
            created_by=user_id,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_conversation_out(row)

    async def list_conversations_page(
        self, *, workspace_id: str, params: CursorParams
    ) -> CursorPage[ConversationOut]:
        limit = params.limit
        stmt = select(Conversation).where(Conversation.workspace_id == workspace_id)
        if params.cursor:
            cursor_at, cursor_id = decode_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    Conversation.created_at < cursor_at,
                    and_(
                        Conversation.created_at == cursor_at,
                        Conversation.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            Conversation.created_at.desc(), Conversation.id.desc()
        ).limit(limit + 1)
        rows = list((await self._session.scalars(stmt)).all())
        items = [self._to_conversation_out(r) for r in rows]
        return build_cursor_page(
            items,
            limit,
            created_at_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    async def get_conversation(
        self, *, workspace_id: str, conversation_id: str
    ) -> ConversationOut:
        row = await self._get_conversation_entity(workspace_id, conversation_id)
        return self._to_conversation_out(row)

    async def delete_conversation(
        self, *, workspace_id: str, conversation_id: str
    ) -> None:
        row = await self._get_conversation_entity(workspace_id, conversation_id)
        await self._session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.workspace_id == workspace_id,
                ConversationMessage.conversation_id == row.id,
            )
        )
        await self._session.delete(row)
        await self._session.flush()

    async def list_messages_page(
        self,
        *,
        workspace_id: str,
        conversation_id: str,
        params: CursorParams,
    ) -> CursorPage[MessageOut]:
        await self._get_conversation_entity(workspace_id, conversation_id)
        limit = params.limit
        stmt = select(ConversationMessage).where(
            ConversationMessage.workspace_id == workspace_id,
            ConversationMessage.conversation_id == conversation_id,
        )
        if params.cursor:
            cursor_at, cursor_id = decode_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    ConversationMessage.created_at < cursor_at,
                    and_(
                        ConversationMessage.created_at == cursor_at,
                        ConversationMessage.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            ConversationMessage.created_at.desc(),
            ConversationMessage.id.desc(),
        ).limit(limit + 1)
        rows = list((await self._session.scalars(stmt)).all())
        items = [self._to_message_out(r) for r in rows]
        return build_cursor_page(
            items,
            limit,
            created_at_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    # ---------- 对话 ----------

    async def chat(
        self,
        *,
        workspace_id: str,
        user_id: str,
        conversation_id: str,
        body: ChatIn,
    ) -> ChatOut:
        """非流式：编排与 stream_chat 相同，收齐后返回 ApiResult 业务体。"""
        content = require_non_blank(body.content, field="content")
        conv = await self._get_conversation_entity(workspace_id, conversation_id)
        user_msg = await self._insert_user_message(
            workspace_id=workspace_id,
            conversation_id=conv.id,
            content=content,
        )
        # 结束写事务后再调 LLM / MCP
        await commit_before_external_io(self._session)

        try:
            agent, creds, llm_messages, openai_tools, bound_tools = (
                await self._prepare_llm_call(
                    workspace_id=workspace_id, conversation=conv
                )
            )
            # workflowId 非空时由上游短路；现网 Agent 无该字段则跳过
            if getattr(agent, "workflow_id", None):
                raise AppError(
                    ErrorCode.BAD_REQUEST,
                    "当前会话应由工作流执行，不走普通对话",
                )

            gateway = get_llm_gateway()
            if not openai_tools:
                # 无工具：与改造前完全一致
                result = await gateway.chat(
                    provider=str(creds["provider_type"]),
                    workspace_id=workspace_id,
                    model=agent.model_name,
                    messages=llm_messages,
                    api_key=str(creds.get("api_key") or ""),
                    base_url=creds.get("base_url"),
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                )
            else:
                result = await chat_with_tools(
                    workspace_id=workspace_id,
                    agent=agent,
                    creds=creds,
                    llm_messages=llm_messages,
                    openai_tools=openai_tools,
                    bound_tools=bound_tools,
                    mcp=self._mcp,
                )
            assistant = await self._insert_assistant_message(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content=result.content or "",
                status=STATUS_COMPLETED,
                token_count=self._usage_to_token_count(result.usage),
            )
            await commit_before_external_io(self._session)
            return ChatOut(
                conversation_id=conv.id,
                user_message=self._to_message_out(user_msg),
                assistant_message=self._to_message_out(assistant),
            )
        except asyncio.CancelledError:
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="",
                status=STATUS_CANCELLED,
            )
            raise
        except AppError:
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="",
                status=STATUS_FAILED,
            )
            raise
        except Exception as exc:
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="",
                status=STATUS_FAILED,
            )
            raise AppError(ErrorCode.LLM_UNAVAILABLE, "对话失败") from exc

    async def stream_chat(
        self,
        *,
        workspace_id: str,
        user_id: str,
        conversation_id: str,
        body: ChatIn,
    ) -> AsyncIterator[str]:
        """流式对话：产出 format_sse 字符串；调 LLM 前已 commit 用户消息。"""
        content = require_non_blank(body.content, field="content")
        conv = await self._get_conversation_entity(workspace_id, conversation_id)
        user_msg = await self._insert_user_message(
            workspace_id=workspace_id,
            conversation_id=conv.id,
            content=content,
        )
        await commit_before_external_io(self._session)

        try:
            agent, creds, llm_messages, openai_tools, bound_tools = (
                await self._prepare_llm_call(
                    workspace_id=workspace_id, conversation=conv
                )
            )
        except AppError as exc:
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="",
                status=STATUS_FAILED,
            )
            yield format_sse_error(code=exc.code, message=exc.message)
            return
        except Exception as exc:
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="",
                status=STATUS_FAILED,
            )
            yield format_sse_error(
                code=ErrorCode.LLM_UNAVAILABLE.value,
                message="准备对话失败",
            )
            logger.exception("stream_chat prepare failed: %s", exc)
            return

        if getattr(agent, "workflow_id", None):
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="",
                status=STATUS_FAILED,
            )
            yield format_sse_error(
                code=ErrorCode.BAD_REQUEST.value,
                message="当前会话应由工作流执行，不走普通对话",
            )
            return

        yield format_sse(
            "meta",
            {
                "conversation_id": conv.id,
                "user_message_id": user_msg.id,
                "agent_id": conv.agent_id,
                "model": agent.model_name,
            },
        )

        gateway = get_llm_gateway()
        parts: list[str] = []
        try:
            # ---------- 无工具：原有流式路径（保持不变）----------
            if not openai_tools:
                stream = gateway.stream_chat(
                    provider=str(creds["provider_type"]),
                    workspace_id=workspace_id,
                    model=agent.model_name,
                    messages=llm_messages,
                    api_key=str(creds.get("api_key") or ""),
                    base_url=creds.get("base_url"),
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                )
                async for delta in stream:
                    if delta.text:
                        parts.append(delta.text)
                        yield format_sse("delta", {"text": delta.text})
            else:
                # ---------- 有工具：先非流式探测 tool_calls ----------
                first = await gateway.chat(
                    provider=str(creds["provider_type"]),
                    workspace_id=workspace_id,
                    model=agent.model_name,
                    messages=llm_messages,
                    api_key=str(creds.get("api_key") or ""),
                    base_url=creds.get("base_url"),
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    tools=openai_tools,
                )
                finish = (first.finish_reason or "").lower()
                if finish == "tool_calls" or first.tool_calls:
                    follow_messages = await append_tool_results(
                        workspace_id=workspace_id,
                        llm_messages=list(llm_messages),
                        first=first,
                        bound_tools=bound_tools,
                        mcp=self._mcp,
                    )
                    # 第二次流式（不再带 tools，避免连环调用）
                    stream = gateway.stream_chat(
                        provider=str(creds["provider_type"]),
                        workspace_id=workspace_id,
                        model=agent.model_name,
                        messages=follow_messages,
                        api_key=str(creds.get("api_key") or ""),
                        base_url=creds.get("base_url"),
                        temperature=agent.temperature,
                        max_tokens=agent.max_tokens,
                    )
                    async for delta in stream:
                        if delta.text:
                            parts.append(delta.text)
                            yield format_sse("delta", {"text": delta.text})
                else:
                    # stop：把首次完整答复推给前端（等价原流式终点）
                    text = first.content or ""
                    if text:
                        parts.append(text)
                        yield format_sse("delta", {"text": text})

            full = "".join(parts)
            assistant = await self._insert_assistant_message(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content=full,
                status=STATUS_COMPLETED,
                token_count=0,
            )
            await commit_before_external_io(self._session)
            yield format_sse(
                "done",
                {
                    "assistant_message_id": assistant.id,
                    "status": STATUS_COMPLETED,
                    "token_count": assistant.token_count,
                },
            )
        except asyncio.CancelledError:
            # 客户端断开：停止消费上游；不吞异常；finally/上游 Gateway 释放限流
            logger.info(
                "stream_chat cancelled conversation_id=%s emitted_chars=%s",
                conv.id,
                sum(len(p) for p in parts),
            )
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="".join(parts),
                status=STATUS_CANCELLED,
            )
            raise
        except AppError as exc:
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="".join(parts),
                status=STATUS_FAILED,
            )
            yield format_sse_error(code=exc.code, message=exc.message)
        except Exception as exc:
            await self._safe_insert_assistant(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                content="".join(parts),
                status=STATUS_FAILED,
            )
            yield format_sse_error(
                code=ErrorCode.LLM_UNAVAILABLE.value,
                message="模型调用失败",
            )
            logger.exception("stream_chat upstream failed: %s", exc)

    # ---------- 写消息（独立方法，便于在流前后单独 commit）----------

    async def _insert_user_message(
        self,
        *,
        workspace_id: str,
        conversation_id: str,
        content: str,
    ) -> ConversationMessage:
        row = ConversationMessage(
            id=new_uuid(),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            role=ROLE_USER,
            status=STATUS_COMPLETED,
            content=content,
            token_count=0,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def _insert_assistant_message(
        self,
        *,
        workspace_id: str,
        conversation_id: str,
        content: str,
        status: str,
        token_count: int = 0,
    ) -> ConversationMessage:
        row = ConversationMessage(
            id=new_uuid(),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            role=ROLE_ASSISTANT,
            status=status,
            content=content or "",
            token_count=int(token_count or 0),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def _safe_insert_assistant(
        self,
        *,
        workspace_id: str,
        conversation_id: str,
        content: str,
        status: str,
    ) -> None:
        """流失败/取消时尽量落库；忽略二次异常以免掩盖主错误。"""
        try:
            await self._insert_assistant_message(
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                content=content,
                status=status,
            )
            await commit_before_external_io(self._session)
        except Exception:
            logger.exception(
                "safe insert assistant failed conversation_id=%s status=%s",
                conversation_id,
                status,
            )
            try:
                await self._session.rollback()
            except Exception:
                pass

    # ---------- 编排 ----------

    async def _prepare_llm_call(
        self, *, workspace_id: str, conversation: Conversation
    ) -> tuple:
        """准备 Agent / 凭证 / messages / 可选 tools。

        返回 (agent, creds, llm_messages, openai_tools, bound_tools)。
        openai_tools 为空列表时调用方必须走无 tools 旧路径。
        """
        agent = await self._agents.get_agent(
            workspace_id=workspace_id, agent_id=conversation.agent_id
        )
        if not agent.is_enabled:
            raise AppError(ErrorCode.FORBIDDEN, "Agent 已禁用")

        creds = await self._providers.get_runtime_credentials(
            workspace_id=workspace_id,
            provider_id=agent.model_provider_id,
        )
        history = await self._load_recent_messages(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            max_turns=agent.max_context_turns,
        )
        # system_prompt 可含 RAG 检索片段；与 tools 并存不冲突
        llm_messages = self._build_llm_messages(
            system_prompt=agent.system_prompt,
            history=history,
        )

        bound_tools: list[McpBoundToolOut] = []
        openai_tools: list[dict[str, Any]] = []
        tool_ids = list(agent.tool_ids or [])
        if tool_ids:
            bound_tools = await self._mcp.list_bound_tools(
                workspace_id=workspace_id, server_ids=tool_ids
            )
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or t.name,
                        "parameters": t.input_schema
                        or {"type": "object", "properties": {}},
                    },
                }
                for t in bound_tools
            ]
        return agent, creds, llm_messages, openai_tools, bound_tools

    async def _load_recent_messages(
        self,
        *,
        workspace_id: str,
        conversation_id: str,
        max_turns: int,
    ) -> list[ConversationMessage]:
        """取最近消息（倒序查再反转为时间正序）；条数约 2*max_turns。"""
        limit = max(1, int(max_turns)) * 2
        stmt = (
            select(ConversationMessage)
            .where(
                ConversationMessage.workspace_id == workspace_id,
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.status == STATUS_COMPLETED,
                ConversationMessage.role.in_([ROLE_USER, ROLE_ASSISTANT]),
            )
            .order_by(
                ConversationMessage.created_at.desc(),
                ConversationMessage.id.desc(),
            )
            .limit(limit)
        )
        rows = list((await self._session.scalars(stmt)).all())
        rows.reverse()
        return rows

    @staticmethod
    def _build_llm_messages(
        *,
        system_prompt: str | None,
        history: list[ConversationMessage],
    ) -> list[ChatMessage]:
        """组装 messages；system 可含 RAG 文本，与后续 tools 参数独立。"""
        out: list[ChatMessage] = []
        if system_prompt and system_prompt.strip():
            out.append(ChatMessage(role=ROLE_SYSTEM, content=system_prompt.strip()))
        for msg in history:
            out.append(ChatMessage(role=msg.role, content=msg.content or ""))
        return out

    async def _get_conversation_entity(
        self, workspace_id: str, conversation_id: str
    ) -> Conversation:
        conversation_id = require_uuid(conversation_id, field="id")
        stmt = (
            select(Conversation)
            .where(
                Conversation.workspace_id == workspace_id,
                Conversation.id == conversation_id,
            )
            .limit(1)
        )
        row = await self._session.scalar(stmt)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "会话不存在")
        return row

    @staticmethod
    def _usage_to_token_count(usage: dict | None) -> int:
        if not usage:
            return 0
        for key in ("total_tokens", "completion_tokens", "output_tokens"):
            raw = usage.get(key)
            if isinstance(raw, int):
                return raw
            if isinstance(raw, (float, str)):
                try:
                    return int(raw)
                except ValueError:
                    continue
        return 0

    @staticmethod
    def _to_conversation_out(row: Conversation) -> ConversationOut:
        return ConversationOut(
            id=row.id,
            workspace_id=row.workspace_id,
            agent_id=row.agent_id,
            title=row.title,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_message_out(row: ConversationMessage) -> MessageOut:
        return MessageOut(
            id=row.id,
            workspace_id=row.workspace_id,
            conversation_id=row.conversation_id,
            role=row.role,
            status=row.status,
            content=row.content,
            token_count=int(row.token_count or 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

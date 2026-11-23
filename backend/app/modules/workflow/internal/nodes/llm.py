"""LLM 节点：经 Agent + ModelProvider + LLMGateway.chat。"""

from __future__ import annotations

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.modules.model_provider.service import ChatMessage
from app.modules.model_provider.service import get_llm_gateway
from app.modules.workflow.internal.engine.context import RunContext
from app.modules.workflow.internal.engine.graph import RuntimeNode
from app.modules.workflow.internal.nodes.base import NodeResult
from app.modules.workflow.node_config import LlmNodeConfig


class LlmNodeHandler:
    """llm：agent_id 必填；检索结果拼进 prompt。"""

    async def execute(
        self, *, node: RuntimeNode, ctx: RunContext
    ) -> NodeResult:
        cfg = node.config
        if not isinstance(cfg, LlmNodeConfig):
            raise AppError(ErrorCode.BAD_REQUEST, "llm 节点配置无效")
        agent_id = (cfg.agent_id or "").strip()
        if not agent_id:
            raise AppError(ErrorCode.BAD_REQUEST, "llm 节点缺少 agent_id")

        agent = await ctx.agents.get_agent(
            workspace_id=ctx.workspace_id, agent_id=agent_id
        )
        if not agent.is_enabled:
            raise AppError(ErrorCode.FORBIDDEN, "Agent 已禁用")

        creds = await ctx.providers.get_runtime_credentials(
            workspace_id=ctx.workspace_id,
            provider_id=agent.model_provider_id,
        )

        system_prompt = (cfg.system_prompt or agent.system_prompt or "").strip()
        # 拼接池中最近检索摘要
        rag_text = _collect_rag_text(ctx)
        if rag_text:
            system_prompt = (
                f"{system_prompt}\n\n参考资料：\n{rag_text}".strip()
                if system_prompt
                else f"参考资料：\n{rag_text}"
            )

        query = str(ctx.pool.get_sys("query") or "")
        messages: list[ChatMessage] = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=query))

        temperature = (
            float(cfg.temperature)
            if cfg.temperature is not None
            else float(agent.temperature)
        )
        gateway = get_llm_gateway()
        result = await gateway.chat(
            provider=str(creds["provider_type"]),
            workspace_id=ctx.workspace_id,
            model=agent.model_name,
            messages=messages,
            api_key=str(creds.get("api_key") or ""),
            base_url=creds.get("base_url"),
            temperature=temperature,
            max_tokens=agent.max_tokens,
        )
        text = (result.content or "").strip()
        return NodeResult(output={"text": text})


def _collect_rag_text(ctx: RunContext) -> str:
    """从已执行节点中收集 knowledge 的 text / chunks 摘要。"""
    parts: list[str] = []
    for _key, out in ctx.pool.node_outputs.items():
        text = out.get("text")
        if isinstance(text, str) and text.strip() and "chunks" in out:
            parts.append(text.strip())
            continue
        chunks = out.get("chunks")
        if isinstance(chunks, list) and chunks:
            for i, c in enumerate(chunks[:5], start=1):
                if isinstance(c, dict):
                    content = str(c.get("content") or "").strip()
                    if content:
                        parts.append(f"[{i}] {content}")
    return "\n".join(parts)

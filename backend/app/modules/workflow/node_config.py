"""节点配置：NodeConfig 判别联合 + NodeConfigParser（对应 Java sealed + record）。"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import Field, TypeAdapter, field_validator

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.schemas import SchemaBase
from app.modules.workflow.constants import (
    NODE_TYPE_CONDITION,
    NODE_TYPE_END,
    NODE_TYPE_KNOWLEDGE,
    NODE_TYPE_LLM,
    NODE_TYPE_START,
    NODE_TYPE_TOOL,
    NODE_TYPES,
)


class StartNodeConfig(SchemaBase):
    """开始节点：无额外配置。"""

    type: Literal["start"] = NODE_TYPE_START


class EndNodeConfig(SchemaBase):
    """结束节点。"""

    type: Literal["end"] = NODE_TYPE_END


class LlmNodeConfig(SchemaBase):
    """LLM / Agent 节点。"""

    type: Literal["llm"] = NODE_TYPE_LLM
    agent_id: str | None = Field(default=None, max_length=36)
    system_prompt: str | None = Field(default=None, max_length=50_000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

    @field_validator("agent_id", "system_prompt")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None


class KnowledgeNodeConfig(SchemaBase):
    """知识库检索节点。"""

    type: Literal["knowledge"] = NODE_TYPE_KNOWLEDGE
    knowledge_base_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("knowledge_base_ids")
    @classmethod
    def _kb_ids(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw in v or []:
            kid = (raw or "").strip()
            if not kid or kid in seen:
                continue
            seen.add(kid)
            out.append(kid)
        return out


class ConditionNodeConfig(SchemaBase):
    """条件分支节点。"""

    type: Literal["condition"] = NODE_TYPE_CONDITION
    expression: str = Field(min_length=1, max_length=2000)

    @field_validator("expression")
    @classmethod
    def _expr(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("expression 不能为空")
        return text


class ToolNodeConfig(SchemaBase):
    """工具 / MCP 节点。"""

    type: Literal["tool"] = NODE_TYPE_TOOL
    mcp_server_id: str | None = Field(default=None, max_length=36)
    tool_name: str | None = Field(default=None, max_length=128)

    @field_validator("mcp_server_id", "tool_name")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        text = v.strip()
        return text or None


NodeConfig = Annotated[
    Union[
        StartNodeConfig,
        EndNodeConfig,
        LlmNodeConfig,
        KnowledgeNodeConfig,
        ConditionNodeConfig,
        ToolNodeConfig,
    ],
    Field(discriminator="type"),
]

_adapter: TypeAdapter[Any] = TypeAdapter(NodeConfig)


class NodeConfigParser:
    """解析 / 序列化节点配置；非法类型或字段抛 AppError。"""

    @staticmethod
    def parse(node_type: str, config: dict[str, Any] | None) -> Any:
        """按 node_type 解析为对应 NodeConfig record。"""
        raw_type = (node_type or "").strip().lower()
        if raw_type not in NODE_TYPES:
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"不支持的节点类型：{node_type}",
            )
        payload = dict(config or {})
        payload["type"] = raw_type
        try:
            return _adapter.validate_python(payload)
        except Exception as exc:  # noqa: BLE001 — 统一映射为参数错误
            raise AppError(
                ErrorCode.BAD_REQUEST,
                f"节点配置无效（{raw_type}）：{exc}",
            ) from exc

    @staticmethod
    def to_dict(config: Any) -> dict[str, Any]:
        """落库用 dict（含 type）。"""
        if hasattr(config, "model_dump"):
            data = config.model_dump(mode="python")
            return dict(data)
        if isinstance(config, dict):
            return dict(config)
        raise AppError(ErrorCode.BAD_REQUEST, "无法序列化节点配置")

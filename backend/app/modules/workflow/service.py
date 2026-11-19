"""workflow 用例：CRUD；图结构拆分写入 workflow / nodes / edges（同一事务）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import new_uuid, soft_delete
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.pagination import (
    CursorPage,
    CursorParams,
    build_cursor_page,
    decode_cursor,
)
from app.core.rules import reject_if, require_non_blank, require_uuid
from app.modules.workflow.models import Workflow, WorkflowEdge, WorkflowNode
from app.modules.workflow.node_config import NodeConfigParser
from app.modules.workflow.schemas import (
    WorkflowCreate,
    WorkflowDetailOut,
    WorkflowEdgeIn,
    WorkflowEdgeOut,
    WorkflowListItemOut,
    WorkflowNodeIn,
    WorkflowNodeOut,
    WorkflowNodePosition,
    WorkflowUpdate,
)


class WorkflowService:
    """工作流定义服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_workflows_page(
        self, *, workspace_id: str, params: CursorParams
    ) -> CursorPage[WorkflowListItemOut]:
        limit = params.limit
        stmt = select(Workflow).where(Workflow.workspace_id == workspace_id)
        if params.cursor:
            cursor_at, cursor_id = decode_cursor(params.cursor)
            stmt = stmt.where(
                or_(
                    Workflow.created_at < cursor_at,
                    and_(
                        Workflow.created_at == cursor_at,
                        Workflow.id < cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(Workflow.created_at.desc(), Workflow.id.desc()).limit(
            limit + 1
        )
        rows = list((await self._session.scalars(stmt)).all())
        items: list[WorkflowListItemOut] = []
        for row in rows:
            node_count, edge_count = await self._count_graph(
                workspace_id=workspace_id, workflow_id=row.id
            )
            items.append(
                self._to_list_item(row, node_count=node_count, edge_count=edge_count)
            )
        return build_cursor_page(
            items,
            limit,
            created_at_of=lambda item: item.created_at,
            id_of=lambda item: item.id,
        )

    async def get_workflow(
        self, *, workspace_id: str, workflow_id: str
    ) -> WorkflowDetailOut:
        row = await self._get_workflow_entity(workspace_id, workflow_id)
        nodes, edges = await self._load_graph(
            workspace_id=workspace_id, workflow_id=row.id
        )
        return self._to_detail(row, nodes=nodes, edges=edges)

    async def create_workflow(
        self,
        *,
        workspace_id: str,
        user_id: str,
        body: WorkflowCreate,
    ) -> WorkflowDetailOut:
        """同一事务：写 workflow + 批量 nodes + 批量 edges。"""
        name = require_non_blank(body.name, field="name")
        await self._assert_name_unique(workspace_id=workspace_id, name=name)

        parsed_nodes = self._parse_nodes(body.nodes)
        definition = self._build_definition_snapshot(
            nodes=body.nodes, edges=body.edges
        )

        wf = Workflow(
            id=new_uuid(),
            workspace_id=workspace_id,
            name=name,
            description=body.description,
            definition=definition,
            is_enabled=bool(body.is_enabled),
            created_by=user_id,
            deleted_at=None,
        )
        self._session.add(wf)
        await self._session.flush()

        await self._insert_nodes(
            workspace_id=workspace_id,
            workflow_id=wf.id,
            nodes=parsed_nodes,
        )
        await self._insert_edges(
            workspace_id=workspace_id,
            workflow_id=wf.id,
            edges=body.edges,
        )
        await self._session.flush()

        return await self.get_workflow(
            workspace_id=workspace_id, workflow_id=wf.id
        )

    async def update_workflow(
        self,
        *,
        workspace_id: str,
        workflow_id: str,
        body: WorkflowUpdate,
    ) -> WorkflowDetailOut:
        """更新元数据；若带 nodes/edges 则整批软删旧图再插入（不做 diff）。"""
        row = await self._get_workflow_entity(workspace_id, workflow_id)
        changes = body.changed_fields()

        if "name" in changes and changes["name"] is not None:
            name = require_non_blank(changes["name"], field="name")
            if name != row.name:
                await self._assert_name_unique(
                    workspace_id=workspace_id,
                    name=name,
                    exclude_id=row.id,
                )
            row.name = name

        if "description" in changes:
            row.description = changes["description"]

        if "is_enabled" in changes and changes["is_enabled"] is not None:
            row.is_enabled = bool(changes["is_enabled"])

        replace_graph = "nodes" in changes
        if replace_graph:
            nodes_in = body.nodes or []
            edges_in = body.edges if body.edges is not None else []
            parsed_nodes = self._parse_nodes(nodes_in)
            await self._soft_delete_graph(
                workspace_id=workspace_id, workflow_id=row.id
            )
            await self._insert_nodes(
                workspace_id=workspace_id,
                workflow_id=row.id,
                nodes=parsed_nodes,
            )
            await self._insert_edges(
                workspace_id=workspace_id,
                workflow_id=row.id,
                edges=edges_in,
            )
            row.definition = self._build_definition_snapshot(
                nodes=nodes_in, edges=edges_in
            )

        await self._session.flush()
        return await self.get_workflow(
            workspace_id=workspace_id, workflow_id=row.id
        )

    async def delete_workflow(
        self, *, workspace_id: str, workflow_id: str
    ) -> None:
        """软删工作流，并一并软删关联 nodes / edges。"""
        row = await self._get_workflow_entity(workspace_id, workflow_id)
        await self._soft_delete_graph(
            workspace_id=workspace_id, workflow_id=row.id
        )
        soft_delete(row)
        await self._session.flush()

    # ---------- 图读写 ----------

    def _parse_nodes(
        self, nodes: list[WorkflowNodeIn]
    ) -> list[tuple[WorkflowNodeIn, dict[str, Any]]]:
        """NodeConfigParser 校验；返回 (入参, 落库 config dict)。"""
        out: list[tuple[WorkflowNodeIn, dict[str, Any]]] = []
        for node in nodes:
            cfg = NodeConfigParser.parse(node.type, node.config)
            out.append((node, NodeConfigParser.to_dict(cfg)))
        return out

    async def _insert_nodes(
        self,
        *,
        workspace_id: str,
        workflow_id: str,
        nodes: list[tuple[WorkflowNodeIn, dict[str, Any]]],
    ) -> None:
        for node, config in nodes:
            pos = node.position
            self._session.add(
                WorkflowNode(
                    id=new_uuid(),
                    workspace_id=workspace_id,
                    workflow_id=workflow_id,
                    node_key=node.key,
                    node_type=node.type.strip().lower(),
                    name=node.name,
                    config=config,
                    position_x=float(pos.x) if pos else None,
                    position_y=float(pos.y) if pos else None,
                    deleted_at=None,
                )
            )

    async def _insert_edges(
        self,
        *,
        workspace_id: str,
        workflow_id: str,
        edges: list[WorkflowEdgeIn],
    ) -> None:
        for edge in edges:
            self._session.add(
                WorkflowEdge(
                    id=new_uuid(),
                    workspace_id=workspace_id,
                    workflow_id=workflow_id,
                    edge_key=edge.key,
                    source_key=edge.source,
                    target_key=edge.target,
                    source_handle=edge.source_handle,
                    target_handle=edge.target_handle,
                    label=edge.label,
                    deleted_at=None,
                )
            )

    async def _soft_delete_graph(
        self, *, workspace_id: str, workflow_id: str
    ) -> None:
        node_rows = list(
            (
                await self._session.scalars(
                    select(WorkflowNode).where(
                        WorkflowNode.workspace_id == workspace_id,
                        WorkflowNode.workflow_id == workflow_id,
                    )
                )
            ).all()
        )
        for n in node_rows:
            soft_delete(n)
        edge_rows = list(
            (
                await self._session.scalars(
                    select(WorkflowEdge).where(
                        WorkflowEdge.workspace_id == workspace_id,
                        WorkflowEdge.workflow_id == workflow_id,
                    )
                )
            ).all()
        )
        for e in edge_rows:
            soft_delete(e)
        await self._session.flush()

    async def _load_graph(
        self, *, workspace_id: str, workflow_id: str
    ) -> tuple[list[WorkflowNodeOut], list[WorkflowEdgeOut]]:
        node_rows = list(
            (
                await self._session.scalars(
                    select(WorkflowNode)
                    .where(
                        WorkflowNode.workspace_id == workspace_id,
                        WorkflowNode.workflow_id == workflow_id,
                    )
                    .order_by(WorkflowNode.created_at.asc(), WorkflowNode.id.asc())
                )
            ).all()
        )
        edge_rows = list(
            (
                await self._session.scalars(
                    select(WorkflowEdge)
                    .where(
                        WorkflowEdge.workspace_id == workspace_id,
                        WorkflowEdge.workflow_id == workflow_id,
                    )
                    .order_by(WorkflowEdge.created_at.asc(), WorkflowEdge.id.asc())
                )
            ).all()
        )
        nodes = [self._to_node_out(n) for n in node_rows]
        edges = [self._to_edge_out(e) for e in edge_rows]
        return nodes, edges

    async def _count_graph(
        self, *, workspace_id: str, workflow_id: str
    ) -> tuple[int, int]:
        nodes = list(
            (
                await self._session.scalars(
                    select(WorkflowNode.id).where(
                        WorkflowNode.workspace_id == workspace_id,
                        WorkflowNode.workflow_id == workflow_id,
                    )
                )
            ).all()
        )
        edges = list(
            (
                await self._session.scalars(
                    select(WorkflowEdge.id).where(
                        WorkflowEdge.workspace_id == workspace_id,
                        WorkflowEdge.workflow_id == workflow_id,
                    )
                )
            ).all()
        )
        return len(nodes), len(edges)

    @staticmethod
    def _build_definition_snapshot(
        *, nodes: list[WorkflowNodeIn], edges: list[WorkflowEdgeIn]
    ) -> dict[str, Any]:
        """同步写入 definition JSON，便于排查（权威仍以三表为准）。"""
        return {
            "nodes": [n.model_dump(mode="python") for n in nodes],
            "edges": [e.model_dump(mode="python") for e in edges],
        }

    # ---------- 实体 ----------

    async def _get_workflow_entity(
        self, workspace_id: str, workflow_id: str
    ) -> Workflow:
        workflow_id = require_uuid(workflow_id, field="id")
        row = await self._session.get(Workflow, workflow_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "工作流不存在")
        if row.workspace_id != workspace_id:
            raise AppError(ErrorCode.FORBIDDEN, "资源不属于当前工作区")
        return row

    async def _assert_name_unique(
        self,
        *,
        workspace_id: str,
        name: str,
        exclude_id: str | None = None,
    ) -> None:
        stmt = select(Workflow.id).where(
            Workflow.workspace_id == workspace_id,
            Workflow.name == name,
        )
        if exclude_id:
            stmt = stmt.where(Workflow.id != exclude_id)
        exists = await self._session.scalar(stmt)
        reject_if(
            exists is not None,
            code=ErrorCode.CONFLICT,
            message="工作流名称已存在",
        )

    @staticmethod
    def _to_list_item(
        row: Workflow, *, node_count: int, edge_count: int
    ) -> WorkflowListItemOut:
        return WorkflowListItemOut(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            description=row.description,
            is_enabled=bool(row.is_enabled),
            node_count=node_count,
            edge_count=edge_count,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_detail(
        row: Workflow,
        *,
        nodes: list[WorkflowNodeOut],
        edges: list[WorkflowEdgeOut],
    ) -> WorkflowDetailOut:
        return WorkflowDetailOut(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            description=row.description,
            is_enabled=bool(row.is_enabled),
            nodes=nodes,
            edges=edges,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_node_out(row: WorkflowNode) -> WorkflowNodeOut:
        pos = None
        if row.position_x is not None or row.position_y is not None:
            pos = WorkflowNodePosition(
                x=float(row.position_x or 0.0),
                y=float(row.position_y or 0.0),
            )
        config = dict(row.config or {})
        # 对外 config 可不强制带 type（类型在 type 字段）；保留落库字段
        return WorkflowNodeOut(
            key=row.node_key,
            type=row.node_type,
            name=row.name,
            config=config,
            position=pos,
        )

    @staticmethod
    def _to_edge_out(row: WorkflowEdge) -> WorkflowEdgeOut:
        return WorkflowEdgeOut(
            key=row.edge_key,
            source=row.source_key,
            target=row.target_key,
            source_handle=row.source_handle,
            target_handle=row.target_handle,
            label=row.label,
        )

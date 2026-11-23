/**
 * Workflow API；经 shared/api-client，自动带 Authorization / X-Workspace-Id。
 */
import {
  deleteJson,
  getJson,
  postJson,
} from "@/shared/api-client";

export const WorkflowApiPrefix = "v1/workflows";

export type WorkflowCursorPage<T> = {
  items: T[];
  next_cursor: string | null;
};

/** 列表项 */
export type WorkflowListItem = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  is_enabled: boolean;
  node_count: number;
  edge_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowNodePosition = {
  x: number;
  y: number;
};

export type WorkflowNodeIn = {
  key: string;
  type: string;
  name?: string | null;
  config?: Record<string, unknown>;
  position?: WorkflowNodePosition | null;
};

export type WorkflowEdgeIn = {
  key: string;
  source: string;
  target: string;
  source_handle?: string | null;
  target_handle?: string | null;
  label?: string | null;
};

/** 详情 */
export type WorkflowDetail = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  is_enabled: boolean;
  nodes: WorkflowNodeIn[];
  edges: WorkflowEdgeIn[];
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowCreateBody = {
  name: string;
  description?: string | null;
  is_enabled?: boolean;
  nodes: WorkflowNodeIn[];
  edges: WorkflowEdgeIn[];
};

export type GetWorkflowListQuery = {
  page?: number;
  pageSize?: number;
  cursor?: string | null;
  limit?: number;
};

/** GET 列表 */
export async function getWorkflowList(
  query: GetWorkflowListQuery = {},
): Promise<WorkflowCursorPage<WorkflowListItem>> {
  const params = new URLSearchParams();
  const limit = query.limit ?? query.pageSize;
  if (query.cursor) params.set("cursor", query.cursor);
  if (limit != null) params.set("limit", String(limit));
  const qs = params.toString();
  const path = qs ? `${WorkflowApiPrefix}?${qs}` : WorkflowApiPrefix;
  return getJson<WorkflowCursorPage<WorkflowListItem>>(path);
}

/** POST 创建 */
export async function createWorkflow(
  body: WorkflowCreateBody,
): Promise<WorkflowDetail> {
  return postJson<WorkflowDetail>(WorkflowApiPrefix, body);
}

/** DELETE 软删 */
export async function deleteWorkflow(id: string): Promise<null> {
  return deleteJson<null>(`${WorkflowApiPrefix}/${id}`);
}

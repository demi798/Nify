/**
 * MCP Server API；经 shared/api-client。
 */
import {
  deleteJson,
  getJson,
  postJson,
  putJson,
} from "@/shared/api-client";

export const McpApiPrefix = "v1/mcp";

export type McpCursorPage<T> = {
  items: T[];
  next_cursor: string | null;
};

export type McpServerOption = {
  id: string;
  name: string;
  transport: string;
  is_enabled: boolean;
};

export type McpTool = {
  name: string;
  description: string | null;
  input_schema: Record<string, unknown> | null;
};

export type McpServerListItem = {
  id: string;
  workspace_id: string;
  name: string;
  transport: string;
  endpoint: string;
  is_enabled: boolean;
  has_auth: boolean;
  tool_whitelist: string[] | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type McpServerDetail = McpServerListItem & {
  config: Record<string, unknown> | null;
  tools: McpTool[];
  tools_error: string | null;
};

export type McpServerTestResult = {
  status: "UP" | "DOWN" | "UNKNOWN";
  latency_ms: number | null;
  tool_count: number;
  tools: McpTool[];
  message: string | null;
  checked_at: string;
};

export type McpServerCreateBody = {
  name: string;
  endpoint: string;
  transport?: string | null;
  is_enabled?: boolean;
  enabled?: boolean;
  auth_token?: string | null;
  tool_whitelist?: string[] | null;
  config?: Record<string, unknown> | null;
};

export type McpServerUpdateBody = {
  name?: string;
  endpoint?: string;
  transport?: string | null;
  is_enabled?: boolean;
  enabled?: boolean;
  auth_token?: string | null;
  tool_whitelist?: string[] | null;
  config?: Record<string, unknown> | null;
};

export type GetMcpServerListQuery = {
  pageSize?: number;
  cursor?: string | null;
  limit?: number;
};

/** GET 列表 */
export async function getMcpServerList(
  query: GetMcpServerListQuery = {},
): Promise<McpCursorPage<McpServerListItem>> {
  const params = new URLSearchParams();
  const limit = query.limit ?? query.pageSize;
  if (query.cursor) params.set("cursor", query.cursor);
  if (limit != null) params.set("limit", String(limit));
  const qs = params.toString();
  const path = qs ? `${McpApiPrefix}?${qs}` : McpApiPrefix;
  return getJson<McpCursorPage<McpServerListItem>>(path);
}

/** GET 启用选项（Agent 多选） */
export async function getMcpServerOptions(): Promise<McpServerOption[]> {
  return getJson<McpServerOption[]>(`${McpApiPrefix}/options`);
}

/** GET 详情 */
export async function getMcpServer(id: string): Promise<McpServerDetail> {
  return getJson<McpServerDetail>(`${McpApiPrefix}/${id}`);
}

/** POST 创建 */
export async function createMcpServer(
  body: McpServerCreateBody,
): Promise<McpServerDetail> {
  return postJson<McpServerDetail>(McpApiPrefix, body);
}

/** PUT 更新 */
export async function updateMcpServer(
  id: string,
  body: McpServerUpdateBody,
): Promise<McpServerDetail> {
  return putJson<McpServerDetail>(`${McpApiPrefix}/${id}`, body);
}

/** DELETE 软删 */
export async function deleteMcpServer(id: string): Promise<null> {
  return deleteJson<null>(`${McpApiPrefix}/${id}`);
}

/** POST 连通性测试 */
export async function testMcpServer(id: string): Promise<McpServerTestResult> {
  return postJson<McpServerTestResult>(`${McpApiPrefix}/${id}/test`);
}

export type McpServerDebugBody = {
  tool_name: string;
  arguments?: Record<string, unknown>;
};

export type McpServerDebugResult = {
  result: string;
  elapsed_ms: number;
};

/** POST 调试调用工具 */
export async function debugMcpServer(
  id: string,
  body: McpServerDebugBody,
): Promise<McpServerDebugResult> {
  return postJson<McpServerDebugResult>(`${McpApiPrefix}/${id}/debug`, body);
}

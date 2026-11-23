/**
 * Agent API；经 shared/api-client，自动带 Authorization / X-Workspace-Id。
 */
import {
  deleteJson,
  getJson,
  postJson,
  putJson,
} from "@/shared/api-client";
import { getKnowledgeBaseOptions } from "@/views/knowledge/api";
import { getMcpServerOptions } from "@/views/mcp/api";
import { getProviderList } from "@/views/model_provider/api";
import type {
  KnowledgeBaseOption,
  ModelSelectGroup,
  McpToolOption,
} from "./types";

export const AgentApiPrefix = "v1/agents";

export type AgentCursorPage<T> = {
  items: T[];
  next_cursor: string | null;
};

/** 绑定知识库简述 */
export type AgentKnowledgeBaseBrief = {
  id: string;
  name: string;
};

/** 列表项 */
export type AgentListItem = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  model_config_id: string;
  model_provider_id: string;
  model_name: string;
  temperature: number;
  tool_count: number;
  knowledge_base_ids: string[];
  knowledge_bases: AgentKnowledgeBaseBrief[];
  is_enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
};

/** 详情 */
export type AgentDetail = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  system_prompt: string | null;
  model_config_id: string;
  model_provider_id: string;
  model_name: string;
  temperature: number;
  max_tokens: number;
  max_context_turns: number;
  tool_ids: string[];
  knowledge_base_ids: string[];
  knowledge_bases: AgentKnowledgeBaseBrief[];
  is_enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  provider_name: string | null;
  model_display_name: string | null;
};

export type AgentCreateBody = {
  name: string;
  description?: string | null;
  system_prompt?: string | null;
  model_config_id: string;
  temperature?: number;
  max_tokens?: number;
  max_context_turns?: number;
  tool_ids?: string[];
  knowledge_base_ids?: string[];
  is_enabled?: boolean;
};

export type AgentUpdateBody = {
  name?: string;
  description?: string | null;
  system_prompt?: string | null;
  model_config_id?: string;
  temperature?: number;
  max_tokens?: number;
  max_context_turns?: number;
  tool_ids?: string[];
  knowledge_base_ids?: string[];
  is_enabled?: boolean;
};

export type GetAgentListQuery = {
  page?: number;
  pageSize?: number;
  cursor?: string | null;
  limit?: number;
};

/** GET 列表 */
export async function getAgentList(
  query: GetAgentListQuery = {},
): Promise<AgentCursorPage<AgentListItem>> {
  const params = new URLSearchParams();
  const limit = query.limit ?? query.pageSize;
  if (query.cursor) params.set("cursor", query.cursor);
  if (limit != null) params.set("limit", String(limit));
  const qs = params.toString();
  const path = qs ? `${AgentApiPrefix}?${qs}` : AgentApiPrefix;
  return getJson<AgentCursorPage<AgentListItem>>(path);
}

/** GET 详情 */
export async function getAgent(id: string): Promise<AgentDetail> {
  return getJson<AgentDetail>(`${AgentApiPrefix}/${id}`);
}

/** POST 创建 */
export async function createAgent(body: AgentCreateBody): Promise<AgentDetail> {
  return postJson<AgentDetail>(AgentApiPrefix, body);
}

/** PUT 更新 */
export async function updateAgent(
  id: string,
  body: AgentUpdateBody,
): Promise<AgentDetail> {
  return putJson<AgentDetail>(`${AgentApiPrefix}/${id}`, body);
}

/** DELETE 软删 */
export async function deleteAgent(id: string): Promise<null> {
  return deleteJson<null>(`${AgentApiPrefix}/${id}`);
}

// ── 本模块 pages 编排用：经本 api 转发他模块公开接口（禁止 pages 跨模块直连）──

/** 从 model-providers 拉取可用模型，按供应商分组 */
export async function listModelSelectGroups(): Promise<ModelSelectGroup[]> {
  const page = await getProviderList({ pageSize: 100 });
  const groups: ModelSelectGroup[] = [];
  for (const p of page.items) {
    if (!p.is_enabled) continue;
    const models = (p.modelConfig?.models ?? []).filter(
      (m) => m.is_enabled && m.status === "available",
    );
    if (models.length === 0) continue;
    groups.push({
      label: p.name,
      options: models.map((m) => ({
        label: `${m.display_name}（${m.model_key}）`,
        value: m.id,
      })),
    });
  }
  return groups;
}

/** MCP 工具多选选项（启用中的 Server） */
export async function listMcpToolOptions(): Promise<McpToolOption[]> {
  const rows = await getMcpServerOptions();
  return (rows ?? []).map((r) => ({
    id: r.id,
    name: r.name,
    transport: r.transport,
  }));
}

/** 启用中的知识库选项 */
export async function listKnowledgeBaseOptions(): Promise<
  KnowledgeBaseOption[]
> {
  const rows = await getKnowledgeBaseOptions();
  return (rows ?? []).map((r) => ({ id: r.id, name: r.name }));
}

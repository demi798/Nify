/**
 * agent 模块 API 出口 + 表单辅助数据（模型 / MCP 工具选项）。
 */
import { getAgentList, getAgent, createAgent, updateAgent, deleteAgent } from "@/api/agent";
import { getProviderList } from "@/api/provider";
import { getJson } from "@/shared/api-client";
import type { ModelSelectGroup, McpToolOption } from "./types";

export {
  getAgentList,
  getAgent,
  createAgent,
  updateAgent,
  deleteAgent,
};

export const AgentApiPrefix = "v1/agents";

type McpServerOption = {
  id: string;
  name: string;
  transport: string;
  is_enabled: boolean;
};

/** 从 model-providers 拉取可用模型，按供应商分组（仅 enabled + available） */
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

/** MCP 工具多选选项 */
export async function listMcpToolOptions(): Promise<McpToolOption[]> {
  const rows = await getJson<McpServerOption[]>("v1/mcp-servers");
  return (rows ?? []).map((r) => ({
    id: r.id,
    name: r.name,
    transport: r.transport,
  }));
}

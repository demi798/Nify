/** model_provider 模块展示类型。 */

import type { Provider, ProviderModel } from "@/api/provider";

export type ModelProviderType =
  | "openai"
  | "openai_compatible"
  | "claude"
  | "gemini"
  | "ollama";

/** 连通性健康态 */
export type HealthStatus = "UNKNOWN" | "UP" | "DOWN" | "DEGRADED";

export type ProviderModelOut = ProviderModel;
export type ProviderOut = Provider;

/** 游标分页 */
export type CursorPage<T> = {
  items: T[];
  next_cursor: string | null;
};

/** 表单字段 */
export type ModelProviderFormValues = {
  id?: string;
  name: string;
  type: ModelProviderType;
  apiKey: string;
  baseUrl: string;
  /** 上游真实 model id（连通测试 / 调用使用） */
  defaultModelKey: string;
};

/** 列表行展示（由 Provider 映射） */
export type ModelProvider = {
  id: string;
  name: string;
  type: ModelProviderType;
  apiKey: string;
  baseUrl: string;
  defaultModelKey: string;
  status: "enabled" | "disabled";
  healthStatus: HealthStatus;
  healthLatencyMs: number | null;
  healthFailCount: number;
  healthMessage: string | null;
  enabledModelCount: number;
  models: ProviderModel[];
  createdAt: string;
};

export const MODEL_PROVIDER_TYPE_OPTIONS: {
  value: ModelProviderType;
  label: string;
}[] = [
  { value: "openai", label: "OpenAI" },
  { value: "openai_compatible", label: "OpenAI 兼容" },
  { value: "claude", label: "Claude" },
  { value: "gemini", label: "Gemini" },
  { value: "ollama", label: "Ollama" },
];

export const MODEL_PROVIDER_TYPE_LABEL: Record<ModelProviderType, string> = {
  openai: "OpenAI",
  openai_compatible: "OpenAI 兼容",
  claude: "Claude",
  gemini: "Gemini",
  ollama: "Ollama",
};

export function mapProviderToRow(p: Provider): ModelProvider {
  const cfg = p.modelConfig;
  const health = p.health;
  const models = cfg?.models ?? [];
  const enabledModels = models.filter((m) => m.is_enabled);
  return {
    id: p.id,
    name: p.name,
    type: p.provider_type as ModelProviderType,
    apiKey: cfg?.has_api_key ? "********" : "",
    baseUrl: cfg?.base_url ?? "",
    defaultModelKey: cfg?.default_model_key ?? "",
    status: p.is_enabled ? "enabled" : "disabled",
    healthStatus: (health?.status as HealthStatus) ?? "UNKNOWN",
    healthLatencyMs: health?.latency_ms ?? null,
    healthFailCount: health?.fail_count ?? 0,
    healthMessage: health?.message ?? null,
    enabledModelCount: enabledModels.length,
    models,
    createdAt: p.created_at,
  };
}

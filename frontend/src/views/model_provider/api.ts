/**
 * 模型提供商 API；经 shared/api-client。
 */
import {
  deleteJson,
  getJson,
  postJson,
  putJson,
} from "@/shared/api-client";

export const ProviderApiPrefix = "v1/model-providers";

/** 游标分页 */
export type ProviderCursorPage<T> = {
  items: T[];
  next_cursor: string | null;
};

export type ProviderModel = {
  id: string;
  workspace_id: string;
  provider_id: string;
  model_key: string;
  display_name: string;
  modality: string;
  context_window: number | null;
  max_output_tokens: number | null;
  capabilities: Record<string, unknown> | null;
  is_default: boolean;
  is_enabled: boolean;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ProviderHealth = {
  status: "UNKNOWN" | "UP" | "DOWN" | "DEGRADED";
  latency_ms: number | null;
  last_success_at: string | null;
  fail_count: number;
  checked_at: string | null;
  error_code: string | null;
  message: string | null;
};

export type Provider = {
  id: string;
  workspace_id: string;
  name: string;
  provider_type: string;
  is_enabled: boolean;
  modelConfig: {
    base_url: string | null;
    auth_scheme: string;
    has_api_key: boolean;
    auth_extra: Record<string, unknown> | null;
    default_model_key: string | null;
    config: Record<string, unknown> | null;
    models?: ProviderModel[] | null;
  };
  health: ProviderHealth;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type ProviderCreateBody = {
  name: string;
  provider_type: string;
  base_url?: string | null;
  auth_scheme?: string | null;
  api_key?: string | null;
  /** 上游真实 model id */
  default_model_key?: string | null;
  is_enabled?: boolean;
};

export type ProviderUpdateBody = {
  name?: string;
  base_url?: string | null;
  auth_scheme?: string | null;
  api_key?: string | null;
  /** 上游真实 model id */
  default_model_key?: string | null;
  is_enabled?: boolean;
};

export type ProviderHealthOut = {
  id: string;
  health: ProviderHealth;
};

export type GetProviderListQuery = {
  /** NifyTable 页码（游标分页下仅用于兼容，首页传 cursor） */
  page?: number;
  pageSize?: number;
  cursor?: string | null;
  limit?: number;
};

/** GET 列表（分页）：CursorPage */
export async function getProviderList(
  query: GetProviderListQuery = {},
): Promise<ProviderCursorPage<Provider>> {
  const params = new URLSearchParams();
  const limit = query.limit ?? query.pageSize;
  if (query.cursor) params.set("cursor", query.cursor);
  if (limit != null) params.set("limit", String(limit));
  const qs = params.toString();
  const path = qs ? `${ProviderApiPrefix}?${qs}` : ProviderApiPrefix;
  return getJson<ProviderCursorPage<Provider>>(path);
}

/** POST 创建 */
export async function createProvider(
  body: ProviderCreateBody,
): Promise<Provider> {
  return postJson<Provider>(ProviderApiPrefix, body);
}

/** PUT 更新 */
export async function updateProvider(
  id: string,
  body: ProviderUpdateBody,
): Promise<Provider> {
  return putJson<Provider>(`${ProviderApiPrefix}/${id}`, body);
}

/** DELETE 删除 */
export async function deleteProvider(id: string): Promise<null> {
  return deleteJson<null>(`${ProviderApiPrefix}/${id}`);
}

/** POST 连通性测试 */
export async function testConnection(id: string): Promise<ProviderHealthOut> {
  return postJson<ProviderHealthOut>(
    `${ProviderApiPrefix}/${id}/test-connection`,
  );
}

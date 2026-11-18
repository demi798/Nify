/**
 * model_provider 模块 API 出口。
 * CRUD / 连通测试统一走 src/api/provider.ts；模型目录仍留本文件。
 */
export {
  createProvider,
  deleteProvider,
  getProviderList,
  testConnection,
  updateProvider,
  type GetProviderListQuery,
  type Provider,
  type ProviderCreateBody,
  type ProviderCursorPage,
  type ProviderHealthOut,
  type ProviderModel,
  type ProviderUpdateBody,
} from "@/api/provider";

import { getJson } from "@/shared/api-client";
import { getProviderList, type ProviderModel } from "@/api/provider";

const ModelProviderApiPrefix = "v1/model-providers";

/** 兼容旧名：列表 */
export async function listProviders(
  query: { cursor?: string | null; limit?: number } = {},
) {
  return getProviderList(query);
}

/** GET 某供应商下的模型目录 */
export async function listProviderModels(
  providerId: string,
): Promise<ProviderModel[]> {
  return getJson<ProviderModel[]>(
    `${ModelProviderApiPrefix}/${providerId}/models`,
  );
}

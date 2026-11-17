/** model_provider 模块 API；须经 shared/api-client，禁止直接 fetch。 */
import { getJson } from "@/shared/api-client";

export const ModelProviderApiPrefix = "/api/v1/model-providers";

/** 占位连通性检查（调用全局 health）。业务接口后续替换。 */
export async function pingModelProviderModule(): Promise<{ status: string }> {
  return getJson("/v1/health");
}

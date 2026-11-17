/**
 * 健康检查 API。
 * request.baseURL 已是 /api，此处路径不要再带 /api 前缀。
 */
import { get } from "@/utils/request";

export type HealthData = {
  status: string;
};

/** GET /api/v1/health */
export function getHealth(): Promise<HealthData> {
  return get<HealthData>("/v1/health");
}

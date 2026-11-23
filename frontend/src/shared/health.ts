/** 健康检查；经 shared/api-client。 */
import { getJson } from "@/shared/api-client";

export type HealthData = {
  status: string;
  [key: string]: unknown;
};

/** GET /api/v1/health */
export function getHealth(): Promise<HealthData> {
  return getJson<HealthData>("v1/health");
}

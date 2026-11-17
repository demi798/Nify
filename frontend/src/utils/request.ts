/**
 * Axios 封装：baseURL=/api，按业务 code 自动解包 data。
 * 成功：code === 200 → 返回 data
 * 失败：message.error 提示后 reject
 */
import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
} from "axios";
import { message } from "antd";

/** 后端统一响应信封 */
export type ApiEnvelope<T = unknown> = {
  code: number | string;
  message: string;
  data: T;
};

const instance: AxiosInstance = axios.create({
  baseURL: "/api",
  timeout: 30_000,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

/** 兼容 CLAUDE.md 的 "0" 与部分约定的 200 */
function isSuccessCode(code: number | string): boolean {
  return code === 0 || code === "0" || code === 200 || code === "200";
}

instance.interceptors.response.use(
  (response: AxiosResponse<ApiEnvelope>) => {
    const payload = response.data;

    // 非 JSON 信封时直接返回原始 data（少见）
    if (payload == null || typeof payload !== "object" || !("code" in payload)) {
      return response.data as never;
    }

    if (isSuccessCode(payload.code)) {
      // 自动解包：调用方拿到的是 data 字段
      return payload.data as never;
    }

    const tip = payload.message || "请求失败";
    message.error(tip);
    return Promise.reject(new Error(tip));
  },
  (error: unknown) => {
    const tip =
      axios.isAxiosError(error)
        ? (error.response?.data as ApiEnvelope | undefined)?.message ||
          error.message ||
          "网络错误"
        : "网络错误";
    message.error(tip);
    return Promise.reject(error);
  },
);

/** GET */
export function get<T = unknown>(
  url: string,
  params?: Record<string, unknown>,
  config?: AxiosRequestConfig,
): Promise<T> {
  return instance.get(url, { ...config, params }) as Promise<T>;
}

/** POST */
export function post<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return instance.post(url, data, config) as Promise<T>;
}

/** PUT */
export function put<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  return instance.put(url, data, config) as Promise<T>;
}

/** DELETE */
export function del<T = unknown>(
  url: string,
  params?: Record<string, unknown>,
  config?: AxiosRequestConfig,
): Promise<T> {
  return instance.delete(url, { ...config, params }) as Promise<T>;
}

export default instance;

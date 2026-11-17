/**
 * 统一 HTTP 客户端（CLAUDE.md）：
 * 1. 解析 {code,message,data}
 * 2. code === "0" 返回 data
 * 3. 否则抛出带 code/message 的错误
 */

export type ApiResult<T> = {
  code: string;
  message: string;
  data: T | null;
};

export class ApiClientError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
  }
}

const TOKEN_KEY = "nify_access_token";
const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = path.startsWith("http")
    ? path
    : `${baseURL.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };

  const hasBody = init?.body !== undefined && init?.body !== null;
  if (hasBody && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const token = getAccessToken();
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  let body: ApiResult<T> | null = null;
  try {
    body = (await response.json()) as ApiResult<T>;
  } catch {
    throw new ApiClientError(
      "B0001",
      `响应不是合法 JSON（HTTP ${response.status}）`,
    );
  }

  if (!response.ok || body.code !== "0") {
    throw new ApiClientError(
      body.code || String(response.status),
      body.message || `请求失败（HTTP ${response.status}）`,
    );
  }

  return body.data as T;
}

export async function getJson<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "GET" });
}

export async function postJson<T>(path: string, data?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body: data === undefined ? undefined : JSON.stringify(data),
  });
}

export async function patchJson<T>(path: string, data?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "PATCH",
    body: data === undefined ? undefined : JSON.stringify(data),
  });
}

export async function deleteJson<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "DELETE" });
}

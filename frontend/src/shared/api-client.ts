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
const WORKSPACE_KEY = "nify_workspace_id";
const USER_KEY = "nify_user";
const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

export type StoredUser = {
  id: string;
  email: string;
  display_name: string;
};

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

export function getWorkspaceId(): string | null {
  return localStorage.getItem(WORKSPACE_KEY);
}

export function setWorkspaceId(workspaceId: string | null): void {
  if (workspaceId) {
    localStorage.setItem(WORKSPACE_KEY, workspaceId);
  } else {
    localStorage.removeItem(WORKSPACE_KEY);
  }
}

export function getStoredUser(): StoredUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function setStoredUser(user: StoredUser | null): void {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}

/** 退出登录：清 token / 用户 / 工作区 */
export function clearAuthSession(): void {
  setAccessToken(null);
  setStoredUser(null);
  setWorkspaceId(null);
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

  const workspaceId = getWorkspaceId();
  if (workspaceId && !headers["X-Workspace-Id"]) {
    headers["X-Workspace-Id"] = workspaceId;
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

export async function putJson<T>(path: string, data?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "PUT",
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

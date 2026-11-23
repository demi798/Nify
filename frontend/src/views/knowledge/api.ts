/**
 * Knowledge API；经 shared/api-client，自动带 Authorization / X-Workspace-Id。
 */
import {
  ApiClientError,
  deleteJson,
  getAccessToken,
  getJson,
  getWorkspaceId,
  postJson,
  putJson,
} from "@/shared/api-client";

export const KnowledgeApiPrefix = "v1/knowledge";

export type KnowledgeCursorPage<T> = {
  items: T[];
  next_cursor: string | null;
};

export type KnowledgeBase = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  is_enabled: boolean;
  created_by: string;
  document_count: number;
  created_at: string;
  updated_at: string;
};

export type KnowledgeBaseCreateBody = {
  name: string;
  description?: string | null;
  is_enabled?: boolean;
};

export type KnowledgeBaseUpdateBody = {
  name?: string;
  description?: string | null;
  is_enabled?: boolean;
};

export type KnowledgeDocument = {
  id: string;
  workspace_id: string;
  knowledge_base_id: string;
  name: string;
  storage_key: string;
  byte_size: number;
  content_type: string;
  status: string;
  error_message: string | null;
  chunk_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type KnowledgeChunk = {
  id: string;
  workspace_id: string;
  knowledge_base_id: string;
  document_id: string;
  seq: number;
  milvus_pk: string;
  content: string;
  token_count: number;
  created_at: string;
  updated_at: string;
};

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

/** 知识库列表；q 按名称模糊搜索 */
export async function getKnowledgeBaseList(params?: {
  cursor?: string;
  pageSize?: number;
  q?: string;
}): Promise<KnowledgeCursorPage<KnowledgeBase>> {
  const search = new URLSearchParams();
  search.set("limit", String(params?.pageSize ?? 20));
  if (params?.cursor) search.set("cursor", params.cursor);
  if (params?.q?.trim()) search.set("q", params.q.trim());
  return getJson(`${KnowledgeApiPrefix}/bases?${search.toString()}`);
}

export async function getKnowledgeBase(id: string): Promise<KnowledgeBase> {
  return getJson(`${KnowledgeApiPrefix}/bases/${id}`);
}

export async function createKnowledgeBase(
  body: KnowledgeBaseCreateBody,
): Promise<KnowledgeBase> {
  return postJson(`${KnowledgeApiPrefix}/bases`, body);
}

export async function updateKnowledgeBase(
  id: string,
  body: KnowledgeBaseUpdateBody,
): Promise<KnowledgeBase> {
  return putJson(`${KnowledgeApiPrefix}/bases/${id}`, body);
}

export async function deleteKnowledgeBase(id: string): Promise<null> {
  return deleteJson(`${KnowledgeApiPrefix}/bases/${id}`);
}

export type KnowledgeBaseRefItem = {
  id: string;
  name: string;
  kind: "agent" | "workflow" | string;
};

export type KnowledgeBaseReferences = {
  knowledge_base_id: string;
  agents: KnowledgeBaseRefItem[];
  workflows: KnowledgeBaseRefItem[];
};

/** 查询仍引用该知识库的 Agent / 工作流（删除前提示） */
export async function getKnowledgeBaseReferences(
  id: string,
): Promise<KnowledgeBaseReferences> {
  return getJson(`${KnowledgeApiPrefix}/bases/${id}/references`);
}

/** 启用中的知识库选项（Agent 绑定） */
export async function getKnowledgeBaseOptions(): Promise<
  { id: string; name: string }[]
> {
  return getJson(`${KnowledgeApiPrefix}/bases/options`);
}

export async function getDocumentList(
  knowledgeBaseId: string,
  params?: { cursor?: string; pageSize?: number },
): Promise<KnowledgeCursorPage<KnowledgeDocument>> {
  const search = new URLSearchParams();
  search.set("limit", String(params?.pageSize ?? 20));
  if (params?.cursor) search.set("cursor", params.cursor);
  return getJson(
    `${KnowledgeApiPrefix}/bases/${knowledgeBaseId}/documents?${search.toString()}`,
  );
}

export async function getDocument(
  documentId: string,
): Promise<KnowledgeDocument> {
  return getJson(`${KnowledgeApiPrefix}/documents/${documentId}`);
}

export async function getDocumentChunks(
  documentId: string,
  params?: { cursor?: string; pageSize?: number },
): Promise<KnowledgeCursorPage<KnowledgeChunk>> {
  const search = new URLSearchParams();
  search.set("limit", String(params?.pageSize ?? 100));
  if (params?.cursor) search.set("cursor", params.cursor);
  return getJson(
    `${KnowledgeApiPrefix}/documents/${documentId}/chunks?${search.toString()}`,
  );
}

export async function deleteDocument(documentId: string): Promise<null> {
  return deleteJson(`${KnowledgeApiPrefix}/documents/${documentId}`);
}

export async function retryDocument(
  documentId: string,
): Promise<KnowledgeDocument> {
  return postJson(`${KnowledgeApiPrefix}/documents/${documentId}/retry`);
}

/** multipart 上传文档（不设 Content-Type，由浏览器带 boundary） */
export async function uploadDocument(
  knowledgeBaseId: string,
  file: File,
  name?: string,
): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.append("file", file);
  if (name?.trim()) form.append("name", name.trim());

  const url = `${baseURL.replace(/\/$/, "")}/${KnowledgeApiPrefix}/bases/${knowledgeBaseId}/documents`;
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const workspaceId = getWorkspaceId();
  if (workspaceId) headers["X-Workspace-Id"] = workspaceId;

  const response = await fetch(url, { method: "POST", headers, body: form });
  let body: { code: string; message: string; data: KnowledgeDocument | null };
  try {
    body = (await response.json()) as typeof body;
  } catch {
    throw new ApiClientError(
      "B0001",
      `响应不是合法 JSON（HTTP ${response.status}）`,
    );
  }
  if (!response.ok || body.code !== "0") {
    throw new ApiClientError(
      body.code || String(response.status),
      body.message || `上传失败（HTTP ${response.status}）`,
    );
  }
  return body.data as KnowledgeDocument;
}

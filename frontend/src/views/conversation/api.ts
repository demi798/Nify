/**
 * 会话 / 对话 API；经 shared/api-client（流式单独 fetch，不解 ApiResult 信封）。
 */
import {
  deleteJson,
  getAccessToken,
  getJson,
  getWorkspaceId,
  postJson,
  ApiClientError,
} from "@/shared/api-client";
import {
  getAgentList as fetchAgentList,
  type AgentListItem,
} from "@/views/agent/api";

export type { AgentListItem };

/** 本模块 pages 选 Agent：经 conversation/api 转发，禁止页面直连 agent 模块 */
export async function getAgentList(
  query: { pageSize?: number; cursor?: string | null } = {},
) {
  return fetchAgentList(query);
}

export const ConversationApiPrefix = "v1/conversations";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

export type ConversationCursorPage<T> = {
  items: T[];
  next_cursor: string | null;
};

export type Conversation = {
  id: string;
  workspace_id: string;
  agent_id: string;
  title: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: string;
  workspace_id: string;
  conversation_id: string;
  role: string;
  status: string;
  content: string;
  token_count: number;
  created_at: string;
  updated_at: string;
};

export type ChatOut = {
  conversation_id: string;
  user_message: ConversationMessage;
  assistant_message: ConversationMessage;
};

export type CreateConversationBody = {
  agent_id: string;
  title?: string | null;
};

export async function getConversationList(query: {
  pageSize?: number;
  cursor?: string | null;
} = {}): Promise<ConversationCursorPage<Conversation>> {
  const params = new URLSearchParams();
  if (query.cursor) params.set("cursor", query.cursor);
  if (query.pageSize != null) params.set("limit", String(query.pageSize));
  const qs = params.toString();
  const path = qs ? `${ConversationApiPrefix}?${qs}` : ConversationApiPrefix;
  return getJson(path);
}

export async function createConversation(
  body: CreateConversationBody,
): Promise<Conversation> {
  return postJson(ConversationApiPrefix, body);
}

export async function getConversation(id: string): Promise<Conversation> {
  return getJson(`${ConversationApiPrefix}/${id}`);
}

export async function deleteConversation(id: string): Promise<null> {
  return deleteJson(`${ConversationApiPrefix}/${id}`);
}

export async function getMessageList(
  conversationId: string,
  query: { pageSize?: number; cursor?: string | null } = {},
): Promise<ConversationCursorPage<ConversationMessage>> {
  const params = new URLSearchParams();
  if (query.cursor) params.set("cursor", query.cursor);
  if (query.pageSize != null) params.set("limit", String(query.pageSize));
  const qs = params.toString();
  const path = qs
    ? `${ConversationApiPrefix}/${conversationId}/messages?${qs}`
    : `${ConversationApiPrefix}/${conversationId}/messages`;
  return getJson(path);
}

/** 非流式 chat */
export async function chat(
  conversationId: string,
  content: string,
): Promise<ChatOut> {
  return postJson(`${ConversationApiPrefix}/${conversationId}/chat`, {
    content,
  });
}

export type StreamChatHandlers = {
  onMeta?: (data: Record<string, unknown>) => void;
  onDelta?: (text: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
  onError?: (code: string, message: string) => void;
  signal?: AbortSignal;
};

/** 流式 chat：fetch + SSE；禁止 EventSource */
export async function streamChat(
  conversationId: string,
  content: string,
  handlers: StreamChatHandlers = {},
): Promise<void> {
  const token = getAccessToken();
  const workspaceId = getWorkspaceId();
  if (!token) throw new ApiClientError("A0100", "请先登录");
  if (!workspaceId) throw new ApiClientError("A0001", "请先选择工作区");

  const url = `${baseURL.replace(/\/$/, "")}/${ConversationApiPrefix}/${conversationId}/chat/stream`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      "X-Workspace-Id": workspaceId,
    },
    body: JSON.stringify({ content }),
    signal: handlers.signal,
  });

  if (!response.ok || !response.body) {
    let message = `流式请求失败（HTTP ${response.status}）`;
    try {
      const body = (await response.json()) as { code?: string; message?: string };
      throw new ApiClientError(
        body.code || String(response.status),
        body.message || message,
      );
    } catch (err) {
      if (err instanceof ApiClientError) throw err;
      throw new ApiClientError(String(response.status), message);
    }
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let eventName = "message";
  let sawDone = false;
  let streamError: { code: string; message: string } | null = null;

  const dispatch = (event: string, dataRaw: string) => {
    if (!dataRaw) return;
    let data: Record<string, unknown> = {};
    try {
      data = JSON.parse(dataRaw) as Record<string, unknown>;
    } catch {
      return;
    }
    if (event === "meta") handlers.onMeta?.(data);
    else if (event === "delta") {
      const text = typeof data.text === "string" ? data.text : "";
      if (text) handlers.onDelta?.(text);
    } else if (event === "done") {
      sawDone = true;
      handlers.onDone?.(data);
    } else if (event === "error") {
      const code = String(data.code || "C0003");
      const message = String(data.message || "对话失败");
      streamError = { code, message };
      handlers.onError?.(code, message);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n");
    buffer = chunks.pop() ?? "";
    for (const line of chunks) {
      const trimmed = line.replace(/\r$/, "");
      if (!trimmed) {
        eventName = "message";
        continue;
      }
      if (trimmed.startsWith(":")) continue;
      if (trimmed.startsWith("event:")) {
        eventName = trimmed.slice(6).trim();
        continue;
      }
      if (trimmed.startsWith("data:")) {
        dispatch(eventName, trimmed.slice(5).trim());
      }
    }
  }

  // 流结束仍无 done：视为失败，保证上层能给 AI 气泡写入错误文案
  if (!sawDone && !streamError) {
    const code = "C0003";
    const message = "对话未正常结束";
    handlers.onError?.(code, message);
    throw new ApiClientError(code, message);
  }
  if (streamError) {
    throw new ApiClientError(streamError.code, streamError.message);
  }
}

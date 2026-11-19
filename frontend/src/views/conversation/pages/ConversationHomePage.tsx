import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PlusOutlined, SendOutlined, StopOutlined } from "@ant-design/icons";
import {
  Button,
  Empty,
  Input,
  List,
  Select,
  Space,
  Typography,
} from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getAgentList } from "@/api/agent";
import type { AgentListItem } from "@/api/agent";
import { getAccessToken, getWorkspaceId } from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError, notifySuccess } from "@/utils/notify";
import {
  createConversation,
  getConversationList,
  getMessageList,
  streamChat,
} from "../api";
import type { Conversation } from "../api";
import type { ChatBubble } from "../types";

function formatFailMessage(code?: string, message?: string): string {
  const msg = (message || "").trim() || "对话失败，请稍后重试";
  const codePart = code ? `[${code}] ` : "";
  return `${codePart}${msg}`;
}

/** 打字机光标 + Markdown 气泡内容 */
function BubbleContent({
  content,
  streaming,
  status,
  isUser,
}: {
  content: string;
  streaming?: boolean;
  status?: string;
  isUser?: boolean;
}) {
  const showLoading = Boolean(streaming && !content);
  if (showLoading) {
    return (
      <span className="nify-chat-loading" aria-label="生成中">
        <span />
        <span />
        <span />
      </span>
    );
  }

  const failed = status === "failed";
  const cancelled = status === "cancelled";
  const display =
    failed && !content.trim()
      ? formatFailMessage(undefined, "生成失败，请重试或检查模型配置")
      : content;

  if (failed) {
    return (
      <div className="nify-chat-plain nify-chat-error" role="alert">
        {display}
      </div>
    );
  }

  if (cancelled) {
    return (
      <div className="nify-chat-cancelled-wrap">
        {display.trim() ? (
          isUser ? (
            <div className="nify-chat-plain">{display}</div>
          ) : (
            <div className="nify-chat-md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{display}</ReactMarkdown>
            </div>
          )
        ) : null}
        <div className="nify-chat-cancelled" role="status">
          已停止生成
        </div>
      </div>
    );
  }

  return (
    <div className={`nify-chat-md${streaming ? " is-streaming" : ""}`}>
      {isUser ? (
        <div className="nify-chat-plain">{display}</div>
      ) : (
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{display}</ReactMarkdown>
      )}
      {streaming ? <span className="nify-chat-caret" aria-hidden /> : null}
    </div>
  );
}

/** 对话页：左会话列表 + 右聊天窗；fetch SSE 流式；Markdown；自动滚底 */
export function ConversationHomePage() {
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [agentId, setAgentId] = useState<string | undefined>();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | undefined>();
  const [bubbles, setBubbles] = useState<ChatBubble[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback((smooth = true) => {
    // 优先滚消息容器，再滚锚点
    const el = listRef.current;
    if (el) {
      el.scrollTo({
        top: el.scrollHeight,
        behavior: smooth ? "smooth" : "auto",
      });
    }
    bottomRef.current?.scrollIntoView({
      behavior: smooth ? "smooth" : "auto",
      block: "end",
    });
  }, []);

  const loadAgents = useCallback(async () => {
    if (!getAccessToken() || !getWorkspaceId()) return;
    try {
      const page = await getAgentList({ pageSize: 100 });
      const enabled = page.items.filter((a) => a.is_enabled);
      setAgents(enabled);
      setAgentId((prev) => prev ?? enabled[0]?.id);
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "加载 Agent 失败");
    }
  }, []);

  const loadConversations = useCallback(async () => {
    if (!getAccessToken() || !getWorkspaceId()) return;
    try {
      const page = await getConversationList({ pageSize: 50 });
      setConversations(page.items);
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "加载会话失败");
    }
  }, []);

  const loadMessages = useCallback(async (conversationId: string) => {
    try {
      const page = await getMessageList(conversationId, { pageSize: 100 });
      const items = [...page.items].reverse();
      setBubbles(
        items.map((m) => ({
          id: m.id,
          role: m.role as ChatBubble["role"],
          content: m.content,
          status: m.status,
        })),
      );
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "加载消息失败");
    }
  }, []);

  useEffect(() => {
    void loadAgents();
    void loadConversations();
  }, [loadAgents, loadConversations]);

  useEffect(() => {
    // 切换会话时中断进行中的流，避免后台继续打模型
    abortRef.current?.abort();
    abortRef.current = null;
    setSending(false);
    if (activeId) void loadMessages(activeId);
    else setBubbles([]);
  }, [activeId, loadMessages]);

  useEffect(() => {
    scrollToBottom(true);
  }, [bubbles, scrollToBottom]);

  // 离开页面时终止未完成的流
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const agentOptions = useMemo(
    () =>
      agents.map((a) => ({
        value: a.id,
        label: `${a.name}（${a.model_name}）`,
      })),
    [agents],
  );

  const handleNewConversation = useCallback(async () => {
    if (!agentId) {
      notifyError("请先选择 Agent（可在 Agent 页创建）");
      return;
    }
    try {
      const conv = await createConversation({ agent_id: agentId });
      notifySuccess("已新建会话");
      await loadConversations();
      setActiveId(conv.id);
      setBubbles([]);
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "创建会话失败");
    }
  }, [agentId, loadConversations]);

  /** 用户手动终止：abort fetch → 服务端 CancelledError → 落库 cancelled */
  const handleStop = useCallback(() => {
    if (!sending) return;
    abortRef.current?.abort();
  }, [sending]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || !activeId || sending) return;

    // 1) 立刻清空输入框，禁用发送
    setInput("");
    setSending(true);

    const userTempId = `local-user-${Date.now()}`;
    const assistantTempId = `local-assistant-${Date.now()}`;
    // 发送时绑定的会话；切换会话后 abort 回调不再改当前气泡
    const boundConversationId = activeId;

    // 2) 追加用户气泡；3) 紧接着空 AI 气泡（加载动画）
    setBubbles((prev) => [
      ...prev,
      { id: userTempId, role: "user", content: text },
      {
        id: assistantTempId,
        role: "assistant",
        content: "",
        streaming: true,
      },
    ]);
    // 下一帧滚到底
    queueMicrotask(() => scrollToBottom(false));

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const stillOnSameConversation = () =>
      abortRef.current === controller;

    const markAssistantFailed = (code?: string, message?: string) => {
      if (!stillOnSameConversation()) {
        setSending(false);
        return;
      }
      const tip = formatFailMessage(code, message);
      setBubbles((prev) =>
        prev.map((b) =>
          b.id === assistantTempId
            ? {
                ...b,
                streaming: false,
                status: "failed",
                // 已有部分生成内容时保留，并在下方附失败原因；全空则只显示错误
                content: b.content.trim()
                  ? `${b.content}\n\n---\n${tip}`
                  : tip,
              }
            : b,
        ),
      );
      setSending(false);
      queueMicrotask(() => scrollToBottom(true));
    };

    try {
      // 4) fetch 手动处理 SSE（POST，非 EventSource）
      await streamChat(boundConversationId, text, {
        signal: controller.signal,
        onDelta: (chunk) => {
          if (!stillOnSameConversation()) return;
          // 5) 每收到 delta 追加到 AI 气泡并滚底
          setBubbles((prev) =>
            prev.map((b) =>
              b.id === assistantTempId
                ? { ...b, content: b.content + chunk, streaming: true }
                : b,
            ),
          );
          queueMicrotask(() => scrollToBottom(false));
        },
        onDone: (data) => {
          if (!stillOnSameConversation()) {
            setSending(false);
            return;
          }
          // 6) done：去掉加载/打字态，恢复发送按钮
          const id =
            typeof data.assistant_message_id === "string"
              ? data.assistant_message_id
              : assistantTempId;
          setBubbles((prev) =>
            prev.map((b) =>
              b.id === assistantTempId
                ? {
                    ...b,
                    id,
                    streaming: false,
                    status: "completed",
                  }
                : b,
            ),
          );
          setSending(false);
          queueMicrotask(() => scrollToBottom(true));
        },
        onError: (code, message) => {
          notifyError(`${code}: ${message}`);
          markAssistantFailed(code, message);
        },
      });
      if (stillOnSameConversation()) setSending(false);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") {
        // 手动停止或切换会话：保留已生成片段，标记 cancelled
        if (stillOnSameConversation()) {
          setBubbles((prev) =>
            prev.map((b) =>
              b.id === assistantTempId
                ? {
                    ...b,
                    streaming: false,
                    status: "cancelled",
                  }
                : b,
            ),
          );
          queueMicrotask(() => scrollToBottom(true));
        }
        setSending(false);
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        return;
      }
      const code =
        err && typeof err === "object" && "code" in err
          ? String((err as { code: string }).code)
          : undefined;
      const message = err instanceof Error ? err.message : "发送失败";
      // onError 可能已写过气泡；若仍为空再补一次
      if (stillOnSameConversation()) {
        setBubbles((prev) => {
          const cur = prev.find((b) => b.id === assistantTempId);
          if (cur && cur.status === "failed" && cur.content.trim()) {
            return prev.map((b) =>
              b.id === assistantTempId ? { ...b, streaming: false } : b,
            );
          }
          return prev.map((b) =>
            b.id === assistantTempId
              ? {
                  ...b,
                  streaming: false,
                  status: "failed",
                  content: b.content.trim()
                    ? `${b.content}\n\n---\n${formatFailMessage(code, message)}`
                    : formatFailMessage(code, message),
                }
              : b,
          );
        });
        notifyError(message);
      }
      setSending(false);
    }
  }, [activeId, input, scrollToBottom, sending]);

  return (
    <div className="nify-page nify-chat-page">
      <PageHeader
        title="对话"
        description="左侧会话列表，右侧流式聊天；支持 Markdown 与自动滚底。"
        extra={
          <Space wrap>
            <Select
              style={{ minWidth: 220 }}
              placeholder="选择 Agent"
              options={agentOptions}
              value={agentId}
              onChange={setAgentId}
              allowClear
            />
            <Button
              type="primary"
              className="nify-btn-primary"
              icon={<PlusOutlined />}
              onClick={() => void handleNewConversation()}
            >
              新建会话
            </Button>
          </Space>
        }
      />

      <div className="nify-chat-layout">
        <aside className="nify-chat-sidebar">
          <PageCard className="nify-chat-sidebar-card">
            <Typography.Text type="secondary">会话列表</Typography.Text>
            <List
              className="nify-chat-session-list"
              size="small"
              dataSource={conversations}
              locale={{ emptyText: <Empty description="暂无会话" /> }}
              renderItem={(item) => (
                <List.Item
                  className={
                    item.id === activeId
                      ? "nify-chat-session is-active"
                      : "nify-chat-session"
                  }
                  onClick={() => setActiveId(item.id)}
                >
                  <Typography.Text ellipsis style={{ maxWidth: 200 }}>
                    {item.title}
                  </Typography.Text>
                </List.Item>
              )}
            />
          </PageCard>
        </aside>

        <section className="nify-chat-main">
          <PageCard className="nify-chat-main-card">
            {!activeId ? (
              <Empty description="请选择或新建会话" />
            ) : (
              <div className="nify-chat-panel">
                <div className="nify-chat-messages" ref={listRef}>
                  {bubbles.length === 0 ? (
                    <Empty description="发送第一条消息开始对话" />
                  ) : (
                    bubbles.map((b) => {
                      const isUser = b.role === "user";
                      return (
                        <div
                          key={b.id}
                          className={
                            isUser
                              ? "nify-chat-row is-user"
                              : "nify-chat-row is-assistant"
                          }
                        >
                          <div className="nify-chat-meta">
                            {isUser ? "你" : "AI"}
                            {b.streaming ? " · 生成中" : ""}
                            {b.status === "failed" ? " · 失败" : ""}
                            {b.status === "cancelled" ? " · 已停止" : ""}
                          </div>
                          <div
                            className={
                              isUser
                                ? "nify-chat-bubble is-user"
                                : "nify-chat-bubble is-assistant"
                            }
                          >
                            <BubbleContent
                              content={b.content}
                              streaming={b.streaming}
                              status={b.status}
                              isUser={isUser}
                            />
                          </div>
                        </div>
                      );
                    })
                  )}
                  <div ref={bottomRef} />
                </div>

                <div className="nify-chat-composer">
                  <Input.TextArea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="输入消息，Enter 发送（Shift+Enter 换行）"
                    autoSize={{ minRows: 2, maxRows: 5 }}
                    disabled={sending}
                    onPressEnter={(e) => {
                      if (!e.shiftKey) {
                        e.preventDefault();
                        void handleSend();
                      }
                    }}
                  />
                  {sending ? (
                    <Button
                      danger
                      className="nify-chat-send nify-chat-stop"
                      icon={<StopOutlined />}
                      onClick={handleStop}
                    >
                      停止
                    </Button>
                  ) : (
                    <Button
                      type="primary"
                      className="nify-btn-primary nify-chat-send"
                      icon={<SendOutlined />}
                      disabled={!input.trim()}
                      onClick={() => void handleSend()}
                    >
                      发送
                    </Button>
                  )}
                </div>
              </div>
            )}
          </PageCard>
        </section>
      </div>
    </div>
  );
}

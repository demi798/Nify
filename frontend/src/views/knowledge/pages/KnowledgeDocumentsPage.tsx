import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeftOutlined,
  InboxOutlined,
  LoadingOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
  Button,
  Empty,
  Modal,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { UploadFile } from "antd/es/upload/interface";
import { NifyTable, confirmDelete } from "@/shared/components";
import type { NifyTableRef } from "@/shared/components";
import { useIsNarrowScreen } from "@/shared/hooks/useMediaQuery";
import { getAccessToken, getWorkspaceId } from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError, notifySuccess } from "@/shared/notify";
import {
  deleteDocument,
  getDocument,
  getDocumentChunks,
  getDocumentList,
  getKnowledgeBase,
  retryDocument,
  uploadDocument,
} from "../api";
import type { KnowledgeChunkRow, KnowledgeDocumentRow } from "../types";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const POLL_INTERVAL_MS = 3000;
const ALLOWED_EXT = new Set(["txt", "md", "markdown", "pdf"]);

/** 终态：停止轮询（Nify ready ≈ 需求 DONE） */
const TERMINAL_STATUSES = new Set(["ready", "failed", "delete_failed"]);

function formatCreatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function fileTypeLabel(name: string, contentType: string): string {
  const ext = name.includes(".")
    ? name.slice(name.lastIndexOf(".") + 1).toLowerCase()
    : "";
  if (ext === "txt" || contentType.includes("text/plain")) return "TXT";
  if (ext === "md" || ext === "markdown" || contentType.includes("markdown")) {
    return "MD";
  }
  if (ext === "pdf" || contentType.includes("pdf")) return "PDF";
  return ext ? ext.toUpperCase() : contentType || "—";
}

function statusTag(status: string, errorMessage?: string) {
  if (status === "pending") {
    return <Tag color="default">PENDING</Tag>;
  }
  if (status === "processing") {
    return (
      <Tag color="processing" icon={<LoadingOutlined spin />}>
        PROCESSING
      </Tag>
    );
  }
  if (status === "ready") {
    return <Tag color="success">DONE</Tag>;
  }
  if (status === "failed" || status === "delete_failed") {
    const tag = (
      <Tag color="error">
        {status === "delete_failed" ? "DELETE_FAILED" : "FAILED"}
      </Tag>
    );
    if (errorMessage?.trim()) {
      return <Tooltip title={errorMessage}>{tag}</Tooltip>;
    }
    return tag;
  }
  return <Tag>{status}</Tag>;
}

function isAllowedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".") + 1) : "";
  if (ALLOWED_EXT.has(ext)) return true;
  const mime = (file.type || "").toLowerCase();
  return (
    mime === "text/plain" ||
    mime === "text/markdown" ||
    mime === "application/pdf"
  );
}

/** 知识库文档管理：上传弹窗、状态轮询、分块预览 */
export function KnowledgeDocumentsPage() {
  const { kbId: knowledgeBaseId = "" } = useParams<{ kbId: string }>();
  const tableRef = useRef<NifyTableRef>(null);
  const isNarrow = useIsNarrowScreen();
  const [kbName, setKbName] = useState("");
  const [kbEnabled, setKbEnabled] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);

  const [chunkOpen, setChunkOpen] = useState(false);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [chunkDocName, setChunkDocName] = useState("");
  const [chunks, setChunks] = useState<KnowledgeChunkRow[]>([]);
  const [expandedChunkIds, setExpandedChunkIds] = useState<Set<string>>(
    () => new Set(),
  );

  /** 正在轮询的文档 id */
  const pollingIdsRef = useRef<Set<string>>(new Set());
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPollingTimer = useCallback(() => {
    if (pollTimerRef.current != null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const ensurePollingTimer = useCallback(() => {
    if (pollTimerRef.current != null) return;
    pollTimerRef.current = setInterval(() => {
      void (async () => {
        const ids = [...pollingIdsRef.current];
        if (ids.length === 0) {
          stopPollingTimer();
          return;
        }
        let finishedAny = false;
        await Promise.all(
          ids.map(async (docId) => {
            try {
              const doc = await getDocument(docId);
              if (TERMINAL_STATUSES.has(doc.status)) {
                pollingIdsRef.current.delete(docId);
                finishedAny = true;
              }
            } catch {
              // 单次失败不中断其它轮询
            }
          }),
        );
        if (finishedAny) {
          await tableRef.current?.refresh();
        }
        if (pollingIdsRef.current.size === 0) {
          stopPollingTimer();
        }
      })();
    }, POLL_INTERVAL_MS);
  }, [stopPollingTimer]);

  const watchDocument = useCallback(
    (documentId: string) => {
      pollingIdsRef.current.add(documentId);
      ensurePollingTimer();
    },
    [ensurePollingTimer],
  );

  // 组件卸载时清理轮询，避免泄漏
  useEffect(() => {
    return () => {
      stopPollingTimer();
      pollingIdsRef.current.clear();
    };
  }, [stopPollingTimer]);

  useEffect(() => {
    if (!knowledgeBaseId || !getAccessToken() || !getWorkspaceId()) return;
    void getKnowledgeBase(knowledgeBaseId)
      .then((b) => {
        setKbName(b.name);
        setKbEnabled(Boolean(b.is_enabled));
      })
      .catch((err) => {
        notifyError(err instanceof Error ? err.message : "加载知识库失败");
      });
  }, [knowledgeBaseId]);

  const listApi = useCallback(
    async ({ pageSize }: { page: number; pageSize: number }) => {
      if (!getAccessToken()) throw new Error("请先登录");
      if (!getWorkspaceId()) throw new Error("请先选择工作区");
      if (!knowledgeBaseId) throw new Error("缺少知识库 ID");
      const page = await getDocumentList(knowledgeBaseId, { pageSize });
      const items: KnowledgeDocumentRow[] = page.items.map((d) => ({
        id: d.id,
        name: d.name,
        fileType: fileTypeLabel(d.name, d.content_type),
        contentType: d.content_type,
        byteSize: d.byte_size,
        chunkCount: d.chunk_count ?? 0,
        status: d.status,
        errorMessage: d.error_message ?? "",
        createdAt: d.created_at,
      }));
      // 列表里仍在处理的文档继续/恢复轮询
      for (const item of items) {
        if (item.status === "pending" || item.status === "processing") {
          watchDocument(item.id);
        }
      }
      return { items, next_cursor: page.next_cursor };
    },
    [knowledgeBaseId, watchDocument],
  );

  const handleUploadConfirm = useCallback(async () => {
    if (!knowledgeBaseId) return;
    const raw = fileList[0]?.originFileObj;
    if (!raw) {
      notifyError("请先选择文件");
      return;
    }
    if (!isAllowedFile(raw)) {
      notifyError("仅支持 txt / md / pdf");
      return;
    }
    if (raw.size > MAX_UPLOAD_BYTES) {
      notifyError("文件大小不能超过 10MB");
      return;
    }
    setUploading(true);
    try {
      const doc = await uploadDocument(knowledgeBaseId, raw);
      notifySuccess("已上传，正在排队处理");
      setUploadOpen(false);
      setFileList([]);
      await tableRef.current?.refresh();
      watchDocument(doc.id);
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }, [fileList, knowledgeBaseId, watchDocument]);

  const handleDelete = useCallback(async (record: KnowledgeDocumentRow) => {
    if (record.status === "processing") return;
    try {
      await confirmDelete({
        content: `确认删除文档「${record.name}」？将清除分块与向量。`,
        api: () => deleteDocument(record.id),
      });
      pollingIdsRef.current.delete(record.id);
      await tableRef.current?.refresh();
    } catch {
      // 取消或失败已提示
    }
  }, []);

  const handleRetry = useCallback(async (record: KnowledgeDocumentRow) => {
    if (record.status !== "failed" && record.status !== "delete_failed") return;
    try {
      await retryDocument(record.id);
      notifySuccess("已重新入队解析");
      watchDocument(record.id);
      await tableRef.current?.refresh();
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "重试失败");
    }
  }, [watchDocument]);

  const openChunks = useCallback(async (record: KnowledgeDocumentRow) => {
    setChunkDocName(record.name);
    setChunkOpen(true);
    setChunkLoading(true);
    setChunks([]);
    setExpandedChunkIds(new Set());
    try {
      const page = await getDocumentChunks(record.id, { pageSize: 100 });
      setChunks(
        page.items.map((c) => ({
          id: c.id,
          seq: c.seq,
          content: c.content,
          tokenCount: c.token_count,
        })),
      );
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "加载分块失败");
      setChunkOpen(false);
    } finally {
      setChunkLoading(false);
    }
  }, []);

  const toggleExpand = useCallback((chunkId: string) => {
    setExpandedChunkIds((prev) => {
      const next = new Set(prev);
      if (next.has(chunkId)) next.delete(chunkId);
      else next.add(chunkId);
      return next;
    });
  }, []);

  const columns: ColumnsType<KnowledgeDocumentRow> = useMemo(
    () => [
      {
        title: "文件名",
        dataIndex: "name",
        ellipsis: true,
      },
      {
        title: "文件类型",
        dataIndex: "fileType",
        width: 88,
      },
      {
        title: "文件大小",
        dataIndex: "byteSize",
        width: 100,
        render: (n: number) => formatBytes(n),
      },
      {
        title: "分块数量",
        dataIndex: "chunkCount",
        width: 96,
        align: "right",
      },
      {
        title: "处理状态",
        dataIndex: "status",
        width: 140,
        render: (s: string, record) => statusTag(s, record.errorMessage),
      },
      {
        title: "创建时间",
        dataIndex: "createdAt",
        width: 160,
        responsive: ["lg"],
        render: (iso: string) => formatCreatedAt(iso),
      },
      {
        title: "操作",
        key: "actions",
        width: isNarrow ? 180 : 210,
        render: (_, record) => {
          const processing = record.status === "processing";
          const canRetry =
            record.status === "failed" || record.status === "delete_failed";
          return (
            <Space size="small" wrap>
              <Button
                type="link"
                size="small"
                onClick={() => void openChunks(record)}
              >
                查看分块
              </Button>
              {canRetry ? (
                <Button
                  type="link"
                  size="small"
                  onClick={() => void handleRetry(record)}
                >
                  重试
                </Button>
              ) : null}
              <Button
                type="link"
                size="small"
                danger
                disabled={processing}
                onClick={() => void handleDelete(record)}
              >
                删除
              </Button>
            </Space>
          );
        },
      },
    ],
    [handleDelete, handleRetry, isNarrow, openChunks],
  );

  return (
    <div className="nify-page">
      <PageHeader
        title={kbName || "文档管理"}
        description={
          kbName
            ? `知识库「${kbName}」的文档列表；上传后自动异步处理。${!kbEnabled ? "（当前已停用，不可上传）" : ""}`
            : "上传 TXT / MD / PDF，系统异步分块并向量化。"
        }
        extra={
          <Space wrap>
            <Link to="/knowledge-bases">
              <Button
                className="nify-btn-secondary"
                icon={<ArrowLeftOutlined />}
              >
                返回知识库
              </Button>
            </Link>
            {!kbEnabled ? <Tag>已停用</Tag> : null}
            <Button
              type="primary"
              className="nify-btn-primary"
              icon={<UploadOutlined />}
              disabled={!kbEnabled}
              onClick={() => {
                setFileList([]);
                setUploadOpen(true);
              }}
            >
              上传文档
            </Button>
          </Space>
        }
      />
      <PageCard>
        <NifyTable<KnowledgeDocumentRow>
          ref={tableRef}
          columns={columns}
          api={listApi}
          deps={[knowledgeBaseId]}
          emptyText={
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无文档，点击右上角「上传文档」开始"
            />
          }
        />
      </PageCard>

      <Modal
        title="上传文档"
        open={uploadOpen}
        onCancel={() => {
          if (!uploading) {
            setUploadOpen(false);
            setFileList([]);
          }
        }}
        onOk={() => void handleUploadConfirm()}
        okText="开始上传"
        cancelText="取消"
        confirmLoading={uploading}
        destroyOnClose
        centered
        className="nify-confirm-modal"
      >
        <Upload.Dragger
          maxCount={1}
          fileList={fileList}
          accept=".txt,.md,.markdown,.pdf,text/plain,text/markdown,application/pdf"
          beforeUpload={(file) => {
            if (!isAllowedFile(file)) {
              notifyError("仅支持 txt / md / pdf");
              return Upload.LIST_IGNORE;
            }
            if (file.size > MAX_UPLOAD_BYTES) {
              notifyError("文件大小不能超过 10MB");
              return Upload.LIST_IGNORE;
            }
            return false;
          }}
          onChange={({ fileList: next }) => setFileList(next.slice(-1))}
          onRemove={() => setFileList([])}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined
              style={{ color: "var(--nify-color-primary, #1677ff)" }}
            />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 TXT / MD / PDF，单文件不超过 10MB
          </p>
        </Upload.Dragger>
      </Modal>

      <Modal
        title={chunkDocName ? `分块 · ${chunkDocName}` : "查看分块"}
        open={chunkOpen}
        onCancel={() => setChunkOpen(false)}
        footer={
          <Button onClick={() => setChunkOpen(false)} className="nify-btn-secondary">
            关闭
          </Button>
        }
        width={720}
        destroyOnClose
        centered
      >
        {chunkLoading ? (
          <div style={{ textAlign: "center", padding: 32 }}>
            <Spin tip="加载分块…" />
          </div>
        ) : chunks.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无分块（文档可能仍在处理或处理失败）"
          />
        ) : (
          <div className="nify-chunk-list">
            {chunks.map((c) => {
              const expanded = expandedChunkIds.has(c.id);
              const full = c.content || "";
              const truncated =
                full.length > 200 ? `${full.slice(0, 200)}…` : full;
              const showExpand = full.length > 200;
              return (
                <div key={c.id} className="nify-chunk-item">
                  <div className="nify-chunk-meta">
                    <Typography.Text strong>#{c.seq}</Typography.Text>
                    <Typography.Text type="secondary">
                      {c.tokenCount} tokens
                    </Typography.Text>
                  </div>
                  <Typography.Paragraph
                    className="nify-chunk-content"
                    style={{ marginBottom: showExpand ? 4 : 0, whiteSpace: "pre-wrap" }}
                  >
                    {expanded ? full : truncated}
                  </Typography.Paragraph>
                  {showExpand ? (
                    <Button
                      type="link"
                      size="small"
                      style={{ padding: 0 }}
                      onClick={() => toggleExpand(c.id)}
                    >
                      {expanded ? "收起" : "展开全文"}
                    </Button>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </Modal>
    </div>
  );
}

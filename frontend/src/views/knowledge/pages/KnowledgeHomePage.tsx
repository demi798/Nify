import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import {
  Button,
  Empty,
  Input,
  Spin,
  Switch,
  Tag,
  Typography,
} from "antd";
import {
  NifyFormDialog,
  NifyFormItem,
  confirmDelete,
} from "@/components";
import type { NifyFormDialogRef, NifyFormRules } from "@/components";
import { getAccessToken, getWorkspaceId } from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError, notifySuccess } from "@/utils/notify";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBase,
  getKnowledgeBaseList,
  getKnowledgeBaseReferences,
  updateKnowledgeBase,
} from "../api";
import type { KnowledgeBaseFormValues, KnowledgeBaseRow } from "../types";

/** 格式化时间 */
function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const formRules: NifyFormRules<KnowledgeBaseFormValues> = {
  name: [{ required: true, message: "请输入名称" }],
};

/** 知识库管理：卡片列表 / 启用停用 / 新建编辑删除 / 点击进文档页 */
export function KnowledgeHomePage() {
  const navigate = useNavigate();
  const dialogRef = useRef<NifyFormDialogRef<KnowledgeBaseFormValues>>(null);
  const [keyword, setKeyword] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<KnowledgeBaseRow[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const mapRow = useCallback(
    (b: {
      id: string;
      name: string;
      description: string | null;
      is_enabled: boolean;
      document_count: number;
      created_at: string;
      updated_at: string;
    }): KnowledgeBaseRow => ({
      id: b.id,
      name: b.name,
      description: b.description ?? "",
      documentCount: b.document_count ?? 0,
      isEnabled: Boolean(b.is_enabled),
      createdAt: b.created_at,
      updatedAt: b.updated_at,
    }),
    [],
  );

  const loadList = useCallback(
    async (opts?: { cursor?: string; append?: boolean }) => {
      if (!getAccessToken()) {
        notifyError("请先登录（工作区页注册/登录）");
        return;
      }
      if (!getWorkspaceId()) {
        notifyError("请先在工作区页选择或创建一个工作区");
        return;
      }
      const append = Boolean(opts?.append);
      if (append) setLoadingMore(true);
      else setLoading(true);
      try {
        const page = await getKnowledgeBaseList({
          pageSize: 24,
          cursor: opts?.cursor,
          q: searchQ || undefined,
        });
        const rows = page.items.map(mapRow);
        setItems((prev) => (append ? [...prev, ...rows] : rows));
        setNextCursor(page.next_cursor);
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "加载知识库失败");
        if (!append) setItems([]);
      } finally {
        if (append) setLoadingMore(false);
        else setLoading(false);
      }
    },
    [mapRow, searchQ],
  );

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const openCreate = useCallback(() => {
    dialogRef.current?.open();
    queueMicrotask(() => {
      dialogRef.current?.form.setFieldsValue({
        name: "",
        description: "",
        isEnabled: true,
      });
    });
  }, []);

  const openEdit = useCallback(async (record: KnowledgeBaseRow) => {
    try {
      const detail = await getKnowledgeBase(record.id);
      dialogRef.current?.open({
        id: detail.id,
        name: detail.name,
        description: detail.description ?? "",
        isEnabled: Boolean(detail.is_enabled),
      });
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "加载知识库失败");
    }
  }, []);

  const handleSubmit = useCallback(
    async (values: KnowledgeBaseFormValues, mode: "create" | "edit") => {
      try {
        const body = {
          name: values.name.trim(),
          description: values.description?.trim() || null,
          is_enabled: values.isEnabled ?? true,
        };
        if (mode === "edit") {
          if (!values.id) throw new Error("缺少知识库 ID");
          await updateKnowledgeBase(values.id, body);
          notifySuccess("已更新知识库");
        } else {
          await createKnowledgeBase(body);
          notifySuccess("已新建知识库");
        }
        await loadList();
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "保存失败");
        throw err;
      }
    },
    [loadList],
  );

  const handleToggleEnabled = useCallback(
    async (record: KnowledgeBaseRow, checked: boolean) => {
      setTogglingId(record.id);
      try {
        const updated = await updateKnowledgeBase(record.id, {
          is_enabled: checked,
        });
        setItems((prev) =>
          prev.map((item) =>
            item.id === record.id
              ? {
                  ...item,
                  isEnabled: Boolean(updated.is_enabled),
                  updatedAt: updated.updated_at,
                }
              : item,
          ),
        );
        notifySuccess(checked ? "已启用知识库" : "已停用知识库");
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "更新启用状态失败");
      } finally {
        setTogglingId(null);
      }
    },
    [],
  );

  const handleDelete = useCallback(
    async (record: KnowledgeBaseRow) => {
      let refs;
      try {
        refs = await getKnowledgeBaseReferences(record.id);
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "查询知识库关联失败");
        return;
      }
      const agentNames = refs.agents.map((a) => a.name);
      const workflowNames = refs.workflows.map((w) => w.name);
      if (agentNames.length > 0 || workflowNames.length > 0) {
        const parts: string[] = [];
        if (agentNames.length) {
          parts.push(`Agent：${agentNames.slice(0, 5).join("、")}`);
        }
        if (workflowNames.length) {
          parts.push(`工作流：${workflowNames.slice(0, 5).join("、")}`);
        }
        notifyError(
          `「${record.name}」仍被关联，请先取消知识库关联后再删除（${parts.join("；")}）。可在 Agent 编辑页取消勾选该知识库。`,
        );
        return;
      }
      if (record.documentCount > 0) {
        notifyError(
          `「${record.name}」下仍有 ${record.documentCount} 个文档，请先进入文档页全部删除后再删知识库`,
        );
        return;
      }
      try {
        await confirmDelete({
          content: `确认删除知识库「${record.name}」？删除前请确认已取消全部 Agent/工作流关联，且文档已清空。删除后可同名重建。`,
          api: () => deleteKnowledgeBase(record.id),
        });
        await loadList();
      } catch {
        // 取消或失败已提示
      }
    },
    [loadList],
  );

  const goDocuments = useCallback(
    (id: string) => {
      navigate(`/knowledge-bases/${id}/documents`);
    },
    [navigate],
  );

  return (
    <div className="nify-page">
      <PageHeader
        title="知识库"
        description="启用中可直接编辑与上传（热更新，无需停用/解绑）。停用后不可绑定 Agent、不可上传。删除前须取消关联并清空文档。"
        extra={
          <Button
            type="primary"
            className="nify-btn-primary"
            icon={<PlusOutlined />}
            onClick={openCreate}
          >
            新建知识库
          </Button>
        }
      />
      <PageCard>
        <div className="nify-toolbar" style={{ marginBottom: 16 }}>
          <Input
            allowClear
            placeholder="按名称搜索"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => setSearchQ(keyword.trim())}
            style={{ maxWidth: 280 }}
          />
          <Button
            className="nify-btn-secondary"
            onClick={() => setSearchQ(keyword.trim())}
          >
            搜索
          </Button>
        </div>

        {loading ? (
          <div style={{ padding: "48px 0", textAlign: "center" }}>
            <Spin />
          </div>
        ) : items.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              searchQ
                ? `未找到名称包含「${searchQ}」的知识库`
                : "暂无知识库，点击右上角「新建知识库」开始"
            }
          />
        ) : (
          <>
            <div className="nify-kb-grid">
              {items.map((record) => (
                <article
                  key={record.id}
                  className={
                    record.isEnabled
                      ? "nify-kb-card"
                      : "nify-kb-card nify-kb-card--disabled"
                  }
                  role="button"
                  tabIndex={0}
                  onClick={() => goDocuments(record.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      goDocuments(record.id);
                    }
                  }}
                >
                  <div className="nify-kb-card__head">
                    <h3 className="nify-kb-card__title">{record.name}</h3>
                    {record.isEnabled ? (
                      <Tag color="success">启用</Tag>
                    ) : (
                      <Tag>停用</Tag>
                    )}
                  </div>
                  <p className="nify-kb-card__desc">
                    {record.description || "暂无描述"}
                  </p>
                  <div className="nify-kb-card__meta">
                    <span>文档 {record.documentCount}</span>
                    <span>创建 {formatDateTime(record.createdAt)}</span>
                    <span>更新 {formatDateTime(record.updatedAt)}</span>
                  </div>
                  <div
                    className="nify-kb-card__actions"
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                  >
                    <Switch
                      size="small"
                      checked={record.isEnabled}
                      loading={togglingId === record.id}
                      checkedChildren="启用"
                      unCheckedChildren="停用"
                      onChange={(checked) =>
                        void handleToggleEnabled(record, checked)
                      }
                    />
                    <div className="nify-kb-card__action-btns">
                      <Button
                        type="link"
                        size="small"
                        onClick={() => void openEdit(record)}
                      >
                        编辑
                      </Button>
                      <Button
                        type="link"
                        size="small"
                        danger
                        onClick={() => void handleDelete(record)}
                      >
                        删除
                      </Button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
            {nextCursor ? (
              <div style={{ marginTop: 20, textAlign: "center" }}>
                <Button
                  className="nify-btn-secondary"
                  loading={loadingMore}
                  onClick={() =>
                    void loadList({ cursor: nextCursor, append: true })
                  }
                >
                  加载更多
                </Button>
              </div>
            ) : null}
          </>
        )}
      </PageCard>

      <NifyFormDialog<KnowledgeBaseFormValues>
        ref={dialogRef}
        title={(mode) => (mode === "edit" ? "编辑知识库" : "新建知识库")}
        rules={formRules}
        onSubmit={handleSubmit}
      >
        {() => (
          <>
            <NifyFormItem name="name" label="名称">
              <Input placeholder="例如：产品手册" maxLength={128} showCount />
            </NifyFormItem>
            <NifyFormItem name="description" label="描述">
              <Input.TextArea
                placeholder="可选，简要说明用途"
                maxLength={512}
                showCount
                autoSize={{ minRows: 2, maxRows: 4 }}
              />
            </NifyFormItem>
            <NifyFormItem
              name="isEnabled"
              label="启用"
              valuePropName="checked"
            >
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </NifyFormItem>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              创建后可在知识库内上传文档；删除前需清空文档。停用后不可绑定
              Agent、不可上传。
            </Typography.Paragraph>
          </>
        )}
      </NifyFormDialog>
    </div>
  );
}

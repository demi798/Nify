import { useCallback, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { PlusOutlined } from "@ant-design/icons";
import { Button, Space, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { NifyTable, confirmDelete } from "@/shared/components";
import type { NifyTableRef } from "@/shared/components";
import { getAccessToken, getWorkspaceId } from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError } from "@/shared/notify";
import { deleteWorkflow, getWorkflowList } from "../api";
import type { WorkflowRow } from "../types";

/** 格式化创建时间 */
function formatCreatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** 工作流列表页：名称 / 状态 / 创建时间 / 删除 */
export function WorkflowHomePage() {
  const navigate = useNavigate();
  const tableRef = useRef<NifyTableRef>(null);

  const listApi = useCallback(
    async ({ pageSize }: { page: number; pageSize: number }) => {
      if (!getAccessToken()) {
        throw new Error("请先登录（工作区页注册/登录）");
      }
      if (!getWorkspaceId()) {
        throw new Error("请先在工作区页选择或创建一个工作区");
      }
      const page = await getWorkflowList({ pageSize });
      const items: WorkflowRow[] = page.items.map((w) => ({
        id: w.id,
        name: w.name,
        description: w.description ?? "",
        isEnabled: Boolean(w.is_enabled),
        // 后端 is_enabled → 前端 DRAFT / PUBLISHED
        status: w.is_enabled ? "PUBLISHED" : "DRAFT",
        nodeCount: w.node_count ?? 0,
        edgeCount: w.edge_count ?? 0,
        createdAt: w.created_at,
      }));
      return { items, next_cursor: page.next_cursor };
    },
    [],
  );

  const handleDelete = useCallback(async (record: WorkflowRow) => {
    try {
      await confirmDelete({
        content: `确认删除工作流「${record.name}」？删除后可同名重建。`,
        api: () => deleteWorkflow(record.id),
      });
      await tableRef.current?.refresh();
    } catch {
      // 取消或失败已提示
    }
  }, []);

  const columns: ColumnsType<WorkflowRow> = useMemo(
    () => [
      {
        title: "名称",
        dataIndex: "name",
        ellipsis: true,
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 140,
        render: (status: WorkflowRow["status"]) =>
          status === "PUBLISHED" ? (
            <Tag color="success">PUBLISHED</Tag>
          ) : (
            <Tag>DRAFT</Tag>
          ),
      },
      {
        title: "创建时间",
        dataIndex: "createdAt",
        width: 180,
        render: (v: string) => formatCreatedAt(v),
      },
      {
        title: "操作",
        key: "actions",
        width: 100,
        render: (_: unknown, record: WorkflowRow) => (
          <Space size="small">
            <Button
              type="link"
              danger
              size="small"
              onClick={() => void handleDelete(record)}
            >
              删除
            </Button>
          </Space>
        ),
      },
    ],
    [handleDelete],
  );

  return (
    <div className="nify-page">
      <PageHeader
        title="工作流"
        description="编排简版工作流定义与运行。"
        extra={
          <Button
            type="primary"
            className="nify-btn-primary"
            icon={<PlusOutlined />}
            onClick={() => {
              if (!getAccessToken() || !getWorkspaceId()) {
                notifyError("请先登录并选择工作区");
                return;
              }
              navigate("/workflows/create");
            }}
          >
            新建工作流
          </Button>
        }
      />
      <PageCard>
        <NifyTable<WorkflowRow>
          ref={tableRef}
          columns={columns}
          api={listApi}
          rowKey="id"
          emptyText="暂无工作流，点击右上角新建"
        />
      </PageCard>
    </div>
  );
}

import { useCallback, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { PlusOutlined } from "@ant-design/icons";
import { Button, Input, Select, Space, Switch, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  NifyFormDialog,
  NifyFormItem,
  NifyTable,
  confirmDelete,
} from "@/shared/components";
import type { NifyFormDialogRef, NifyFormRules, NifyTableRef } from "@/shared/components";
import { getAccessToken, getWorkspaceId } from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError, notifySuccess } from "@/shared/notify";
import {
  createMcpServer,
  deleteMcpServer,
  getMcpServerList,
  testMcpServer,
  updateMcpServer,
} from "../api";
import type { McpServerFormValues, McpServerRow } from "../types";
import { MCP_TRANSPORT_OPTIONS } from "../types";

/** 格式化创建时间 */
function formatCreatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const formRules: NifyFormRules<McpServerFormValues> = {
  name: [{ required: true, message: "请输入名称" }],
  transport: [{ required: true, message: "请选择传输类型" }],
  endpoint: [
    { required: true, message: "请输入 endpoint" },
    ({ getFieldValue }) => ({
      validator(_, value) {
        const transport = getFieldValue("transport") as string;
        const raw = value == null ? "" : String(value).trim();
        if (!raw) return Promise.reject(new Error("请输入 endpoint"));
        if (
          (transport === "http" || transport === "sse") &&
          !/^https?:\/\/.+/.test(raw)
        ) {
          return Promise.reject(
            new Error("HTTP/SSE 须以 http:// 或 https:// 开头"),
          );
        }
        return Promise.resolve();
      },
    }),
  ],
};

/** MCP Server 管理：对齐 Provider（NifyTable + 表单弹窗 + 连通性测试） */
export function McpHomePage() {
  const navigate = useNavigate();
  const tableRef = useRef<NifyTableRef>(null);
  const dialogRef = useRef<NifyFormDialogRef<McpServerFormValues>>(null);

  const listApi = useCallback(
    async ({ pageSize }: { page: number; pageSize: number }) => {
      if (!getAccessToken()) {
        throw new Error("请先登录（工作区页注册/登录）");
      }
      if (!getWorkspaceId()) {
        throw new Error("请先在工作区页选择或创建一个工作区");
      }
      const page = await getMcpServerList({ pageSize });
      const items: McpServerRow[] = page.items.map((s) => ({
        id: s.id,
        name: s.name,
        transport: s.transport,
        endpoint: s.endpoint,
        isEnabled: Boolean(s.is_enabled),
        hasAuth: Boolean(s.has_auth),
        createdAt: s.created_at,
      }));
      return { items, next_cursor: page.next_cursor };
    },
    [],
  );

  const openCreate = useCallback(() => {
    dialogRef.current?.open();
    queueMicrotask(() => {
      dialogRef.current?.form.setFieldsValue({
        transport: "http",
        isEnabled: true,
        endpoint: "",
        authToken: "",
        name: "",
      });
    });
  }, []);

  const openEdit = useCallback((record: McpServerRow) => {
    dialogRef.current?.open({
      id: record.id,
      name: record.name,
      transport:
        (record.transport as McpServerFormValues["transport"]) || "http",
      endpoint: record.endpoint,
      authToken: "",
      isEnabled: record.isEnabled,
    });
  }, []);

  const handleSubmit = useCallback(
    async (values: McpServerFormValues, mode: "create" | "edit") => {
      try {
        if (mode === "edit") {
          if (!values.id) throw new Error("缺少 MCP Server ID");
          const updateBody: Parameters<typeof updateMcpServer>[1] = {
            name: values.name.trim(),
            endpoint: values.endpoint.trim(),
            transport: values.transport,
            is_enabled: Boolean(values.isEnabled),
          };
          if (values.authToken?.trim()) {
            updateBody.auth_token = values.authToken.trim();
          }
          await updateMcpServer(values.id, updateBody);
          notifySuccess("已更新 MCP 连接");
        } else {
          await createMcpServer({
            name: values.name.trim(),
            endpoint: values.endpoint.trim(),
            transport: values.transport,
            is_enabled: Boolean(values.isEnabled),
            auth_token: values.authToken?.trim() || undefined,
          });
          notifySuccess("已添加 MCP 连接");
        }
        await tableRef.current?.refresh();
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "保存失败");
        throw err;
      }
    },
    [],
  );

  const handleDelete = useCallback(async (record: McpServerRow) => {
    try {
      await confirmDelete({
        content: `确认删除 MCP「${record.name}」？若有 Agent 绑定将无法删除。`,
        api: () => deleteMcpServer(record.id),
      });
      await tableRef.current?.refresh();
    } catch {
      // 取消或失败已提示
    }
  }, []);

  const handleTest = useCallback(async (record: McpServerRow) => {
    try {
      const result = await testMcpServer(record.id);
      if (result.status === "UP") {
        notifySuccess(
          `连通成功（${result.latency_ms ?? "—"}ms，工具 ${result.tool_count} 个）`,
        );
      } else {
        notifyError(result.message || "连通失败");
      }
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "连通性测试失败");
    }
  }, []);

  const columns: ColumnsType<McpServerRow> = useMemo(
    () => [
      {
        title: "名称",
        dataIndex: "name",
        ellipsis: true,
      },
      {
        title: "传输",
        dataIndex: "transport",
        width: 110,
        render: (v: string) => <Tag>{v}</Tag>,
      },
      {
        title: "Endpoint",
        dataIndex: "endpoint",
        ellipsis: true,
      },
      {
        title: "启用",
        dataIndex: "isEnabled",
        width: 80,
        render: (v: boolean) =>
          v ? <Tag color="success">是</Tag> : <Tag>否</Tag>,
      },
      {
        title: "创建时间",
        dataIndex: "createdAt",
        width: 170,
        render: (v: string) => formatCreatedAt(v),
      },
      {
        title: "操作",
        key: "actions",
        width: 280,
        render: (_: unknown, record: McpServerRow) => (
          <Space size="small" wrap>
            <Button type="link" size="small" onClick={() => openEdit(record)}>
              编辑
            </Button>
            <Button
              type="link"
              size="small"
              onClick={() =>
                navigate(`/mcp/${record.id}?tab=debug`)
              }
            >
              调试
            </Button>
            <Button
              type="link"
              size="small"
              onClick={() => void handleTest(record)}
            >
              测试
            </Button>
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
    [handleDelete, handleTest, navigate, openEdit],
  );

  return (
    <div className="nify-page">
      <PageHeader
        title="MCP"
        description="配置 MCP 连接与白名单工具。"
        extra={
          <Button
            type="primary"
            className="nify-btn-primary"
            icon={<PlusOutlined />}
            onClick={openCreate}
          >
            添加连接
          </Button>
        }
      />
      <PageCard>
        <NifyTable<McpServerRow>
          ref={tableRef}
          columns={columns}
          api={listApi}
          rowKey="id"
          emptyText="暂无 MCP 连接，点击右上角添加"
        />
      </PageCard>

      <NifyFormDialog<McpServerFormValues>
        ref={dialogRef}
        title={(mode) => (mode === "edit" ? "编辑 MCP 连接" : "添加 MCP 连接")}
        rules={formRules}
        onSubmit={handleSubmit}
        width={560}
      >
        {(form) => (
          <>
            <NifyFormItem name="name" label="名称">
              <Input maxLength={128} placeholder="例如：天气工具" />
            </NifyFormItem>
            <NifyFormItem name="transport" label="传输类型" initialValue="http">
              <Select
                options={MCP_TRANSPORT_OPTIONS}
                onChange={() => {
                  void form.validateFields(["endpoint"]);
                }}
              />
            </NifyFormItem>
            <NifyFormItem
              name="endpoint"
              label="Endpoint"
              extra="HTTP/SSE 填 URL；stdio 填可执行命令"
            >
              <Input.TextArea rows={2} maxLength={512} />
            </NifyFormItem>
            <NifyFormItem
              name="authToken"
              label="鉴权 Token"
              extra="可选；编辑时留空表示不修改"
            >
              <Input.Password placeholder="Bearer Token（可选）" />
            </NifyFormItem>
            <NifyFormItem
              name="isEnabled"
              label="启用"
              valuePropName="checked"
              initialValue={true}
            >
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </NifyFormItem>
          </>
        )}
      </NifyFormDialog>
    </div>
  );
}

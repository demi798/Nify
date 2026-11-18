import { useCallback, useMemo, useRef, useState } from "react";
import { PlusOutlined } from "@ant-design/icons";
import { Button, Input, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  NifyFormDialog,
  NifyFormItem,
  NifyTable,
  confirmDelete,
} from "@/components";
import type { NifyFormDialogRef, NifyFormRules, NifyTableRef } from "@/components";
import {
  createProvider,
  deleteProvider,
  getProviderList,
  testConnection,
  updateProvider,
} from "@/api/provider";
import { useIsNarrowScreen } from "@/hooks/useMediaQuery";
import { getAccessToken, getWorkspaceId } from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError, notifySuccess } from "@/utils/notify";
import type {
  HealthStatus,
  ModelProvider,
  ModelProviderFormValues,
} from "../types";
import {
  MODEL_PROVIDER_TYPE_LABEL,
  MODEL_PROVIDER_TYPE_OPTIONS,
  mapProviderToRow,
} from "../types";

function renderHealthTag(status: HealthStatus) {
  if (status === "UP") return <Tag color="success">UP</Tag>;
  if (status === "DOWN") return <Tag color="error">DOWN</Tag>;
  if (status === "DEGRADED") return <Tag color="warning">DEGRADED</Tag>;
  return <Tag>UNKNOWN</Tag>;
}

/** 格式化创建时间（展示用） */
function formatCreatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const formRules: NifyFormRules<ModelProviderFormValues> = {
  name: [{ required: true, message: "请输入名称" }],
  type: [{ required: true, message: "请选择类型" }],
  // 新增时非 Ollama 必填；编辑时留空表示不修改
  apiKey: [
    ({ getFieldValue }) => ({
      validator(_, value) {
        const id = getFieldValue("id") as string | undefined;
        if (id) return Promise.resolve();
        const providerType = getFieldValue("type") as ModelProviderFormValues["type"];
        if (providerType === "ollama") return Promise.resolve();
        if (!value || !String(value).trim()) {
          return Promise.reject(new Error("请输入 API Key"));
        }
        return Promise.resolve();
      },
    }),
  ],
  baseUrl: [
    ({ getFieldValue }) => ({
      validator(_, value) {
        const providerType = getFieldValue("type") as ModelProviderFormValues["type"];
        const raw = value == null ? "" : String(value).trim();
        if (providerType === "openai_compatible" && !raw) {
          return Promise.reject(new Error("OpenAI 兼容类型必须填写 Base URL"));
        }
        if (raw && !/^https?:\/\/.+/.test(raw)) {
          return Promise.reject(
            new Error("请以 http:// 或 https:// 开头，或留空使用默认"),
          );
        }
        return Promise.resolve();
      },
    }),
  ],
  defaultModelKey: [
    ({ getFieldValue }) => ({
      validator(_, value) {
        const providerType = getFieldValue("type") as ModelProviderFormValues["type"];
        const raw = value == null ? "" : String(value).trim();
        if (providerType === "openai_compatible" && !raw) {
          return Promise.reject(
            new Error("请填写上游真实模型名（如 qwen-flash）"),
          );
        }
        return Promise.resolve();
      },
    }),
  ],
};

/** 模型提供商管理：真实 API + NifyTable / NifyFormDialog */
export function ModelProviderHomePage() {
  const tableRef = useRef<NifyTableRef>(null);
  const dialogRef = useRef<NifyFormDialogRef<ModelProviderFormValues>>(null);
  const isNarrow = useIsNarrowScreen();
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([]);

  const listApi = useCallback(
    async ({ pageSize }: { page: number; pageSize: number }) => {
      if (!getAccessToken()) {
        throw new Error("请先登录（工作区页注册/登录）");
      }
      if (!getWorkspaceId()) {
        throw new Error("请先在工作区页选择或创建一个工作区");
      }
      const page = await getProviderList({ pageSize });
      return {
        items: page.items.map(mapProviderToRow),
        next_cursor: page.next_cursor,
      };
    },
    [],
  );

  const handleSubmit = useCallback(
    async (values: ModelProviderFormValues, mode: "create" | "edit") => {
      try {
        if (mode === "edit") {
          if (!values.id) throw new Error("缺少提供商 ID");
          const body: Parameters<typeof updateProvider>[1] = {
            name: values.name,
            base_url: values.baseUrl?.trim() || null,
          };
          if (values.apiKey?.trim()) {
            body.api_key = values.apiKey.trim();
          }
          if (values.defaultModelKey?.trim()) {
            body.default_model_key = values.defaultModelKey.trim();
          }
          await updateProvider(values.id, body);
          notifySuccess("已更新提供商");
        } else {
          await createProvider({
            name: values.name,
            provider_type: values.type,
            base_url: values.baseUrl?.trim() || null,
            api_key: values.apiKey?.trim() || null,
            default_model_key: values.defaultModelKey?.trim() || null,
          });
          notifySuccess("已新增提供商");
        }
        await tableRef.current?.refresh();
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "保存失败");
        throw err;
      }
    },
    [],
  );

  const handleDelete = useCallback(async (record: ModelProvider) => {
    try {
      await confirmDelete({
        content: `确认删除提供商「${record.name}」？删除后不可恢复。`,
        api: () => deleteProvider(record.id),
      });
      await tableRef.current?.refresh();
    } catch {
      // 取消或失败已提示
    }
  }, []);

  const handleConnectivityTest = useCallback(async (record: ModelProvider) => {
    try {
      const result = await testConnection(record.id);
      const health = result.health;
      if (health.status === "UP") {
        notifySuccess(`连通成功（${health.latency_ms ?? "-"} ms）`);
      } else {
        notifyError(
          health.message ||
            `连通失败（连续失败 ${health.fail_count} 次）`,
        );
      }
      await tableRef.current?.refresh();
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "连通性测试失败");
    }
  }, []);

  const toggleExpand = useCallback((record: ModelProvider) => {
    setExpandedRowKeys((prev) =>
      prev.includes(record.id)
        ? prev.filter((k) => k !== record.id)
        : [...prev, record.id],
    );
  }, []);

  const columns: ColumnsType<ModelProvider> = useMemo(() => {
    const cols: ColumnsType<ModelProvider> = [
      {
        title: "名称",
        dataIndex: "name",
        width: 160,
        ellipsis: true,
      },
      {
        title: "类型",
        dataIndex: "type",
        width: 100,
        render: (type: ModelProvider["type"]) =>
          MODEL_PROVIDER_TYPE_LABEL[type] ?? type,
      },
    ];

    if (!isNarrow) {
      cols.push({
        title: "Base URL",
        dataIndex: "baseUrl",
        width: 240,
        ellipsis: true,
        render: (v: string) => v || "—",
      });
    }

    cols.push(
      {
        title: "启用",
        dataIndex: "status",
        width: 80,
        render: (status: ModelProvider["status"]) =>
          status === "enabled" ? (
            <Tag color="success">启用</Tag>
          ) : (
            <Tag>禁用</Tag>
          ),
      },
      {
        title: "健康状态",
        dataIndex: "healthStatus",
        width: 110,
        render: (status: HealthStatus, record) => (
          <Space size={4} direction="vertical">
            {renderHealthTag(status)}
            {record.healthLatencyMs != null ? (
              <span className="nify-caption">{record.healthLatencyMs} ms</span>
            ) : null}
          </Space>
        ),
      },
      {
        title: "模型数",
        dataIndex: "enabledModelCount",
        width: 90,
        render: (count: number, record) => (
          <Typography.Link onClick={() => toggleExpand(record)}>
            {count}
          </Typography.Link>
        ),
      },
    );

    if (!isNarrow) {
      cols.push({
        title: "创建时间",
        dataIndex: "createdAt",
        width: 160,
        render: (v: string) => formatCreatedAt(v),
      });
    }

    cols.push({
      title: "操作",
      key: "actions",
      width: isNarrow ? 160 : 220,
      fixed: "right",
      render: (_, record) => (
        <Space size="small">
          <Typography.Link onClick={() => void handleConnectivityTest(record)}>
            连通性测试
          </Typography.Link>
          <Typography.Link
            onClick={() => {
              dialogRef.current?.open({
                id: record.id,
                name: record.name,
                type: record.type,
                apiKey: "",
                baseUrl: record.baseUrl,
                defaultModelKey: record.defaultModelKey,
              });
            }}
          >
            编辑
          </Typography.Link>
          <Typography.Link type="danger" onClick={() => void handleDelete(record)}>
            删除
          </Typography.Link>
        </Space>
      ),
    });

    return cols;
  }, [handleConnectivityTest, handleDelete, isNarrow, toggleExpand]);

  return (
    <div className="nify-page">
      <PageHeader
        title="模型提供商管理"
        description="配置 OpenAI、OpenAI 兼容、Claude、Gemini、Ollama 等模型提供商的接入信息与密钥。"
        extra={
          <Button
            type="primary"
            className="nify-btn-primary"
            icon={<PlusOutlined />}
            onClick={() => dialogRef.current?.open()}
          >
            新增提供商
          </Button>
        }
      />

      <PageCard>
        <NifyTable<ModelProvider>
          ref={tableRef}
          columns={columns}
          api={listApi}
          rowKey="id"
          pagination
          expandable={{
            expandedRowKeys,
            onExpandedRowsChange: (keys) =>
              setExpandedRowKeys(keys as string[]),
            expandedRowRender: (record) => {
              const enabled = record.models.filter((m) => m.is_enabled);
              if (enabled.length === 0) {
                return (
                  <span className="nify-caption">暂无已启用模型</span>
                );
              }
              return (
                <Table
                  size="small"
                  pagination={false}
                  rowKey="id"
                  dataSource={enabled}
                  columns={[
                    { title: "模型 Key", dataIndex: "model_key", width: 200 },
                    { title: "显示名", dataIndex: "display_name", width: 160 },
                    { title: "模态", dataIndex: "modality", width: 100 },
                    {
                      title: "默认",
                      dataIndex: "is_default",
                      width: 80,
                      render: (v: boolean) =>
                        v ? <Tag color="blue">默认</Tag> : "—",
                    },
                    { title: "状态", dataIndex: "status", width: 100 },
                  ]}
                />
              );
            },
            rowExpandable: (record) => record.models.length > 0,
          }}
        />
      </PageCard>

      <NifyFormDialog<ModelProviderFormValues>
        ref={dialogRef}
        title={(mode) => (mode === "edit" ? "编辑提供商" : "新增提供商")}
        width={560}
        rules={formRules}
        onSubmit={handleSubmit}
      >
        {(_form, mode) => (
          <>
            <NifyFormItem name="id" hidden>
              <Input />
            </NifyFormItem>
            <NifyFormItem name="name" label="名称">
              <Input placeholder="例如：OpenAI 生产" maxLength={64} allowClear />
            </NifyFormItem>
            <NifyFormItem name="type" label="类型">
              <Select
                placeholder="请选择类型"
                options={MODEL_PROVIDER_TYPE_OPTIONS}
                disabled={mode === "edit"}
              />
            </NifyFormItem>
            <NifyFormItem
              name="apiKey"
              label="API Key"
              dependencies={["type", "id"]}
              extra={mode === "edit" ? "留空表示不修改原密钥" : undefined}
            >
              <Input.Password
                placeholder={
                  mode === "edit" ? "留空则不修改" : "sk-...（Ollama 可留空）"
                }
                visibilityToggle
              />
            </NifyFormItem>
            <NifyFormItem
              name="baseUrl"
              label="Base URL"
              dependencies={["type"]}
              extra="OpenAI 兼容类型必填，例如 https://your-gateway/v1"
            >
              <Input placeholder="留空则使用类型默认地址" allowClear />
            </NifyFormItem>
            <NifyFormItem
              name="defaultModelKey"
              label="默认模型"
              dependencies={["type"]}
              extra="须与上游控制台中的模型 ID 一致；连通测试会调用该模型"
            >
              <Input
                placeholder="例如 qwen-flash / gpt-4o-mini"
                maxLength={128}
                allowClear
              />
            </NifyFormItem>
          </>
        )}
      </NifyFormDialog>
    </div>
  );
}

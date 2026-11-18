import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PlusOutlined } from "@ant-design/icons";
import {
  Button,
  Checkbox,
  Input,
  InputNumber,
  Select,
  Slider,
  Space,
  Switch,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  NifyFormDialog,
  NifyFormItem,
  NifyTable,
  confirmDelete,
} from "@/components";
import type { NifyFormDialogRef, NifyFormRules, NifyTableRef } from "@/components";
import { useIsNarrowScreen } from "@/hooks/useMediaQuery";
import { getAccessToken, getWorkspaceId } from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError, notifySuccess } from "@/utils/notify";
import {
  createAgent,
  deleteAgent,
  getAgent,
  getAgentList,
  listMcpToolOptions,
  listModelSelectGroups,
  updateAgent,
} from "../api";
import type {
  AgentFormValues,
  AgentRow,
  ModelSelectGroup,
  McpToolOption,
} from "../types";

/** 格式化创建时间 */
function formatCreatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const formRules: NifyFormRules<AgentFormValues> = {
  name: [{ required: true, message: "请输入名称" }],
  modelConfigId: [{ required: true, message: "请选择模型" }],
  temperature: [{ required: true, message: "请设置 temperature" }],
  maxTokens: [{ required: true, message: "请输入 max_tokens" }],
  maxContextTurns: [{ required: true, message: "请输入 max_context_turns" }],
};

const CREATE_DEFAULTS: Partial<AgentFormValues> = {
  temperature: 0.7,
  maxTokens: 2048,
  maxContextTurns: 20,
  toolIds: [],
  isEnabled: true,
  systemPrompt: "",
  description: "",
};

/** Agent 管理：NifyTable + NifyFormDialog */
export function AgentHomePage() {
  const tableRef = useRef<NifyTableRef>(null);
  const dialogRef = useRef<NifyFormDialogRef<AgentFormValues>>(null);
  const isNarrow = useIsNarrowScreen();
  const [modelGroups, setModelGroups] = useState<ModelSelectGroup[]>([]);
  const [toolOptions, setToolOptions] = useState<McpToolOption[]>([]);
  const [formTab, setFormTab] = useState("basic");

  const loadFormOptions = useCallback(async () => {
    try {
      const [models, tools] = await Promise.all([
        listModelSelectGroups(),
        listMcpToolOptions(),
      ]);
      setModelGroups(models);
      setToolOptions(tools);
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "加载选项失败");
    }
  }, []);

  useEffect(() => {
    if (!getAccessToken() || !getWorkspaceId()) return;
    void loadFormOptions();
  }, [loadFormOptions]);

  const listApi = useCallback(
    async ({ pageSize }: { page: number; pageSize: number }) => {
      if (!getAccessToken()) {
        throw new Error("请先登录（工作区页注册/登录）");
      }
      if (!getWorkspaceId()) {
        throw new Error("请先在工作区页选择或创建一个工作区");
      }
      const page = await getAgentList({ pageSize });
      const items: AgentRow[] = page.items.map((a) => ({
        id: a.id,
        name: a.name,
        description: a.description ?? "",
        modelName: a.model_name,
        modelConfigId: a.model_config_id,
        toolCount: a.tool_count,
        temperature: a.temperature,
        isEnabled: a.is_enabled,
        createdAt: a.created_at,
      }));
      return {
        items,
        next_cursor: page.next_cursor,
      };
    },
    [],
  );

  const openCreate = useCallback(async () => {
    setFormTab("basic");
    await loadFormOptions();
    // 用 reset + 微任务设默认值；不传 id 保持 create 模式需绕开 open(data) 的 edit 判定
    dialogRef.current?.open();
    queueMicrotask(() => {
      dialogRef.current?.form.setFieldsValue({
        ...CREATE_DEFAULTS,
      } as AgentFormValues);
    });
  }, [loadFormOptions]);

  const openEdit = useCallback(
    async (record: AgentRow) => {
      setFormTab("basic");
      try {
        await loadFormOptions();
        const detail = await getAgent(record.id);
        dialogRef.current?.open({
          id: detail.id,
          name: detail.name,
          description: detail.description ?? "",
          modelConfigId: detail.model_config_id,
          systemPrompt: detail.system_prompt ?? "",
          temperature: detail.temperature,
          maxTokens: detail.max_tokens,
          maxContextTurns: detail.max_context_turns,
          toolIds: detail.tool_ids ?? [],
          isEnabled: detail.is_enabled,
        });
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "加载 Agent 失败");
      }
    },
    [loadFormOptions],
  );

  const handleSubmit = useCallback(
    async (values: AgentFormValues, mode: "create" | "edit") => {
      try {
        const body = {
          name: values.name.trim(),
          description: values.description?.trim() || null,
          system_prompt: values.systemPrompt?.trim() || null,
          model_config_id: values.modelConfigId,
          temperature: values.temperature,
          max_tokens: values.maxTokens,
          max_context_turns: values.maxContextTurns,
          tool_ids: values.toolIds ?? [],
          is_enabled: values.isEnabled ?? true,
        };
        if (mode === "edit") {
          if (!values.id) throw new Error("缺少 Agent ID");
          await updateAgent(values.id, body);
          notifySuccess("已更新 Agent");
        } else {
          await createAgent(body);
          notifySuccess("已新增 Agent");
        }
        await tableRef.current?.refresh();
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "保存失败");
        throw err;
      }
    },
    [],
  );

  const handleDelete = useCallback(async (record: AgentRow) => {
    try {
      await confirmDelete({
        content: `确认删除 Agent「${record.name}」？删除后可同名重建。`,
        api: () => deleteAgent(record.id),
      });
      await tableRef.current?.refresh();
    } catch {
      // 取消或失败已提示
    }
  }, []);

  const columns: ColumnsType<AgentRow> = useMemo(() => {
    const cols: ColumnsType<AgentRow> = [
      {
        title: "名称",
        dataIndex: "name",
        width: 160,
        ellipsis: true,
      },
      {
        title: "关联模型",
        dataIndex: "modelName",
        width: 160,
        ellipsis: true,
      },
      {
        title: "工具数量",
        dataIndex: "toolCount",
        width: 90,
      },
      {
        title: "temperature",
        dataIndex: "temperature",
        width: 110,
        render: (v: number) => (Number.isFinite(v) ? v.toFixed(1) : "—"),
      },
      {
        title: "启用",
        dataIndex: "isEnabled",
        width: 80,
        render: (enabled: boolean) =>
          enabled ? (
            <Tag color="success">启用</Tag>
          ) : (
            <Tag>禁用</Tag>
          ),
      },
    ];

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
      width: isNarrow ? 120 : 140,
      fixed: "right",
      render: (_, record) => (
        <Space size="small">
          <Typography.Link onClick={() => void openEdit(record)}>
            编辑
          </Typography.Link>
          <Typography.Link type="danger" onClick={() => void handleDelete(record)}>
            删除
          </Typography.Link>
        </Space>
      ),
    });

    return cols;
  }, [handleDelete, isNarrow, openEdit]);

  return (
    <div className="nify-page">
      <PageHeader
        title="Agent 管理"
        description="配置提示词、模型参数与 MCP 工具绑定。"
        extra={
          <Button
            type="primary"
            className="nify-btn-primary"
            icon={<PlusOutlined />}
            onClick={() => void openCreate()}
          >
            新建 Agent
          </Button>
        }
      />

      <PageCard>
        <NifyTable<AgentRow>
          ref={tableRef}
          columns={columns}
          api={listApi}
          rowKey="id"
          pagination
        />
      </PageCard>

      <NifyFormDialog<AgentFormValues>
        ref={dialogRef}
        title={(mode) => (mode === "edit" ? "编辑 Agent" : "新建 Agent")}
        width={720}
        rules={formRules}
        onSubmit={handleSubmit}
      >
        {(_form, mode) => (
          <>
            <NifyFormItem name="id" hidden>
              <Input />
            </NifyFormItem>

            <Tabs
              activeKey={formTab}
              onChange={setFormTab}
              items={[
                {
                  key: "basic",
                  label: "基本配置",
                  children: (
                    <>
                      <NifyFormItem name="name" label="名称">
                        <Input
                          placeholder="例如：客服助手"
                          maxLength={128}
                          allowClear
                        />
                      </NifyFormItem>
                      <NifyFormItem name="description" label="描述">
                        <Input.TextArea
                          placeholder="简要说明用途"
                          maxLength={512}
                          rows={2}
                          allowClear
                        />
                      </NifyFormItem>
                      <NifyFormItem name="modelConfigId" label="模型">
                        <Select
                          placeholder={
                            modelGroups.length
                              ? "按供应商选择可用模型"
                              : "暂无可用模型，请先在「模型」页配置"
                          }
                          options={modelGroups}
                          showSearch
                          optionFilterProp="label"
                          disabled={modelGroups.length === 0}
                        />
                      </NifyFormItem>
                      <NifyFormItem name="systemPrompt" label="System Prompt">
                        <Input.TextArea
                          placeholder="设定角色、语气与约束…"
                          rows={6}
                          style={{ minHeight: 144 }}
                          allowClear
                        />
                      </NifyFormItem>
                      <NifyFormItem
                        name="temperature"
                        label="temperature"
                        initialValue={0.7}
                      >
                        <Slider
                          min={0}
                          max={1}
                          step={0.1}
                          marks={{ 0: "0", 0.5: "0.5", 1: "1" }}
                          tooltip={{ formatter: (v) => String(v ?? 0) }}
                        />
                      </NifyFormItem>
                      <NifyFormItem
                        name="maxTokens"
                        label="max_tokens"
                        initialValue={2048}
                      >
                        <InputNumber
                          min={1}
                          max={128000}
                          style={{ width: "100%" }}
                        />
                      </NifyFormItem>
                      <NifyFormItem
                        name="maxContextTurns"
                        label="max_context_turns"
                        initialValue={20}
                      >
                        <InputNumber
                          min={1}
                          max={200}
                          style={{ width: "100%" }}
                        />
                      </NifyFormItem>
                      <NifyFormItem
                        name="isEnabled"
                        label="启用"
                        valuePropName="checked"
                        initialValue={true}
                      >
                        <Switch
                          checkedChildren="启用"
                          unCheckedChildren="禁用"
                        />
                      </NifyFormItem>
                    </>
                  ),
                },
                {
                  key: "tools",
                  label: `工具绑定${toolOptions.length ? `（${toolOptions.length}）` : ""}`,
                  children: (
                    <>
                      {toolOptions.length === 0 ? (
                        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
                          暂无可用 MCP 服务。配置 MCP 后重新打开本弹窗即可勾选绑定。
                          {mode === "edit"
                            ? " 已绑定的工具 ID 仍会保留，直至有可选项后重新保存。"
                            : ""}
                        </Typography.Paragraph>
                      ) : null}
                      <NifyFormItem
                        name="toolIds"
                        label="MCP 工具"
                        initialValue={[]}
                        extra="多选绑定到该 Agent"
                      >
                        <Checkbox.Group
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 8,
                          }}
                          options={toolOptions.map((t) => ({
                            label: `${t.name}（${t.transport}）`,
                            value: t.id,
                          }))}
                        />
                      </NifyFormItem>
                    </>
                  ),
                },
              ]}
            />
          </>
        )}
      </NifyFormDialog>
    </div>
  );
}

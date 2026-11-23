import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Space,
  Switch,
  Typography,
} from "antd";
import type { McpTool } from "../api";
import { debugMcpServer } from "../api";
import { notifyError } from "@/shared/notify";

const { Text, Paragraph, Title } = Typography;

type JsonSchema = {
  type?: string | string[];
  properties?: Record<string, JsonSchema>;
  required?: string[];
  description?: string;
  default?: unknown;
  items?: JsonSchema;
};

export type DebugCallRecord = {
  id: string;
  toolName: string;
  arguments: Record<string, unknown>;
  result: string;
  elapsedMs: number;
  at: string;
  ok: boolean;
};

type Props = {
  serverId: string;
  tools: McpTool[];
  toolsError?: string | null;
};

/** 从 JSON Schema type 取主类型 */
function primaryType(schema: JsonSchema | undefined): string {
  const t = schema?.type;
  if (Array.isArray(t)) {
    return String(t.find((x) => x !== "null") || t[0] || "string");
  }
  return String(t || "string");
}

/** 按 inputSchema.properties 动态生成表单字段 */
function SchemaFields({ schema }: { schema: JsonSchema | null }) {
  const properties = schema?.properties || {};
  const required = new Set(schema?.required || []);
  const keys = Object.keys(properties);

  if (keys.length === 0) {
    return (
      <Alert
        type="info"
        showIcon
        message="该工具无参数（或 schema 未声明 properties）"
        style={{ marginBottom: 12 }}
      />
    );
  }

  return (
    <>
      {keys.map((key) => {
        const prop = properties[key] || {};
        const t = primaryType(prop);
        const isRequired = required.has(key);
        const label = (
          <span>
            {key}
            {isRequired ? (
              <Text type="danger" style={{ marginLeft: 4 }}>
                *
              </Text>
            ) : null}
          </span>
        );
        const extra = prop.description || undefined;

        if (t === "number" || t === "integer") {
          return (
            <Form.Item
              key={key}
              name={key}
              label={label}
              extra={extra}
              rules={
                isRequired
                  ? [{ required: true, message: `请填写 ${key}` }]
                  : undefined
              }
            >
              <InputNumber style={{ width: "100%" }} />
            </Form.Item>
          );
        }

        if (t === "boolean") {
          return (
            <Form.Item
              key={key}
              name={key}
              label={label}
              extra={extra}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          );
        }

        // object / array / 其它：用 JSON 文本
        if (t === "object" || t === "array") {
          return (
            <Form.Item
              key={key}
              name={key}
              label={label}
              extra={extra || "请填写 JSON"}
              rules={
                isRequired
                  ? [{ required: true, message: `请填写 ${key}` }]
                  : undefined
              }
            >
              <Input.TextArea rows={3} placeholder='例如 {"a":1} 或 [1,2]' />
            </Form.Item>
          );
        }

        return (
          <Form.Item
            key={key}
            name={key}
            label={label}
            extra={extra}
            rules={
              isRequired
                ? [{ required: true, message: `请填写 ${key}` }]
                : undefined
            }
          >
            <Input allowClear />
          </Form.Item>
        );
      })}
    </>
  );
}

function parseArguments(
  values: Record<string, unknown>,
  schema: JsonSchema | null,
): Record<string, unknown> {
  const properties = schema?.properties || {};
  const out: Record<string, unknown> = {};
  for (const [key, raw] of Object.entries(values)) {
    if (raw === undefined || raw === null || raw === "") continue;
    const prop = properties[key];
    const t = primaryType(prop);
    if (t === "object" || t === "array") {
      if (typeof raw === "string") {
        out[key] = JSON.parse(raw);
      } else {
        out[key] = raw;
      }
      continue;
    }
    if (t === "boolean" && typeof raw === "string") {
      const lower = raw.trim().toLowerCase();
      out[key] = lower === "true" || lower === "1";
      continue;
    }
    out[key] = raw;
  }
  return out;
}

/** MCP 工具调试面板：左工具列表，右参数表单 + 结果 */
export function McpDebugPanel({ serverId, tools, toolsError }: Props) {
  const [selectedName, setSelectedName] = useState<string | null>(
    tools[0]?.name ?? null,
  );
  const [form] = Form.useForm<Record<string, unknown>>();
  const [loading, setLoading] = useState(false);
  const [latest, setLatest] = useState<DebugCallRecord | null>(null);
  const [history, setHistory] = useState<DebugCallRecord[]>([]);

  const selected = useMemo(
    () => tools.find((t) => t.name === selectedName) || null,
    [tools, selectedName],
  );

  const inputSchema = useMemo(() => {
    const raw = selected?.input_schema;
    if (!raw || typeof raw !== "object") return null;
    return raw as JsonSchema;
  }, [selected]);

  useEffect(() => {
    if (!tools.length) {
      setSelectedName(null);
      return;
    }
    if (!selectedName || !tools.some((t) => t.name === selectedName)) {
      setSelectedName(tools[0].name);
    }
  }, [tools, selectedName]);

  useEffect(() => {
    form.resetFields();
    if (!inputSchema?.properties) return;
    const initials: Record<string, unknown> = {};
    for (const [key, prop] of Object.entries(inputSchema.properties)) {
      if (prop && "default" in prop && prop.default !== undefined) {
        initials[key] = prop.default;
      }
    }
    if (Object.keys(initials).length) {
      // JSON Schema default 类型宽于 Form Store；此处仅预填调试表单
      form.setFieldsValue(initials as Record<string, string | number | boolean>);
    }
  }, [selectedName, inputSchema, form]);

  const handleCall = useCallback(async () => {
    if (!selected || loading) return;
    try {
      const values = await form.validateFields();
      let args: Record<string, unknown>;
      try {
        args = parseArguments(values, inputSchema);
      } catch {
        notifyError("参数 JSON 格式无效");
        return;
      }
      setLoading(true);
      const res = await debugMcpServer(serverId, {
        tool_name: selected.name,
        arguments: args,
      });
      const record: DebugCallRecord = {
        id: `${Date.now()}`,
        toolName: selected.name,
        arguments: args,
        result: res.result,
        elapsedMs: res.elapsed_ms,
        at: new Date().toISOString(),
        ok: true,
      };
      setLatest(record);
      setHistory((prev) => [record, ...prev].slice(0, 5));
    } catch (err) {
      const message = err instanceof Error ? err.message : "调用失败";
      notifyError(message);
      const record: DebugCallRecord = {
        id: `${Date.now()}`,
        toolName: selected.name,
        arguments: form.getFieldsValue(),
        result: message,
        elapsedMs: 0,
        at: new Date().toISOString(),
        ok: false,
      };
      setLatest(record);
      setHistory((prev) => [record, ...prev].slice(0, 5));
    } finally {
      setLoading(false);
    }
  }, [selected, loading, form, inputSchema, serverId]);

  if (toolsError) {
    return (
      <Alert
        type="warning"
        showIcon
        message="工具列表加载失败"
        description={toolsError}
      />
    );
  }

  if (!tools.length) {
    return (
      <Empty description="暂无工具，请先确认 MCP Server 可连通" />
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "240px 1fr",
        gap: 16,
        minHeight: 420,
      }}
    >
      <div
        style={{
          border: "1px solid var(--ant-color-border-secondary, #f0f0f0)",
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "10px 12px", borderBottom: "1px solid #f0f0f0" }}>
          <Text strong>工具列表</Text>
        </div>
        <List
          size="small"
          dataSource={tools}
          renderItem={(item) => (
            <List.Item
              style={{
                cursor: "pointer",
                padding: "10px 12px",
                background:
                  item.name === selectedName
                    ? "rgba(22, 119, 255, 0.06)"
                    : undefined,
              }}
              onClick={() => setSelectedName(item.name)}
            >
              <Text
                ellipsis
                style={{
                  width: "100%",
                  fontWeight: item.name === selectedName ? 600 : 400,
                }}
              >
                {item.name}
              </Text>
            </List.Item>
          )}
        />
      </div>

      <div>
        {selected ? (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <div>
              <Title level={5} style={{ margin: 0 }}>
                {selected.name}
              </Title>
              <Paragraph
                type="secondary"
                style={{ marginTop: 8, marginBottom: 0, whiteSpace: "pre-wrap" }}
              >
                {selected.description || "（无 description）"}
              </Paragraph>
            </div>

            <Form form={form} layout="vertical" disabled={loading}>
              <SchemaFields schema={inputSchema} />
              <Form.Item>
                <Button
                  type="primary"
                  className="nify-btn-primary"
                  loading={loading}
                  disabled={loading}
                  onClick={() => void handleCall()}
                >
                  调用
                </Button>
              </Form.Item>
            </Form>

            <div>
              <Text strong>本次结果</Text>
              {latest ? (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">
                    耗时 {latest.elapsedMs} ms
                    {latest.ok ? "" : " · 失败"}
                  </Text>
                  <pre
                    style={{
                      marginTop: 8,
                      padding: 12,
                      background: "#fafafa",
                      borderRadius: 8,
                      maxHeight: 240,
                      overflow: "auto",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {latest.result}
                  </pre>
                </div>
              ) : (
                <Paragraph type="secondary" style={{ marginTop: 8 }}>
                  尚未调用
                </Paragraph>
              )}
            </div>

            <div>
              <Text strong>最近调用（最多 5 次）</Text>
              {history.length === 0 ? (
                <Paragraph type="secondary" style={{ marginTop: 8 }}>
                  暂无记录
                </Paragraph>
              ) : (
                <List
                  size="small"
                  style={{ marginTop: 8 }}
                  dataSource={history}
                  renderItem={(item) => (
                    <List.Item>
                      <Space direction="vertical" size={0} style={{ width: "100%" }}>
                        <Text>
                          {item.toolName}
                          <Text type="secondary">
                            {" "}
                            · {item.elapsedMs} ms ·{" "}
                            {new Date(item.at).toLocaleTimeString()}
                            {item.ok ? "" : " · 失败"}
                          </Text>
                        </Text>
                        <Text
                          type="secondary"
                          ellipsis
                          style={{ maxWidth: "100%" }}
                        >
                          {item.result}
                        </Text>
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </div>
          </Space>
        ) : (
          <Empty description="请选择左侧工具" />
        )}
      </div>
    </div>
  );
}

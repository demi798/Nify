import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Form, Input, Space } from "antd";
import { getAccessToken, getWorkspaceId } from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError, notifySuccess } from "@/shared/notify";
import { createWorkflow } from "../api";
import type { WorkflowCreateBody, WorkflowEdgeIn, WorkflowNodeIn } from "../api";
import { CUSTOMER_SERVICE_WORKFLOW_SAMPLE_JSON } from "../sampleConfig";
import type { WorkflowCreateFormValues } from "../types";

type GraphConfig = {
  nodes?: WorkflowNodeIn[];
  edges?: WorkflowEdgeIn[];
  is_enabled?: boolean;
};

/** 解析并校验工作流配置 JSON */
function parseGraphConfig(raw: string): GraphConfig {
  const text = (raw || "").trim();
  if (!text) {
    throw new Error("工作流配置不能为空");
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("工作流配置不是合法 JSON，请检查语法");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("工作流配置必须是 JSON 对象（含 nodes / edges）");
  }
  const obj = parsed as GraphConfig;
  if (!Array.isArray(obj.nodes)) {
    throw new Error("工作流配置缺少 nodes 数组");
  }
  if (!Array.isArray(obj.edges)) {
    throw new Error("工作流配置缺少 edges 数组");
  }
  return obj;
}

/** 工作流创建页：名称 / 描述 / JSON 配置 */
export function WorkflowCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<WorkflowCreateFormValues>();
  const [submitting, setSubmitting] = useState(false);

  const initialValues = useMemo<WorkflowCreateFormValues>(
    () => ({
      name: "智能客服分类",
      description: "开始 → 知识库检索 → 条件分流 → LLM 答复（示例可改）",
      configJson: CUSTOMER_SERVICE_WORKFLOW_SAMPLE_JSON,
    }),
    [],
  );

  const handleFormat = () => {
    const raw = form.getFieldValue("configJson") as string;
    try {
      const obj = JSON.parse((raw || "").trim());
      form.setFieldsValue({
        configJson: JSON.stringify(obj, null, 2),
      });
      form.setFields([{ name: "configJson", errors: [] }]);
      notifySuccess("已格式化");
    } catch {
      notifyError("当前内容不是合法 JSON，无法格式化");
      form.setFields([
        { name: "configJson", errors: ["不是合法 JSON，无法格式化"] },
      ]);
    }
  };

  const onFinish = async (values: WorkflowCreateFormValues) => {
    if (!getAccessToken()) {
      notifyError("请先登录");
      return;
    }
    if (!getWorkspaceId()) {
      notifyError("请先在工作区页选择或创建一个工作区");
      return;
    }

    let graph: GraphConfig;
    try {
      graph = parseGraphConfig(values.configJson);
      form.setFields([{ name: "configJson", errors: [] }]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "JSON 校验失败";
      form.setFields([{ name: "configJson", errors: [msg] }]);
      notifyError(msg);
      return;
    }

    const body: WorkflowCreateBody = {
      name: values.name.trim(),
      description: (values.description || "").trim() || null,
      is_enabled: graph.is_enabled !== false,
      nodes: graph.nodes ?? [],
      edges: graph.edges ?? [],
    };

    setSubmitting(true);
    try {
      await createWorkflow(body);
      notifySuccess("工作流已创建");
      navigate("/workflows");
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="nify-page">
      <PageHeader
        title="新建工作流"
        description="填写名称与图配置 JSON；示例为智能客服分类流程。"
        extra={
          <Button onClick={() => navigate("/workflows")}>返回列表</Button>
        }
      />
      <PageCard>
        <Form<WorkflowCreateFormValues>
          form={form}
          layout="vertical"
          initialValues={initialValues}
          onFinish={(v) => void onFinish(v)}
          style={{ maxWidth: 880 }}
        >
          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true, message: "请输入名称" }]}
          >
            <Input maxLength={128} placeholder="例如：智能客服分类" />
          </Form.Item>

          <Form.Item label="描述" name="description">
            <Input.TextArea
              rows={2}
              maxLength={512}
              placeholder="可选，简要说明流程用途"
              showCount
            />
          </Form.Item>

          <Form.Item
            label="工作流配置"
            name="configJson"
            rules={[{ required: true, message: "请填写工作流配置 JSON" }]}
            extra="JSON 需包含 nodes、edges；提交前请替换 knowledge_base_ids / agent_id 为真实 ID。"
          >
            <Input.TextArea
              rows={20}
              spellCheck={false}
              style={{
                fontFamily:
                  "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                fontSize: 13,
              }}
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button onClick={handleFormat}>格式化</Button>
              <Button
                type="primary"
                className="nify-btn-primary"
                htmlType="submit"
                loading={submitting}
              >
                提交
              </Button>
              <Button onClick={() => navigate("/workflows")}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </PageCard>
    </div>
  );
}

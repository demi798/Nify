/**
 * 预填示例：智能客服分类工作流（Nify 节点类型）。
 *
 * 流程：开始 → 知识库检索 → 条件分流
 *   ├─ 命中 → LLM 引用资料答复 → 结束
 *   └─ 未命中 → LLM 安抚/转人工话术 → 结束
 *
 * 提交前请把 knowledge_base_ids / agent_id 换成当前工作区真实 ID。
 */
export const CUSTOMER_SERVICE_WORKFLOW_SAMPLE = {
  nodes: [
    {
      key: "start",
      type: "start",
      name: "开始",
      config: {},
      position: { x: 40, y: 200 },
    },
    {
      key: "kb1",
      type: "knowledge",
      name: "知识库检索",
      config: {
        knowledge_base_ids: [],
        top_k: 5,
      },
      position: { x: 240, y: 200 },
    },
    {
      key: "cond1",
      type: "condition",
      name: "是否命中资料",
      config: {
        expression: "nodes.kb1.chunks",
      },
      position: { x: 460, y: 200 },
    },
    {
      key: "llm_hit",
      type: "llm",
      name: "命中答复",
      config: {
        agent_id: null,
        system_prompt:
          "你是 Nify 智能客服。请严格依据「参考资料」回答用户问题，语气专业友好、简洁明了。资料不足时明确说明并建议联系人工客服，禁止编造。",
        temperature: 0.3,
      },
      position: { x: 700, y: 80 },
    },
    {
      key: "llm_miss",
      type: "llm",
      name: "未命中安抚",
      config: {
        agent_id: null,
        system_prompt:
          "你是 Nify 智能客服。当前知识库未检索到相关资料。请礼貌说明暂时无法从手册确认，引导用户补充信息或转人工客服，不要编造政策细节。",
        temperature: 0.4,
      },
      position: { x: 700, y: 320 },
    },
    {
      key: "end",
      type: "end",
      name: "结束",
      config: {},
      position: { x: 940, y: 200 },
    },
  ],
  edges: [
    { key: "e1", source: "start", target: "kb1" },
    { key: "e2", source: "kb1", target: "cond1" },
    {
      key: "e3",
      source: "cond1",
      target: "llm_hit",
      source_handle: "true",
      label: "命中",
    },
    {
      key: "e4",
      source: "cond1",
      target: "llm_miss",
      source_handle: "false",
      label: "未命中",
    },
    { key: "e5", source: "llm_hit", target: "end" },
    { key: "e6", source: "llm_miss", target: "end" },
  ],
} as const;

/** 预填到文本框的美化 JSON */
export const CUSTOMER_SERVICE_WORKFLOW_SAMPLE_JSON = JSON.stringify(
  CUSTOMER_SERVICE_WORKFLOW_SAMPLE,
  null,
  2,
);

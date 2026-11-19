/** agent 模块展示类型。 */

export type AgentKnowledgeBaseBrief = {
  id: string;
  name: string;
};

export type AgentRow = {
  id: string;
  name: string;
  description: string;
  modelName: string;
  modelConfigId: string;
  toolCount: number;
  knowledgeBases: AgentKnowledgeBaseBrief[];
  temperature: number;
  isEnabled: boolean;
  createdAt: string;
};

export type AgentFormValues = {
  id?: string;
  name: string;
  description?: string;
  modelConfigId: string;
  systemPrompt?: string;
  temperature: number;
  maxTokens: number;
  maxContextTurns: number;
  toolIds: string[];
  knowledgeBaseIds: string[];
  isEnabled: boolean;
};

export type KnowledgeBaseOption = {
  id: string;
  name: string;
};

/** 按供应商分组的模型下拉选项 */
export type ModelSelectGroup = {
  label: string;
  options: { label: string; value: string }[];
};

export type McpToolOption = {
  id: string;
  name: string;
  transport: string;
};

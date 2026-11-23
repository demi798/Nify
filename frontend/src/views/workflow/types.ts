/** workflow 模块前端展示类型（与后端 schemas 对齐）。 */

/** 列表行：状态由 is_enabled 映射为 DRAFT / PUBLISHED */
export type WorkflowRow = {
  id: string;
  name: string;
  description: string;
  status: "DRAFT" | "PUBLISHED";
  isEnabled: boolean;
  nodeCount: number;
  edgeCount: number;
  createdAt: string;
};

/** 创建页表单 */
export type WorkflowCreateFormValues = {
  name: string;
  description?: string;
  /** 图配置 JSON 字符串（含 nodes / edges） */
  configJson: string;
};

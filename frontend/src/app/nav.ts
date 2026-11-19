/** 侧栏与面包屑共用的导航元数据 */

export type NavItem = {
  path: string;
  label: string;
  description: string;
};

export const NAV_ITEMS: NavItem[] = [
  {
    path: "/conversation",
    label: "对话",
    description: "与 Agent 进行流式对话与工具调用。",
  },
  {
    path: "/agents",
    label: "Agent",
    description: "配置提示词、模型与知识库 / 工具绑定。",
  },
  {
    path: "/knowledge-bases",
    label: "知识库",
    description: "上传文档、分块检索，支撑 RAG。",
  },
  {
    path: "/workflows",
    label: "工作流",
    description: "编排简版工作流定义与运行。",
  },
  {
    path: "/model-providers",
    label: "模型",
    description: "管理模型提供商、密钥与默认模型。",
  },
  {
    path: "/mcp",
    label: "MCP",
    description: "配置 MCP 连接与白名单工具。",
  },
  {
    path: "/identity",
    label: "工作区",
    description: "登录注册与工作区成员管理（CRUD 演示）。",
  },
];

export function findNavItem(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find(
    (item) => pathname === item.path || pathname.startsWith(`${item.path}/`),
  );
}

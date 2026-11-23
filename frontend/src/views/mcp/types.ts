/** mcp 前端展示类型。 */

export type McpTransport = "http" | "sse" | "stdio";

export type McpServerRow = {
  id: string;
  name: string;
  transport: McpTransport | string;
  endpoint: string;
  isEnabled: boolean;
  hasAuth: boolean;
  createdAt: string;
};

export type McpServerFormValues = {
  id?: string;
  name: string;
  transport: McpTransport;
  endpoint: string;
  authToken?: string;
  isEnabled: boolean;
};

export const MCP_TRANSPORT_OPTIONS = [
  { label: "HTTP（Streamable）", value: "http" as const },
  { label: "SSE", value: "sse" as const },
  { label: "stdio", value: "stdio" as const },
];

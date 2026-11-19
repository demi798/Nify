/** conversation 模块展示类型。 */

export type ChatBubble = {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  status?: string;
  streaming?: boolean;
};

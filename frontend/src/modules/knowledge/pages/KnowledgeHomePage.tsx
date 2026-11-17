import { Typography } from "antd";

/** 知识库 模块首页占位 */
export function KnowledgeHomePage() {
  return (
    <div>
      <Typography.Title level={3}>知识库</Typography.Title>
      <Typography.Paragraph type="secondary">
        模块目录已按 CLAUDE.md 初始化，业务页面待实现。
      </Typography.Paragraph>
    </div>
  );
}

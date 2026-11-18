import { Button } from "antd";
import { PageCard, PageHeader } from "@/shared/components";

/** MCP 模块首页占位 */
export function McpHomePage() {
  return (
    <div className="nify-page">
      <PageHeader
        title="MCP"
        description="配置 MCP 连接与白名单工具。"
        extra={
          <Button type="primary" className="nify-btn-primary">
            添加连接
          </Button>
        }
      />
      <PageCard>
        <p className="nify-muted">业务页面待实现。</p>
      </PageCard>
    </div>
  );
}

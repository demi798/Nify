import { Button } from "antd";
import { PageCard, PageHeader } from "@/shared/components";

/** 对话 模块首页占位 */
export function ConversationHomePage() {
  return (
    <div className="nify-page">
      <PageHeader
        title="对话"
        description="与 Agent 进行流式对话与工具调用。"
        extra={
          <Button type="primary" className="nify-btn-primary">
            新建对话
          </Button>
        }
      />
      <PageCard>
        <p className="nify-muted">业务页面待实现。</p>
      </PageCard>
    </div>
  );
}

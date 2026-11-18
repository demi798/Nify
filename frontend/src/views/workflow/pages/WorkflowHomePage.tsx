import { Button } from "antd";
import { PageCard, PageHeader } from "@/shared/components";

/** 工作流 模块首页占位 */
export function WorkflowHomePage() {
  return (
    <div className="nify-page">
      <PageHeader
        title="工作流"
        description="编排简版工作流定义与运行。"
        extra={
          <Button type="primary" className="nify-btn-primary">
            新建工作流
          </Button>
        }
      />
      <PageCard>
        <p className="nify-muted">业务页面待实现。</p>
      </PageCard>
    </div>
  );
}

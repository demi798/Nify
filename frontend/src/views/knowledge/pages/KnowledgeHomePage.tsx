import { Button } from "antd";
import { PageCard, PageHeader } from "@/shared/components";

/** 知识库 模块首页占位 */
export function KnowledgeHomePage() {
  return (
    <div className="nify-page">
      <PageHeader
        title="知识库"
        description="上传文档、分块检索，支撑 RAG。"
        extra={
          <>
            <Button className="nify-btn-secondary">导入</Button>
            <Button type="primary" className="nify-btn-primary">
              新建知识库
            </Button>
          </>
        }
      />
      <PageCard>
        <p className="nify-muted">业务页面待实现。</p>
      </PageCard>
    </div>
  );
}

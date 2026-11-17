import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/app/layout";
import { IdentityHomePage } from "@/modules/identity";
import { ModelProviderHomePage } from "@/modules/model_provider";
import { AgentHomePage } from "@/modules/agent";
import { ConversationHomePage } from "@/modules/conversation";
import { KnowledgeHomePage } from "@/modules/knowledge";
import { WorkflowHomePage } from "@/modules/workflow";
import { McpHomePage } from "@/modules/mcp";

/** 统一路由配置（CLAUDE.md：routes.tsx） */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/identity" replace />} />
        <Route path="identity" element={<IdentityHomePage />} />

        <Route path="model-providers" element={<ModelProviderHomePage />} />
        <Route path="agents" element={<AgentHomePage />} />
        <Route path="conversation" element={<ConversationHomePage />} />
        <Route path="knowledge" element={<KnowledgeHomePage />} />
        <Route path="workflows" element={<WorkflowHomePage />} />
        <Route path="mcp" element={<McpHomePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

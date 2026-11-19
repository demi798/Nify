import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/app/layout";
import { RequireAuth } from "@/app/RequireAuth";
import {
  IdentityHomePage,
  LoginPage,
  RegisterPage,
} from "@/views/identity";
import { ModelProviderHomePage } from "@/views/model_provider";
import { AgentHomePage } from "@/views/agent";
import { ConversationHomePage } from "@/views/conversation";
import {
  KnowledgeDocumentsPage,
  KnowledgeHomePage,
} from "@/views/knowledge";
import { WorkflowHomePage } from "@/views/workflow";
import { McpHomePage } from "@/views/mcp";
import { getAccessToken } from "@/shared/api-client";

/** 根路径：已登录进系统，未登录进登录页 */
function RootRedirect() {
  return (
    <Navigate to={getAccessToken() ? "/conversation" : "/login"} replace />
  );
}

/** 统一路由配置（CLAUDE.md：routes.tsx） */
export function AppRoutes() {
  return (
    <Routes>
      {/* 系统外：登录 / 注册 */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* 系统内：需登录 */}
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<RootRedirect />} />
        <Route path="identity" element={<IdentityHomePage />} />
        <Route path="model-providers" element={<ModelProviderHomePage />} />
        <Route path="agents" element={<AgentHomePage />} />
        <Route path="conversation" element={<ConversationHomePage />} />
        <Route path="knowledge-bases" element={<KnowledgeHomePage />} />
        <Route
          path="knowledge-bases/:kbId/documents"
          element={<KnowledgeDocumentsPage />}
        />
        {/* 兼容旧路径 */}
        <Route
          path="knowledge"
          element={<Navigate to="/knowledge-bases" replace />}
        />
        <Route path="workflows" element={<WorkflowHomePage />} />
        <Route path="mcp" element={<McpHomePage />} />
      </Route>

      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}

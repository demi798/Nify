import { Layout, Menu, Typography } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/conversation", label: "对话" },
  { key: "/agents", label: "Agent" },
  { key: "/knowledge", label: "知识库" },
  { key: "/workflows", label: "工作流" },
  { key: "/model-providers", label: "模型" },
  { key: "/mcp", label: "MCP" },
  { key: "/identity", label: "工作区" },
];

/** 应用壳布局 */
export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider breakpoint="lg" collapsedWidth={64}>
        <div style={{ padding: "16px", color: "#fff", fontWeight: 600 }}>Nify</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: "#fff", paddingInline: 24 }}>
          <Typography.Text type="secondary">内部 AI Agent 平台</Typography.Text>
        </Header>
        <Content style={{ margin: 24 }}>
          <div
            style={{
              background: "#fff",
              padding: 24,
              minHeight: 360,
              borderRadius: 8,
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}

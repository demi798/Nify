import { useEffect, useMemo, useState } from "react";
import {
  Avatar,
  Breadcrumb,
  Button,
  Layout,
  Menu,
  Space,
  Tooltip,
  Typography,
} from "antd";
import {
  ApiOutlined,
  ApartmentOutlined,
  BookOutlined,
  HomeOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { findNavItem } from "@/app/nav";
import { useIsNarrowScreen } from "@/hooks/useMediaQuery";
import {
  clearAuthSession,
  getStoredUser,
} from "@/shared/api-client";

const { Header, Sider, Content } = Layout;

const APP_VERSION = "v0.1.0";

type MenuItem = Required<MenuProps>["items"][number];

const menuItems: MenuItem[] = [
  { key: "/conversation", icon: <MessageOutlined />, label: "对话" },
  { key: "/agents", icon: <UserOutlined />, label: "Agent" },
  { key: "/knowledge-bases", icon: <BookOutlined />, label: "知识库" },
  { key: "/workflows", icon: <ApartmentOutlined />, label: "工作流" },
  { key: "/model-providers", icon: <SettingOutlined />, label: "模型" },
  { key: "/mcp", icon: <ApiOutlined />, label: "MCP" },
  { key: "/identity", icon: <TeamOutlined />, label: "工作区" },
];

/** 应用壳：深色侧栏 + 顶栏面包屑/用户 + 浅灰内容区 */
export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  // 宽度 < 1200px 自动折叠为图标模式；≥1200px 自动展开
  const isNarrow = useIsNarrowScreen();
  const [collapsed, setCollapsed] = useState(isNarrow);
  const user = getStoredUser();

  useEffect(() => {
    setCollapsed(isNarrow);
  }, [isNarrow]);

  const currentNav = useMemo(
    () => findNavItem(location.pathname),
    [location.pathname],
  );

  const selectedKeys = useMemo(() => {
    if (currentNav) return [currentNav.path];
    return [location.pathname];
  }, [currentNav, location.pathname]);

  const breadcrumbItems = useMemo(
    () => [
      {
        title: (
          <Link to="/conversation">
            <HomeOutlined />
          </Link>
        ),
      },
      ...(currentNav
        ? [
            {
              title: currentNav.label,
            },
          ]
        : [
            {
              title: "页面",
            },
          ]),
    ],
    [currentNav],
  );

  return (
    <Layout className="nify-shell">
      <Sider
        className="nify-sider"
        width={240}
        collapsedWidth={72}
        collapsible
        collapsed={collapsed}
        trigger={null}
      >
        <div className={`nify-brand${collapsed ? " nify-brand--collapsed" : ""}`}>
          <div className="nify-brand__text">
            <div className="nify-brand__name">Nify</div>
            {!collapsed ? (
              <div className="nify-brand__tagline">AI Agent Platform</div>
            ) : null}
          </div>
        </div>

        <div className="nify-sider__menu">
          <Menu
            theme="dark"
            mode="inline"
            inlineCollapsed={collapsed}
            selectedKeys={selectedKeys}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
          />
        </div>

        <div className="nify-sider__footer">
          <Tooltip
            title={collapsed ? "展开侧栏" : "折叠侧栏"}
            placement="right"
          >
            <Button
              type="text"
              className="nify-sider__collapse"
              aria-label={collapsed ? "展开侧栏" : "折叠侧栏"}
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed((v) => !v)}
            />
          </Tooltip>
          {!collapsed ? (
            <Typography.Text className="nify-sider__version">
              {APP_VERSION}
            </Typography.Text>
          ) : (
            <Typography.Text className="nify-sider__version nify-sider__version--compact">
              {APP_VERSION.replace("v", "")}
            </Typography.Text>
          )}
        </div>
      </Sider>

      <Layout className="nify-main">
        <Header className="nify-header">
          <Breadcrumb
            className="nify-header__breadcrumb"
            items={breadcrumbItems}
          />
          <Space className="nify-header__user" size={12}>
            <Avatar
              size={32}
              icon={<UserOutlined />}
              className="nify-header__avatar"
            />
            <div className="nify-header__user-meta">
              <span className="nify-header__user-name">
                {user?.display_name || "用户"}
              </span>
              <span className="nify-header__user-role">
                {user?.email || "已登录"}
              </span>
            </div>
            <Button
              type="text"
              className="nify-btn-secondary"
              onClick={() => {
                clearAuthSession();
                navigate("/login", { replace: true });
              }}
            >
              退出
            </Button>
          </Space>
        </Header>

        <Content className="nify-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

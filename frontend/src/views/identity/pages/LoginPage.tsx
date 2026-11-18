import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button, Form, Input, Typography } from "antd";
import { login, listWorkspaces } from "../api";
import {
  getAccessToken,
  setAccessToken,
  setStoredUser,
  setWorkspaceId,
} from "@/shared/api-client";
import { notifyError, notifySuccess } from "@/utils/notify";

/** 演示账号（与后端 seed 一致） */
const DEMO_LOGIN = {
  email: "demo@nify.local",
  password: "Demo1234!",
};

type LoginForm = {
  email: string;
  password: string;
};

type LocationState = {
  from?: { pathname?: string };
  email?: string;
};

/** 独立登录页（系统壳外） */
export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as LocationState | null) ?? null;
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm<LoginForm>();

  if (getAccessToken()) {
    return <Navigate to="/conversation" replace />;
  }

  const onFinish = async (values: LoginForm) => {
    setLoading(true);
    try {
      const token = await login(values);
      setAccessToken(token.access_token);
      setStoredUser({
        id: token.user.id,
        email: token.user.email,
        display_name: token.user.display_name,
      });
      try {
        const workspaces = await listWorkspaces();
        if (workspaces?.length) {
          setWorkspaceId(workspaces[0].id);
        }
      } catch {
        // 工作区列表失败不阻断进入系统
      }
      notifySuccess(`欢迎回来，${token.user.display_name}`);
      const redirect = state?.from?.pathname;
      navigate(redirect && redirect !== "/login" ? redirect : "/conversation", {
        replace: true,
      });
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="nify-auth-screen">
      <div className="nify-auth-screen__panel">
        <div className="nify-auth-screen__brand">
          <div className="nify-auth-screen__logo">Nify</div>
          <p className="nify-auth-screen__tagline">AI Agent Platform</p>
        </div>

        <div className="nify-auth-screen__card">
          <Typography.Title level={3} className="nify-auth-screen__title">
            登录
          </Typography.Title>
          <Typography.Paragraph type="secondary" className="nify-auth-screen__desc">
            使用账号进入工作区与模型管理
          </Typography.Paragraph>

          <Form
            form={form}
            layout="vertical"
            requiredMark={false}
            initialValues={{
              ...DEMO_LOGIN,
              email: state?.email || DEMO_LOGIN.email,
            }}
            onFinish={(v) => void onFinish(v)}
          >
            <Form.Item
              name="email"
              label="邮箱"
              rules={[{ required: true, type: "email", message: "请输入有效邮箱" }]}
            >
              <Input size="large" placeholder="demo@nify.local" autoComplete="username" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: "请输入密码" }]}
            >
              <Input.Password
                size="large"
                placeholder="密码"
                autoComplete="current-password"
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              className="nify-btn-primary"
              loading={loading}
            >
              登录
            </Button>
          </Form>

          <p className="nify-auth-screen__footer">
            还没有账号？{" "}
            <Link to="/register">去注册</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

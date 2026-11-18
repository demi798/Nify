import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Button, Form, Input, Typography } from "antd";
import { register } from "../api";
import { getAccessToken } from "@/shared/api-client";
import { notifyError, notifySuccess } from "@/utils/notify";

type RegisterForm = {
  display_name: string;
  email: string;
  password: string;
  confirm_password: string;
};

/** 独立注册页（系统壳外）；成功后跳转登录 */
export function RegisterPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm<RegisterForm>();

  if (getAccessToken()) {
    return <Navigate to="/conversation" replace />;
  }

  const onFinish = async (values: RegisterForm) => {
    setLoading(true);
    try {
      await register({
        display_name: values.display_name,
        email: values.email,
        password: values.password,
      });
      notifySuccess("注册成功，请登录");
      navigate("/login", { replace: true, state: { email: values.email } });
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "注册失败");
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
            注册
          </Typography.Title>
          <Typography.Paragraph type="secondary" className="nify-auth-screen__desc">
            创建账号后即可登录使用 Nify
          </Typography.Paragraph>

          <Form
            form={form}
            layout="vertical"
            requiredMark={false}
            onFinish={(v) => void onFinish(v)}
          >
            <Form.Item
              name="display_name"
              label="昵称"
              rules={[{ required: true, message: "请输入昵称" }]}
            >
              <Input size="large" placeholder="演示用户" maxLength={64} />
            </Form.Item>
            <Form.Item
              name="email"
              label="邮箱"
              rules={[{ required: true, type: "email", message: "请输入有效邮箱" }]}
            >
              <Input size="large" placeholder="you@example.com" autoComplete="email" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[
                { required: true, message: "请输入密码" },
                { min: 8, message: "至少 8 位" },
              ]}
            >
              <Input.Password
                size="large"
                placeholder="至少 8 位"
                autoComplete="new-password"
              />
            </Form.Item>
            <Form.Item
              name="confirm_password"
              label="确认密码"
              dependencies={["password"]}
              rules={[
                { required: true, message: "请再次输入密码" },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue("password") === value) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error("两次密码不一致"));
                  },
                }),
              ]}
            >
              <Input.Password
                size="large"
                placeholder="再次输入密码"
                autoComplete="new-password"
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
              注册
            </Button>
          </Form>

          <p className="nify-auth-screen__footer">
            已有账号？{" "}
            <Link to="/login">去登录</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

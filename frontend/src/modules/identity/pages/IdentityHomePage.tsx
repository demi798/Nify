import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  Popconfirm,
  Space,
  Table,
  Typography,
  message,
} from "antd";
import {
  createWorkspace,
  deleteWorkspace,
  listWorkspaces,
  login,
  register,
  updateWorkspace,
} from "../api";
import type { UserOut, WorkspaceOut } from "../types";
import { getAccessToken, setAccessToken } from "@/shared/api-client";

/** 最简单 CRUD 演示：注册/登录 + 工作区增删改查 */
export function IdentityHomePage() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [rows, setRows] = useState<WorkspaceOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [registerForm] = Form.useForm();
  const [loginForm] = Form.useForm();
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [editing, setEditing] = useState<WorkspaceOut | null>(null);

  const refresh = useCallback(async () => {
    if (!getAccessToken()) {
      setRows([]);
      return;
    }
    setLoading(true);
    try {
      const data = await listWorkspaces();
      setRows(data ?? []);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, user]);

  const onRegister = async () => {
    const values = await registerForm.validateFields();
    setAuthLoading(true);
    try {
      await register(values);
      message.success("注册成功，请登录");
      loginForm.setFieldsValue({
        email: values.email,
        password: values.password,
      });
    } catch (err) {
      message.error(err instanceof Error ? err.message : "注册失败");
    } finally {
      setAuthLoading(false);
    }
  };

  const onLogin = async () => {
    const values = await loginForm.validateFields();
    setAuthLoading(true);
    try {
      const token = await login(values);
      setAccessToken(token.access_token);
      setUser(token.user);
      message.success(`已登录：${token.user.display_name}`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "登录失败");
    } finally {
      setAuthLoading(false);
    }
  };

  const onLogout = () => {
    setAccessToken(null);
    setUser(null);
    setRows([]);
  };

  const onCreate = async () => {
    const values = await createForm.validateFields();
    try {
      await createWorkspace(values);
      createForm.resetFields();
      message.success("已创建工作区");
      await refresh();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "创建失败");
    }
  };

  const onSaveEdit = async () => {
    if (!editing) return;
    const values = await editForm.validateFields();
    try {
      await updateWorkspace(editing.id, values);
      setEditing(null);
      editForm.resetFields();
      message.success("已更新");
      await refresh();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "更新失败");
    }
  };

  const onDelete = async (id: string) => {
    try {
      await deleteWorkspace(id);
      message.success("已删除");
      await refresh();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "删除失败");
    }
  };

  return (
    <div>
      <Typography.Title level={3}>工作区 CRUD 演示</Typography.Title>
      <Typography.Paragraph type="secondary">
        先注册/登录，再对工作区做创建、列表、修改、删除。
      </Typography.Paragraph>

      <Space align="start" size="large" wrap style={{ width: "100%" }}>
        <Card title="注册" size="small" style={{ width: 320 }}>
          <Form form={registerForm} layout="vertical">
            <Form.Item
              name="display_name"
              label="昵称"
              rules={[{ required: true, message: "请输入昵称" }]}
            >
              <Input placeholder="演示用户" />
            </Form.Item>
            <Form.Item
              name="email"
              label="邮箱"
              rules={[{ required: true, type: "email" }]}
            >
              <Input placeholder="demo@nify.local" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, min: 8, message: "至少 8 位" }]}
            >
              <Input.Password placeholder="至少 8 位" />
            </Form.Item>
            <Button type="primary" loading={authLoading} onClick={() => void onRegister()}>
              注册
            </Button>
          </Form>
        </Card>

        <Card title="登录" size="small" style={{ width: 320 }}>
          <Form form={loginForm} layout="vertical">
            <Form.Item
              name="email"
              label="邮箱"
              rules={[{ required: true, type: "email" }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true }]}
            >
              <Input.Password />
            </Form.Item>
            <Space>
              <Button type="primary" loading={authLoading} onClick={() => void onLogin()}>
                登录
              </Button>
              {user ? (
                <Button onClick={onLogout}>退出（{user.display_name}）</Button>
              ) : null}
            </Space>
          </Form>
        </Card>
      </Space>

      <Card
        title="我的工作区"
        size="small"
        style={{ marginTop: 24 }}
        extra={
          <Space>
            <Form form={createForm} layout="inline">
              <Form.Item
                name="name"
                rules={[{ required: true, message: "请输入名称" }]}
              >
                <Input placeholder="新工作区名称" disabled={!getAccessToken()} />
              </Form.Item>
              <Button
                type="primary"
                disabled={!getAccessToken()}
                onClick={() => void onCreate()}
              >
                创建
              </Button>
            </Form>
          </Space>
        }
      >
        <Table<WorkspaceOut>
          rowKey="id"
          loading={loading}
          dataSource={rows}
          pagination={false}
          locale={{ emptyText: getAccessToken() ? "暂无工作区" : "请先登录" }}
          columns={[
            { title: "名称", dataIndex: "name" },
            { title: "角色", dataIndex: "role", width: 100 },
            { title: "创建时间", dataIndex: "created_at", width: 200 },
            {
              title: "操作",
              width: 180,
              render: (_, record) => (
                <Space>
                  <Button
                    size="small"
                    onClick={() => {
                      setEditing(record);
                      editForm.setFieldsValue({ name: record.name });
                    }}
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title="确认删除该工作区？"
                    onConfirm={() => void onDelete(record.id)}
                  >
                    <Button size="small" danger>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />

        {editing ? (
          <Card type="inner" title="编辑工作区" style={{ marginTop: 16 }}>
            <Form form={editForm} layout="inline">
              <Form.Item
                name="name"
                rules={[{ required: true, message: "请输入名称" }]}
              >
                <Input />
              </Form.Item>
              <Button type="primary" onClick={() => void onSaveEdit()}>
                保存
              </Button>
              <Button
                onClick={() => {
                  setEditing(null);
                  editForm.resetFields();
                }}
              >
                取消
              </Button>
            </Form>
          </Card>
        ) : null}
      </Card>
    </div>
  );
}

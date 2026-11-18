import { useCallback, useEffect, useState } from "react";
import { Button, Card, Form, Input, Popconfirm, Space, Table, message } from "antd";
import {
  createWorkspace,
  deleteWorkspace,
  listWorkspaces,
  updateWorkspace,
} from "../api";
import type { WorkspaceOut } from "../types";
import {
  getWorkspaceId,
  setWorkspaceId,
} from "@/shared/api-client";
import { PageCard, PageHeader } from "@/shared/components";

/** 工作区管理（需已登录；登录/注册在独立页面） */
export function IdentityHomePage() {
  const [rows, setRows] = useState<WorkspaceOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [editing, setEditing] = useState<WorkspaceOut | null>(null);
  const [activeId, setActiveId] = useState<string | null>(getWorkspaceId());

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listWorkspaces();
      const list = data ?? [];
      setRows(list);
      const current = getWorkspaceId();
      if (list.length === 0) {
        setWorkspaceId(null);
        setActiveId(null);
      } else if (!current || !list.some((w) => w.id === current)) {
        setWorkspaceId(list[0].id);
        setActiveId(list[0].id);
      } else {
        setActiveId(current);
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onCreate = async () => {
    const values = await createForm.validateFields();
    try {
      const ws = await createWorkspace(values);
      createForm.resetFields();
      setWorkspaceId(ws.id);
      setActiveId(ws.id);
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
      if (getWorkspaceId() === id) {
        setWorkspaceId(null);
        setActiveId(null);
      }
      message.success("已删除");
      await refresh();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "删除失败");
    }
  };

  return (
    <div className="nify-page">
      <PageHeader
        title="工作区"
        description="管理你的工作区；切换「使用」后，模型等模块将使用当前工作区。"
        extra={
          <Button className="nify-btn-secondary" onClick={() => void refresh()}>
            刷新
          </Button>
        }
      />

      <PageCard>
        <div className="nify-stack">
          <Space wrap style={{ width: "100%", justifyContent: "space-between" }}>
            <strong>我的工作区</strong>
            <Form form={createForm} layout="inline">
              <Form.Item
                name="name"
                rules={[{ required: true, message: "请输入名称" }]}
              >
                <Input placeholder="新工作区名称" />
              </Form.Item>
              <Button
                type="primary"
                className="nify-btn-primary"
                onClick={() => void onCreate()}
              >
                创建
              </Button>
            </Form>
          </Space>

          <Table<WorkspaceOut>
            rowKey="id"
            loading={loading}
            dataSource={rows}
            pagination={false}
            locale={{ emptyText: "暂无工作区，请先创建" }}
            rowClassName={(record) =>
              record.id === activeId ? "nify-table-row--active" : ""
            }
            columns={[
              {
                title: "名称",
                dataIndex: "name",
                render: (name: string, record) => (
                  <Space>
                    <span>{name}</span>
                    {record.id === activeId ? (
                      <span className="nify-caption">当前</span>
                    ) : null}
                  </Space>
                ),
              },
              { title: "角色", dataIndex: "role", width: 100 },
              { title: "创建时间", dataIndex: "created_at", width: 200 },
              {
                title: "操作",
                width: 240,
                render: (_, record) => (
                  <Space>
                    <Button
                      size="small"
                      className="nify-btn-secondary"
                      disabled={record.id === activeId}
                      onClick={() => {
                        setWorkspaceId(record.id);
                        setActiveId(record.id);
                        message.success(`已切换工作区：${record.name}`);
                      }}
                    >
                      使用
                    </Button>
                    <Button
                      size="small"
                      className="nify-btn-secondary"
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
                      <Button size="small" danger className="nify-btn-danger">
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
          />

          {editing ? (
            <Card type="inner" title="编辑工作区">
              <Form form={editForm} layout="inline">
                <Form.Item
                  name="name"
                  rules={[{ required: true, message: "请输入名称" }]}
                >
                  <Input />
                </Form.Item>
                <Button
                  type="primary"
                  className="nify-btn-primary"
                  onClick={() => void onSaveEdit()}
                >
                  保存
                </Button>
                <Button
                  className="nify-btn-secondary"
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
        </div>
      </PageCard>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Alert, Button, Descriptions, Space, Spin, Tabs, Tag } from "antd";
import { PageCard, PageHeader } from "@/shared/components";
import { notifyError } from "@/shared/notify";
import { getMcpServer } from "../api";
import type { McpServerDetail } from "../api";
import { McpDebugPanel } from "../components/McpDebugPanel";

/** MCP Server 详情：概览 + 调试 Tab */
export function McpDetailPage() {
  const { serverId = "" } = useParams<{ serverId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const tab = searchParams.get("tab") === "debug" ? "debug" : "overview";

  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<McpServerDetail | null>(null);

  const load = useCallback(async () => {
    if (!serverId) return;
    setLoading(true);
    try {
      const data = await getMcpServer(serverId);
      setDetail(data);
    } catch (err) {
      notifyError(err instanceof Error ? err.message : "加载失败");
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [serverId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onTabChange = (key: string) => {
    const next = new URLSearchParams(searchParams);
    if (key === "debug") next.set("tab", "debug");
    else next.delete("tab");
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="nify-page">
      <PageHeader
        title={detail?.name || "MCP 详情"}
        description={
          detail
            ? `${detail.transport} · ${detail.endpoint}`
            : "查看连接信息并调试工具调用"
        }
        extra={
          <Space wrap>
            <Link to="/mcp">
              <Button
                className="nify-btn-secondary"
                icon={<ArrowLeftOutlined />}
              >
                返回列表
              </Button>
            </Link>
            <Button onClick={() => void load()} disabled={loading}>
              刷新
            </Button>
          </Space>
        }
      />

      <PageCard>
        {loading && !detail ? (
          <div style={{ textAlign: "center", padding: 48 }}>
            <Spin />
          </div>
        ) : !detail ? (
          <Alert
            type="error"
            showIcon
            message="MCP Server 不存在或加载失败"
            action={
              <Button size="small" onClick={() => navigate("/mcp")}>
                返回
              </Button>
            }
          />
        ) : (
          <Tabs
            activeKey={tab}
            onChange={onTabChange}
            items={[
              {
                key: "overview",
                label: "概览",
                children: (
                  <Descriptions
                    column={1}
                    bordered
                    size="small"
                    labelStyle={{ width: 140 }}
                  >
                    <Descriptions.Item label="名称">
                      {detail.name}
                    </Descriptions.Item>
                    <Descriptions.Item label="传输">
                      <Tag>{detail.transport}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="Endpoint">
                      {detail.endpoint}
                    </Descriptions.Item>
                    <Descriptions.Item label="启用">
                      {detail.is_enabled ? (
                        <Tag color="success">是</Tag>
                      ) : (
                        <Tag>否</Tag>
                      )}
                    </Descriptions.Item>
                    <Descriptions.Item label="鉴权">
                      {detail.has_auth ? "已配置" : "无"}
                    </Descriptions.Item>
                    <Descriptions.Item label="工具数">
                      {detail.tools?.length ?? 0}
                    </Descriptions.Item>
                    {detail.tools_error ? (
                      <Descriptions.Item label="工具拉取">
                        <Alert
                          type="warning"
                          showIcon
                          message={detail.tools_error}
                        />
                      </Descriptions.Item>
                    ) : null}
                  </Descriptions>
                ),
              },
              {
                key: "debug",
                label: "调试",
                children: (
                  <McpDebugPanel
                    serverId={detail.id}
                    tools={detail.tools || []}
                    toolsError={detail.tools_error}
                  />
                ),
              },
            ]}
          />
        )}
      </PageCard>
    </div>
  );
}

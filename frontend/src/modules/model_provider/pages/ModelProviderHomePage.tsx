import { useEffect, useState } from "react";
import { Spin, Typography } from "antd";
import { getHealth } from "@/api/health";

type ConnState = "loading" | "ok" | "fail";

/** 模型提供商模块首页：加载时探测后端健康检查 */
export function ModelProviderHomePage() {
  const [conn, setConn] = useState<ConnState>("loading");
  const [detail, setDetail] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    getHealth()
      .then((data) => {
        if (cancelled) return;
        setConn("ok");
        setDetail(data?.status ? `status=${data.status}` : "");
      })
      .catch(() => {
        if (cancelled) return;
        setConn("fail");
        setDetail("");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <Typography.Title level={3}>模型提供商</Typography.Title>
      <Typography.Paragraph type="secondary">
        模块目录已按 CLAUDE.md 初始化，业务页面待实现。
      </Typography.Paragraph>

      {conn === "loading" ? (
        <Spin tip="正在检测后端连接…" />
      ) : conn === "ok" ? (
        <Typography.Text style={{ color: "#52c41a" }}>
          后端已连接：Nify is running
          {detail ? `（${detail}）` : null}
        </Typography.Text>
      ) : (
        <Typography.Text style={{ color: "#ff4d4f" }}>后端未连接</Typography.Text>
      )}
    </div>
  );
}

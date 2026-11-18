import type { ThemeConfig } from "antd";

/**
 * Ant Design 主题：对齐 tokens.css 中的 Nify 设计变量。
 * 主色蓝紫、辅色青绿、浅底内容区。
 */
export const nifyAntdTheme: ThemeConfig = {
  token: {
    colorPrimary: "#4f46e5",
    colorInfo: "#3b82f6",
    colorSuccess: "#14b8a6",
    colorWarning: "#f59e0b",
    colorError: "#ef4444",
    colorLink: "#4f46e5",
    colorTextBase: "#0f172a",
    colorTextSecondary: "#475569",
    colorTextTertiary: "#94a3b8",
    colorTextQuaternary: "#cbd5e1",
    colorBgBase: "#ffffff",
    colorBgLayout: "#f1f5f9",
    colorBgContainer: "#ffffff",
    colorBgElevated: "#ffffff",
    colorBorder: "#e2e8f0",
    colorBorderSecondary: "#eef2f7",
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    borderRadiusXS: 4,
    fontFamily:
      '"Plus Jakarta Sans", "IBM Plex Sans", "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    fontSize: 14,
    controlHeight: 36,
    controlHeightSM: 28,
    controlHeightLG: 40,
    boxShadow: "0 1px 2px rgba(15, 23, 42, 0.05), 0 1px 3px rgba(15, 23, 42, 0.04)",
    boxShadowSecondary:
      "0 4px 12px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.04)",
    motionDurationFast: "0.12s",
    motionDurationMid: "0.2s",
    motionDurationSlow: "0.32s",
    wireframe: false,
  },
  components: {
    Layout: {
      siderBg: "#0a0a0f",
      triggerBg: "#12121a",
      headerBg: "#ffffff",
      bodyBg: "#f1f5f9",
      headerHeight: 56,
    },

    Menu: {
      darkItemBg: "transparent",
      darkSubMenuItemBg: "transparent",
      darkItemSelectedBg: "rgba(255, 255, 255, 0.1)",
      darkItemHoverBg: "rgba(255, 255, 255, 0.1)",
      darkItemColor: "#ffffff",
      darkItemSelectedColor: "#ffffff",
      itemBorderRadius: 8,
      iconSize: 16,
    },

    Button: {
      primaryShadow: "0 0 0 1px rgba(99, 102, 241, 0.15), 0 6px 16px rgba(79, 70, 229, 0.18)",
      borderRadius: 8,
      fontWeight: 500,
    },
    Table: {
      headerBg: "#f8fafc",
      headerColor: "#475569",
      rowHoverBg: "#f8fafc",
      borderColor: "#eef2f7",
      borderRadius: 8,
    },
    Card: {
      borderRadiusLG: 12,
      paddingLG: 24,
    },
    Input: {
      activeBorderColor: "#818cf8",
      hoverBorderColor: "#a5b4fc",
      activeShadow: "0 0 0 3px rgba(99, 102, 241, 0.2)",
    },
    Select: {
      optionSelectedBg: "#eef2ff",
    },
    Tag: {
      borderRadiusSM: 6,
    },
  },
};

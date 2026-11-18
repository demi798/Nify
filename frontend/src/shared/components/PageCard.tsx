import type { ReactNode } from "react";

type PageCardProps = {
  children: ReactNode;
  className?: string;
};

/** 内容白卡片：轻阴影 + 圆角，建立与浅灰底的层次 */
export function PageCard({ children, className }: PageCardProps) {
  const cls = className ? `nify-page-card ${className}` : "nify-page-card";
  return <div className={cls}>{children}</div>;
}

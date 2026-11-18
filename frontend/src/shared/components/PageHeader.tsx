import type { ReactNode } from "react";

type PageHeaderProps = {
  title: string;
  description?: string;
  extra?: ReactNode;
};

/** 页面标题区：左侧标题+描述，右侧操作按钮 */
export function PageHeader({ title, description, extra }: PageHeaderProps) {
  return (
    <div className="nify-page-header">
      <div className="nify-page-header__main">
        <h1 className="nify-page-header__title">{title}</h1>
        {description ? (
          <p className="nify-page-header__desc">{description}</p>
        ) : null}
      </div>
      {extra ? <div className="nify-page-header__extra">{extra}</div> : null}
    </div>
  );
}

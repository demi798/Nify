import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { getAccessToken } from "@/shared/api-client";

/** 未登录则跳转登录页，保留来源路径便于登录后回跳 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!getAccessToken()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}

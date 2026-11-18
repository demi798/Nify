import { useEffect, useState } from "react";

/**
 * 订阅 CSS 媒体查询，窗口变化时自动更新。
 * @example useMediaQuery("(max-width: 1199px)")
 */
export function useMediaQuery(query: string): boolean {
  const getMatches = () =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false;

  const [matches, setMatches] = useState(getMatches);

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

/** 窄屏：宽度小于 1200px（与侧栏自动折叠断点一致） */
export function useIsNarrowScreen(): boolean {
  return useMediaQuery("(max-width: 1199px)");
}

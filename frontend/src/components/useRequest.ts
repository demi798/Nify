/**
 * 请求状态管理：自动维护 data / loading / error，减少页面 try-catch-finally 样板。
 */
import { useCallback, useEffect, useRef, useState } from "react";

export type UseRequestOptions<TArgs extends unknown[], TData> = {
  /** 挂载时立即执行（无参 API 时常用） */
  immediate?: boolean;
  /** immediate 时传入的参数 */
  defaultArgs?: TArgs;
  onSuccess?: (data: TData, args: TArgs) => void;
  onError?: (error: Error, args: TArgs) => void;
};

export type UseRequestResult<TArgs extends unknown[], TData> = {
  data: TData | undefined;
  loading: boolean;
  error: Error | null;
  execute: (...args: TArgs) => Promise<TData>;
  reset: () => void;
};

export function useRequest<TArgs extends unknown[], TData>(
  api: (...args: TArgs) => Promise<TData>,
  options: UseRequestOptions<TArgs, TData> = {},
): UseRequestResult<TArgs, TData> {
  const { immediate = false, defaultArgs, onSuccess, onError } = options;
  const [data, setData] = useState<TData | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const apiRef = useRef(api);
  apiRef.current = api;
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  onSuccessRef.current = onSuccess;
  onErrorRef.current = onError;

  const execute = useCallback(async (...args: TArgs): Promise<TData> => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiRef.current(...args);
      setData(result);
      onSuccessRef.current?.(result, args);
      return result;
    } catch (err) {
      const normalized =
        err instanceof Error ? err : new Error(String(err ?? "请求失败"));
      setError(normalized);
      onErrorRef.current?.(normalized, args);
      throw normalized;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(undefined);
    setError(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!immediate) return;
    const args = (defaultArgs ?? ([] as unknown as TArgs)) as TArgs;
    void execute(...args).catch(() => {
      /* 错误已写入 error state */
    });
    // 仅挂载触发一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [immediate]);

  return { data, loading, error, execute, reset };
}

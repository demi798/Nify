/**
 * 通用列表页表格：自动管理 loading / 分页 / 请求，暴露 refresh()。
 */
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import type { ReactElement, ReactNode, Ref } from "react";
import { Empty, Table } from "antd";
import type { TablePaginationConfig, TableProps } from "antd";
import { notifyError } from "@/shared/notify";

export type NifyTableQuery = {
  page: number;
  pageSize: number;
};

/** 兼容数组或 { items, total } 分页结构 */
export type NifyTableListResult<T> =
  | T[]
  | {
      items: T[];
      total?: number;
      next_cursor?: string | null;
    };

export type NifyTableApi<T> = (
  query: NifyTableQuery,
) => Promise<NifyTableListResult<T>>;

export type NifyTableProps<T extends object> = {
  columns: TableProps<T>["columns"];
  api: NifyTableApi<T>;
  /** 是否显示分页，默认 true */
  pagination?: boolean;
  rowKey?: TableProps<T>["rowKey"];
  /** 行展开（如模型列表） */
  expandable?: TableProps<T>["expandable"];
  /** 额外查询参数变化时自动刷新 */
  deps?: unknown[];
  size?: TableProps<T>["size"];
  className?: string;
  /** 空状态文案或节点 */
  emptyText?: ReactNode;
};

export type NifyTableRef = {
  refresh: () => Promise<void>;
};

function normalizeResult<T>(
  result: NifyTableListResult<T>,
): { items: T[]; total?: number } {
  if (Array.isArray(result)) {
    return { items: result, total: result.length };
  }
  return {
    items: result.items ?? [],
    total: result.total,
  };
}

function NifyTableInner<T extends object>(
  {
    columns,
    api,
    pagination = true,
    rowKey = "id" as TableProps<T>["rowKey"],
    expandable,
    deps = [],
    size = "middle",
    className,
    emptyText,
  }: NifyTableProps<T>,
  ref: Ref<NifyTableRef>,
) {
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<T[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const fetchData = useCallback(
    async (nextPage = page, nextSize = pageSize) => {
      setLoading(true);
      try {
        const raw = await api({ page: nextPage, pageSize: nextSize });
        const { items, total: remoteTotal } = normalizeResult(raw);
        setDataSource(items);
        if (typeof remoteTotal === "number") {
          setTotal(remoteTotal);
        } else if (!pagination) {
          setTotal(items.length);
        } else {
          // 无 total 时：满页则估为至少还有下一页
          setTotal(
            items.length < nextSize
              ? (nextPage - 1) * nextSize + items.length
              : nextPage * nextSize + 1,
          );
        }
      } catch (err) {
        notifyError(err instanceof Error ? err.message : "加载列表失败");
        setDataSource([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    // deps 由调用方控制刷新时机；api 引用变化也应刷新
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, page, pageSize, pagination, ...deps],
  );

  useEffect(() => {
    void fetchData(page, pageSize);
  }, [fetchData, page, pageSize]);

  useImperativeHandle(
    ref,
    () => ({
      refresh: () => fetchData(page, pageSize),
    }),
    [fetchData, page, pageSize],
  );

  const paginationConfig: TablePaginationConfig | false = pagination
    ? {
        current: page,
        pageSize,
        total,
        showSizeChanger: true,
        showTotal: (t) => `共 ${t} 条`,
        onChange: (p, ps) => {
          setPage(p);
          setPageSize(ps);
        },
      }
    : false;

  return (
    <Table<T>
      className={className ? `nify-table ${className}` : "nify-table"}
      rowKey={rowKey}
      columns={columns}
      dataSource={dataSource}
      loading={loading}
      size={size}
      pagination={paginationConfig}
      expandable={expandable}
      locale={{
        emptyText: emptyText ?? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无数据"
          />
        ),
      }}
    />
  );
}

/** 泛型 forwardRef 包装 */
export const NifyTable = forwardRef(NifyTableInner) as <T extends object>(
  props: NifyTableProps<T> & { ref?: Ref<NifyTableRef> },
) => ReactElement;

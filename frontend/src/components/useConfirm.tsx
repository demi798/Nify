/**
 * 删除确认：确认文案 → 调 API → 成功提示，一行完成全流程。
 */
import { Modal } from "antd";
import { ExclamationCircleFilled } from "@ant-design/icons";
import { notifyError, notifySuccess } from "@/utils/notify";

export type ConfirmDeleteOptions<T = void> = {
  /** 确认框标题 */
  title?: string;
  /** 确认文案 */
  content: string;
  /** 确认后调用的 API */
  api: () => Promise<T>;
  /** 成功提示（默认「删除成功」） */
  successText?: string;
  /** 危险确认（红色确认按钮） */
  danger?: boolean;
  okText?: string;
  cancelText?: string;
};

/**
 * 弹出删除确认并执行 API。
 * @example
 * await confirmDelete({ content: '确认删除该工作区？', api: () => deleteWorkspace(id) })
 */
export function confirmDelete<T = void>(
  options: ConfirmDeleteOptions<T>,
): Promise<T> {
  const {
    title = "确认删除",
    content,
    api,
    successText = "删除成功",
    danger = true,
    okText = "删除",
    cancelText = "取消",
  } = options;

  return new Promise<T>((resolve, reject) => {
    Modal.confirm({
      title,
      icon: <ExclamationCircleFilled style={{ color: "var(--nify-error)" }} />,
      content,
      okText,
      cancelText,
      okButtonProps: {
        danger,
        className: danger ? "nify-btn-danger" : "nify-btn-primary",
      },
      cancelButtonProps: {
        className: "nify-btn-secondary",
      },
      centered: true,
      className: "nify-confirm-modal",
      async onOk() {
        try {
          const result = await api();
          notifySuccess(successText);
          resolve(result);
          return result;
        } catch (err) {
          const msg =
            err instanceof Error ? err.message : String(err ?? "操作失败");
          notifyError(msg);
          reject(err);
          // 阻止弹窗关闭，便于用户重试；若希望关闭可 return
          return Promise.reject(err);
        }
      },
      onCancel() {
        reject(new Error("cancelled"));
      },
    });
  });
}

/** Hook 形态（便于组件内稳定引用） */
export function useConfirm() {
  return { confirmDelete };
}

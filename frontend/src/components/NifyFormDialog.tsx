/**
 * 通用表单弹窗：open(data?) 编辑/新增，提交触发 onSubmit，由父组件调 API。
 */
import {
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useImperativeHandle,
  useMemo,
  useState,
} from "react";
import type { ReactElement, ReactNode, Ref } from "react";
import { Form, Modal } from "antd";
import type { FormInstance, FormItemProps, FormRule } from "antd";

export type NifyFormRules<T extends object> = Partial<
  Record<keyof T & string, FormRule[]>
>;

export type NifyFormDialogProps<T extends object> = {
  title: string | ((mode: "create" | "edit") => string);
  width?: number | string;
  /** 字段校验规则；配合 NifyFormItem 自动挂载 */
  rules?: NifyFormRules<T>;
  /** 提交：父组件负责 API；返回 Promise 时等待结束后再关窗 */
  onSubmit: (values: T, mode: "create" | "edit") => void | Promise<void>;
  children: (form: FormInstance<T>, mode: "create" | "edit") => ReactNode;
  okText?: string;
  cancelText?: string;
  destroyOnClose?: boolean;
};

export type NifyFormDialogRef<T extends object> = {
  /** 传 data 为编辑模式，不传为新增模式 */
  open: (data?: Partial<T>) => void;
  close: () => void;
  form: FormInstance<T>;
};

const FormRulesContext = createContext<NifyFormRules<object> | undefined>(
  undefined,
);

/** 自动合并 Dialog rules 的 Form.Item */
export function NifyFormItem<T extends object = object>(
  props: FormItemProps<T> & { name: keyof T & string },
) {
  const rulesMap = useContext(FormRulesContext) as NifyFormRules<T> | undefined;
  const mergedRules = [
    ...(rulesMap?.[props.name] ?? []),
    ...(props.rules ?? []),
  ];
  return <Form.Item {...props} rules={mergedRules.length ? mergedRules : undefined} />;
}

function NifyFormDialogInner<T extends object>(
  {
    title,
    width = 520,
    rules,
    onSubmit,
    children,
    okText = "确定",
    cancelText = "取消",
    destroyOnClose = true,
  }: NifyFormDialogProps<T>,
  ref: Ref<NifyFormDialogRef<T>>,
) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"create" | "edit">("create");
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<T>();

  const resolvedTitle = useMemo(() => {
    return typeof title === "function" ? title(mode) : title;
  }, [title, mode]);

  const resetAndClose = useCallback(() => {
    form.resetFields();
    setOpen(false);
    setMode("create");
  }, [form]);

  useImperativeHandle(
    ref,
    () => ({
      open(data?: Partial<T>) {
        if (data && Object.keys(data).length > 0) {
          setMode("edit");
          // 先打开再设值，避免 destroyOnClose 竞态
          setOpen(true);
          queueMicrotask(() => {
            form.setFieldsValue(data as T);
          });
        } else {
          setMode("create");
          form.resetFields();
          setOpen(true);
        }
      },
      close: resetAndClose,
      form,
    }),
    [form, resetAndClose],
  );

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      await onSubmit(values, mode);
      resetAndClose();
    } catch (err) {
      if (err && typeof err === "object" && "errorFields" in err) {
        return;
      }
      // 业务失败保持弹窗，便于修改后重试
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      className="nify-form-dialog"
      title={resolvedTitle}
      open={open}
      width={width}
      okText={okText}
      cancelText={cancelText}
      confirmLoading={submitting}
      destroyOnClose={destroyOnClose}
      maskClosable={!submitting}
      okButtonProps={{ className: "nify-btn-primary" }}
      cancelButtonProps={{ className: "nify-btn-secondary" }}
      onOk={() => void handleOk()}
      onCancel={() => {
        if (!submitting) resetAndClose();
      }}
      afterClose={() => {
        form.resetFields();
      }}
    >
      <FormRulesContext.Provider value={rules as NifyFormRules<object> | undefined}>
        <Form<T>
          form={form}
          layout="vertical"
          requiredMark="optional"
          className="nify-form-dialog__form"
          style={{ marginTop: 8 }}
        >
          {children(form, mode)}
        </Form>
      </FormRulesContext.Provider>
    </Modal>
  );
}

export const NifyFormDialog = forwardRef(NifyFormDialogInner) as <
  T extends object,
>(
  props: NifyFormDialogProps<T> & { ref?: Ref<NifyFormDialogRef<T>> },
) => ReactElement;

/** 手动取某字段 rules（不用 NifyFormItem 时） */
export function fieldRules<T extends object>(
  rules: NifyFormRules<T> | undefined,
  name: keyof T & string,
): FormRule[] | undefined {
  return rules?.[name];
}

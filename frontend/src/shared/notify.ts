/**
 * 统一通知封装：底层 Ant Design message，统一 duration 与样式类名。
 */
import { message } from "antd";

const DEFAULT_DURATION = 2.5;

message.config({
  duration: DEFAULT_DURATION,
  maxCount: 3,
});

export function notifySuccess(content: string, duration = DEFAULT_DURATION): void {
  message.success({
    content,
    duration,
    className: "nify-notify nify-notify--success",
  });
}

export function notifyError(content: string, duration = DEFAULT_DURATION): void {
  message.error({
    content,
    duration,
    className: "nify-notify nify-notify--error",
  });
}

export function notifyWarning(content: string, duration = DEFAULT_DURATION): void {
  message.warning({
    content,
    duration,
    className: "nify-notify nify-notify--warning",
  });
}

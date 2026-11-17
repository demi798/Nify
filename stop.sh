#!/usr/bin/env bash
# Nify 停止脚本：按 PID 文件优雅停止后端与前端
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID_FILE="${ROOT_DIR}/.nify-backend.pid"
FRONTEND_PID_FILE="${ROOT_DIR}/.nify-frontend.pid"
STOP_WAIT_SEC="${STOP_WAIT_SEC:-10}"

info() {
  echo "[信息] $*"
}

warn() {
  echo "[警告] $*" >&2
}

# 向进程及其子进程发送信号
signal_tree() {
  local sig="$1"
  local pid="$2"
  local child
  # 先子后父，便于子进程先收到信号
  while read -r child; do
    [[ -n "${child}" ]] || continue
    signal_tree "${sig}" "${child}"
  done < <(pgrep -P "${pid}" 2>/dev/null || true)
  kill "-${sig}" "${pid}" 2>/dev/null || true
}

# 等待进程树退出，超时返回 1
wait_tree_exit() {
  local pid="$1"
  local timeout="$2"
  local elapsed=0
  while (( elapsed < timeout )); do
    if ! kill -0 "${pid}" 2>/dev/null; then
      # 父进程没了，再确认是否还有残留子进程名（尽力）
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

stop_by_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "${pid_file}" ]]; then
    info "${name}: 未找到 PID 文件 ${pid_file}，跳过"
    return 0
  fi

  local pid
  pid="$(tr -d '[:space:]' <"${pid_file}" || true)"
  if [[ -z "${pid}" ]] || ! [[ "${pid}" =~ ^[0-9]+$ ]]; then
    warn "${name}: PID 文件内容无效，删除 ${pid_file}"
    rm -f "${pid_file}"
    return 0
  fi

  if ! kill -0 "${pid}" 2>/dev/null; then
    info "${name}: 进程 PID=${pid} 已不存在，清理 PID 文件"
    rm -f "${pid_file}"
    return 0
  fi

  info "${name}: 发送 SIGTERM → PID=${pid}（含子进程）"
  signal_tree TERM "${pid}"

  if wait_tree_exit "${pid}" "${STOP_WAIT_SEC}"; then
    info "${name}: 已优雅退出 PID=${pid}"
    rm -f "${pid_file}"
    return 0
  fi

  warn "${name}: ${STOP_WAIT_SEC}s 内未退出，发送 SIGKILL → PID=${pid}"
  signal_tree KILL "${pid}"
  sleep 1
  if kill -0 "${pid}" 2>/dev/null; then
    warn "${name}: SIGKILL 后仍存活 PID=${pid}"
    return 1
  fi
  info "${name}: 已强制结束 PID=${pid}"
  rm -f "${pid_file}"
  return 0
}

main() {
  info "Nify 停止脚本: ${ROOT_DIR}"
  local failed=0
  # 先停前端再停后端，避免前端代理误打已半死的后端
  stop_by_pid_file "前端" "${FRONTEND_PID_FILE}" || failed=1
  stop_by_pid_file "后端" "${BACKEND_PID_FILE}" || failed=1

  if [[ "${failed}" -ne 0 ]]; then
    echo "[错误] 部分进程未能完全停止" >&2
    exit 1
  fi
  info "全部目标进程已处理完毕"
}

main "$@"

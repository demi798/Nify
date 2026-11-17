#!/usr/bin/env bash
# Nify 一键启动：检查依赖 → 启动后端 → 等健康检查 → 启动前端
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
LOG_DIR="${BACKEND_DIR}/log"
BACKEND_PID=""
FRONTEND_PID=""
BACKEND_PID_FILE="${ROOT_DIR}/.nify-backend.pid"
FRONTEND_PID_FILE="${ROOT_DIR}/.nify-frontend.pid"
BACKEND_LOG="${LOG_DIR}/nify-backend.log"
FRONTEND_LOG="${LOG_DIR}/nify-frontend.log"
FRONTEND_INSTALL_LOG="${LOG_DIR}/nify-frontend-install.log"
HEALTH_URL="http://127.0.0.1:8080/api/v1/health"
HEALTH_TIMEOUT_SEC="${HEALTH_TIMEOUT_SEC:-60}"
HEALTH_INTERVAL_SEC="${HEALTH_INTERVAL_SEC:-2}"

# 默认连接（可被 backend/.env 覆盖）
NIFY_MYSQL_HOST="${NIFY_MYSQL_HOST:-127.0.0.1}"
NIFY_MYSQL_PORT="${NIFY_MYSQL_PORT:-3306}"
NIFY_REDIS_HOST="${NIFY_REDIS_HOST:-127.0.0.1}"
NIFY_REDIS_PORT="${NIFY_REDIS_PORT:-6379}"
NIFY_SERVER_PORT="${NIFY_SERVER_PORT:-8080}"

die() {
  echo "[错误] $*" >&2
  exit 1
}

info() {
  echo "[信息] $*"
}

load_env() {
  local env_file="${BACKEND_DIR}/.env"
  if [[ -f "${env_file}" ]]; then
    info "加载环境变量: ${env_file}"
    set -a
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${env_file}" || true)
    set +a
  else
    info "未找到 ${env_file}，使用默认连接配置（可复制 .env.example）"
  fi
  HEALTH_URL="http://127.0.0.1:${NIFY_SERVER_PORT}/api/v1/health"
}

cleanup() {
  local code=$?
  # 启动失败时尽量清掉已拉起的进程与 PID 文件
  if [[ ${code} -ne 0 ]]; then
    if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
      kill -TERM "${FRONTEND_PID}" 2>/dev/null || true
    fi
    if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
      kill -TERM "${BACKEND_PID}" 2>/dev/null || true
    fi
    echo "[错误] 启动失败（exit=${code}）。后端日志: ${BACKEND_LOG}" >&2
  fi
}

trap cleanup EXIT INT TERM

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"
}

check_tcp() {
  local host="$1"
  local port="$2"
  local name="$3"
  if python3 - "$host" "$port" <<'PY'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=3):
        pass
except OSError as e:
    print(e)
    sys.exit(1)
PY
  then
    info "${name} 可达: ${host}:${port}"
  else
    die "${name} 不可用: ${host}:${port}（请先启动服务或检查 .env）"
  fi
}

check_mysql() {
  check_tcp "${NIFY_MYSQL_HOST}" "${NIFY_MYSQL_PORT}" "MySQL"
}

check_redis() {
  check_tcp "${NIFY_REDIS_HOST}" "${NIFY_REDIS_PORT}" "Redis"
}

build_and_start_backend() {
  require_cmd python3
  [[ -d "${BACKEND_DIR}" ]] || die "后端目录不存在: ${BACKEND_DIR}"
  cd "${BACKEND_DIR}"

  info "安装/构建后端依赖…"
  if [[ -f "${BACKEND_DIR}/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${BACKEND_DIR}/.venv/bin/activate"
  fi
  python3 -m pip install -e ".[dev]" >>"${BACKEND_LOG}" 2>&1 \
    || die "后端依赖安装失败，详见 ${BACKEND_LOG}"

  if lsof -iTCP:"${NIFY_SERVER_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    die "端口 ${NIFY_SERVER_PORT} 已被占用，请先执行 ./stop.sh 或释放端口"
  fi

  info "后台启动后端（端口 ${NIFY_SERVER_PORT}）…"
  : >"${BACKEND_LOG}"
  (
    cd "${BACKEND_DIR}"
    if [[ -f "${BACKEND_DIR}/.venv/bin/activate" ]]; then
      # shellcheck disable=SC1091
      source "${BACKEND_DIR}/.venv/bin/activate"
    fi
    export PYTHONPATH="${BACKEND_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
    exec python3 -m uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${NIFY_SERVER_PORT}"
  ) >>"${BACKEND_LOG}" 2>&1 &
  BACKEND_PID=$!
  echo "${BACKEND_PID}" >"${BACKEND_PID_FILE}"
  sleep 1
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    rm -f "${BACKEND_PID_FILE}"
    die "后端进程启动失败，详见 ${BACKEND_LOG}"
  fi
  info "后端已启动 PID=${BACKEND_PID}，PID 文件: ${BACKEND_PID_FILE}"
}

wait_for_health() {
  require_cmd curl
  info "等待后端健康检查: ${HEALTH_URL}"
  local elapsed=0
  while (( elapsed < HEALTH_TIMEOUT_SEC )); do
    if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
      die "后端进程已退出，健康检查中止。详见 ${BACKEND_LOG}"
    fi
    if curl -fsS "${HEALTH_URL}" 2>/dev/null | python3 -c '
import json,sys
try:
    body=json.load(sys.stdin)
except Exception:
    sys.exit(1)
code=str(body.get("code",""))
if code not in ("0","200"):
    sys.exit(1)
data=body.get("data")
if isinstance(data, dict) and "status" in data and data["status"] not in ("up","ok","running"):
    sys.exit(1)
sys.exit(0)
'; then
      info "后端健康检查通过"
      return 0
    fi
    sleep "${HEALTH_INTERVAL_SEC}"
    elapsed=$((elapsed + HEALTH_INTERVAL_SEC))
  done
  die "等待健康检查超时（${HEALTH_TIMEOUT_SEC}s），详见 ${BACKEND_LOG}"
}

start_frontend() {
  require_cmd npm
  [[ -d "${FRONTEND_DIR}" ]] || die "前端目录不存在: ${FRONTEND_DIR}"
  cd "${FRONTEND_DIR}"
  if [[ ! -d node_modules ]]; then
    info "安装前端依赖…"
    npm install >>"${FRONTEND_INSTALL_LOG}" 2>&1 \
      || die "前端依赖安装失败，详见 ${FRONTEND_INSTALL_LOG}"
  fi

  info "后台启动前端开发服务器…"
  : >"${FRONTEND_LOG}"
  (
    cd "${FRONTEND_DIR}"
    exec npm run dev
  ) >>"${FRONTEND_LOG}" 2>&1 &
  FRONTEND_PID=$!
  echo "${FRONTEND_PID}" >"${FRONTEND_PID_FILE}"
  sleep 1
  if ! kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    rm -f "${FRONTEND_PID_FILE}"
    die "前端进程启动失败，详见 ${FRONTEND_LOG}"
  fi
  info "前端已启动 PID=${FRONTEND_PID}，PID 文件: ${FRONTEND_PID_FILE}"
  info "前端日志: ${FRONTEND_LOG}；停止请执行: ${ROOT_DIR}/stop.sh"
  # 前台等待前端，便于本终端 Ctrl+C；EXIT trap 会尝试 TERM
  wait "${FRONTEND_PID}" || true
}

main() {
  info "Nify 启动脚本: ${ROOT_DIR}"
  mkdir -p "${LOG_DIR}"
  load_env
  check_mysql
  check_redis
  build_and_start_backend
  wait_for_health
  start_frontend
}

main "$@"

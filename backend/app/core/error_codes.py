"""稳定业务错误码枚举。

规则（与 CLAUDE.md 一致）：
- 成功固定为 \"0\"
- A*：用户侧（参数、鉴权、权限、资源不存在等）
- B*：本系统（未捕获异常、配置错误、数据不一致等）
- C*：第三方（LLM、MCP、对象存储、向量库等）
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """通用与一期预置错误码；业务模块可在本枚举中按步长追加，禁止魔法字符串散落。"""

    # ---------- 成功 ----------
    OK = "0"

    # ---------- A* 用户侧 ----------
    # 参数 / 校验
    BAD_REQUEST = "A0001"
    VALIDATION_ERROR = "A0002"
    # 鉴权 / 权限
    UNAUTHORIZED = "A0100"
    FORBIDDEN = "A0101"
    # 资源
    NOT_FOUND = "A0200"
    CONFLICT = "A0201"
    # 限流 / 配额（工作区级）
    TOO_MANY_REQUESTS = "A0300"

    # ---------- B* 本系统 ----------
    INTERNAL_ERROR = "B0001"
    SERVICE_UNAVAILABLE = "B0002"
    DATA_INCONSISTENT = "B0003"

    # ---------- C* 第三方 ----------
    LLM_TIMEOUT = "C0001"
    LLM_RATE_LIMIT = "C0002"
    LLM_UNAVAILABLE = "C0003"
    LLM_BAD_REQUEST = "C0004"
    LLM_AUTH = "C0005"
    EXTERNAL_SERVICE_ERROR = "C0099"

    @property
    def default_message(self) -> str:
        """默认对人展示的短句（可被 AppError.message 覆盖）。"""
        return _DEFAULT_MESSAGES.get(self, "请求失败")

    @property
    def http_status(self) -> int:
        """默认 HTTP 状态码（可被 AppError.http_status 覆盖）。"""
        return _DEFAULT_HTTP_STATUS.get(self, 500)


_DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.OK: "ok",
    ErrorCode.BAD_REQUEST: "请求参数错误",
    ErrorCode.VALIDATION_ERROR: "请求参数校验失败",
    ErrorCode.UNAUTHORIZED: "未授权，请先登录",
    ErrorCode.FORBIDDEN: "无权限执行此操作",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.CONFLICT: "资源冲突",
    ErrorCode.TOO_MANY_REQUESTS: "请求过于频繁，请稍后重试",
    ErrorCode.INTERNAL_ERROR: "系统内部错误",
    ErrorCode.SERVICE_UNAVAILABLE: "服务暂不可用",
    ErrorCode.DATA_INCONSISTENT: "数据不一致，请联系管理员",
    ErrorCode.LLM_TIMEOUT: "模型响应超时",
    ErrorCode.LLM_RATE_LIMIT: "模型调用触发限流",
    ErrorCode.LLM_UNAVAILABLE: "模型服务不可用",
    ErrorCode.LLM_BAD_REQUEST: "模型请求参数错误",
    ErrorCode.LLM_AUTH: "模型服务鉴权失败",
    ErrorCode.EXTERNAL_SERVICE_ERROR: "外部服务调用失败",
}

_DEFAULT_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.OK: 200,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.TOO_MANY_REQUESTS: 429,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.DATA_INCONSISTENT: 500,
    ErrorCode.LLM_TIMEOUT: 504,
    ErrorCode.LLM_RATE_LIMIT: 429,
    ErrorCode.LLM_UNAVAILABLE: 503,
    ErrorCode.LLM_BAD_REQUEST: 400,
    ErrorCode.LLM_AUTH: 502,
    ErrorCode.EXTERNAL_SERVICE_ERROR: 502,
}

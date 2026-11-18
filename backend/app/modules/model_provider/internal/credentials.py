"""凭证加解密：统一 JSON 形态入库，禁止明文落库。"""

from __future__ import annotations

import json
from typing import Any

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.security import decrypt_secret, encrypt_secret


def pack_credentials(*, api_key: str | None) -> str:
    """将凭证打包并加密。"""
    payload: dict[str, Any] = {}
    if api_key is not None and api_key.strip():
        payload["api_key"] = api_key.strip()
    return encrypt_secret(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def unpack_credentials(cipher_text: str) -> dict[str, Any]:
    """解密凭证 JSON。"""
    raw = decrypt_secret(cipher_text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError(ErrorCode.DATA_INCONSISTENT, "凭证密文格式损坏") from exc
    if not isinstance(data, dict):
        raise AppError(ErrorCode.DATA_INCONSISTENT, "凭证密文格式损坏")
    return data


def credentials_has_api_key(cipher_text: str) -> bool:
    """列表/详情：是否已配置 api_key（不解密到日志）。"""
    try:
        data = unpack_credentials(cipher_text)
    except AppError:
        return False
    key = data.get("api_key")
    return isinstance(key, str) and bool(key.strip())


def get_api_key(cipher_text: str) -> str:
    """取出 api_key；无则空串（如 Ollama）。"""
    data = unpack_credentials(cipher_text)
    key = data.get("api_key")
    if isinstance(key, str):
        return key.strip()
    return ""

"""MCP 鉴权材料加解密（禁止明文落库）。"""

from __future__ import annotations

import json
from typing import Any

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.security import decrypt_secret, encrypt_secret


def pack_auth(*, token: str | None) -> str | None:
    """打包鉴权 token；空则返回 None。"""
    if token is None or not str(token).strip():
        return None
    payload = {"token": str(token).strip()}
    return encrypt_secret(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def unpack_auth(cipher_text: str | None) -> dict[str, Any]:
    """解密鉴权 JSON。"""
    if not cipher_text:
        return {}
    raw = decrypt_secret(cipher_text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError(ErrorCode.DATA_INCONSISTENT, "MCP 鉴权密文损坏") from exc
    if not isinstance(data, dict):
        raise AppError(ErrorCode.DATA_INCONSISTENT, "MCP 鉴权密文损坏")
    return data


def auth_has_token(cipher_text: str | None) -> bool:
    try:
        data = unpack_auth(cipher_text)
    except AppError:
        return False
    token = data.get("token")
    return isinstance(token, str) and bool(token.strip())


def get_auth_token(cipher_text: str | None) -> str | None:
    data = unpack_auth(cipher_text)
    token = data.get("token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None

"""安全原语：密码哈希、JWT、敏感字段加密。

供 identity / model_provider 等使用；禁止在业务里手写 bcrypt/JWT。
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError

_fernet: Fernet | None = None


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """访问令牌载荷（与业务 User 实体解耦）。"""

    user_id: str
    email: str | None = None
    exp: datetime | None = None


def hash_password(plain: str) -> str:
    """哈希明文密码（bcrypt；超过 72 字节先截断）。"""
    raw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    raw = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(raw, password_hash.encode("ascii"))
    except ValueError:
        return False


def create_access_token(
    *,
    user_id: str,
    email: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    """签发 Bearer JWT。"""
    expire_delta = timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else settings.jwt_expire_minutes
    )
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + expire_delta,
    }
    if email:
        payload["email"] = email
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> TokenPayload:
    """解析并校验 JWT；失败抛 UNAUTHORIZED。"""
    try:
        data = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(ErrorCode.UNAUTHORIZED, "登录已过期，请重新登录") from exc
    except jwt.PyJWTError as exc:
        raise AppError(ErrorCode.UNAUTHORIZED, "无效的访问令牌") from exc

    user_id = data.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise AppError(ErrorCode.UNAUTHORIZED, "无效的访问令牌")

    exp_raw = data.get("exp")
    exp: datetime | None = None
    if isinstance(exp_raw, (int, float)):
        exp = datetime.fromtimestamp(exp_raw, tz=timezone.utc)

    email = data.get("email")
    return TokenPayload(
        user_id=user_id,
        email=email if isinstance(email, str) else None,
        exp=exp,
    )


def _get_fernet() -> Fernet:
    """由 secret_key 派生 Fernet 密钥（进程内单例）。"""
    global _fernet
    if _fernet is None:
        digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        _fernet = Fernet(key)
    return _fernet


def encrypt_secret(plain: str) -> str:
    """加密 API Key 等敏感串，入库前调用。"""
    token = _get_fernet().encrypt(plain.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(cipher_text: str) -> str:
    """解密敏感串；损坏则视为系统数据错误。"""
    try:
        plain = _get_fernet().decrypt(cipher_text.encode("ascii"))
    except (InvalidToken, ValueError) as exc:
        raise AppError(ErrorCode.DATA_INCONSISTENT, "密钥密文无法解密") from exc
    return plain.decode("utf-8")

"""本地对象存储薄封装（Files）。

只存 storage_key；禁止把文件二进制写入 MySQL。
一期默认本地磁盘，后续可替换为 S3 实现而不改业务签名。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.core.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


class LocalFileStorage:
    """基于本地目录的文件存储。"""

    def __init__(self, root: str | None = None) -> None:
        self._root = Path(root or settings.storage_root).resolve()

    def resolve_path(self, storage_key: str) -> Path:
        """将 storage_key 解析为绝对路径，并阻止目录穿越。"""
        if not storage_key or storage_key.startswith("/") or ".." in storage_key.split("/"):
            raise AppError(ErrorCode.BAD_REQUEST, "非法 storage_key")
        path = (self._root / storage_key).resolve()
        if not str(path).startswith(str(self._root)):
            raise AppError(ErrorCode.BAD_REQUEST, "非法 storage_key")
        return path

    def ensure_root(self) -> None:
        """确保根目录存在。"""
        self._root.mkdir(parents=True, exist_ok=True)

    async def save_bytes(self, storage_key: str, data: bytes) -> str:
        """写入字节并返回 storage_key。"""

        def _write() -> None:
            self.ensure_root()
            path = self.resolve_path(storage_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)
        logger.info("file saved key=%s bytes=%s", storage_key, len(data))
        return storage_key

    async def read_bytes(self, storage_key: str) -> bytes:
        """读取全部字节。"""

        def _read() -> bytes:
            path = self.resolve_path(storage_key)
            if not path.is_file():
                raise AppError(ErrorCode.NOT_FOUND, "文件不存在")
            return path.read_bytes()

        return await asyncio.to_thread(_read)

    async def delete(self, storage_key: str) -> None:
        """删除文件；不存在则忽略。"""

        def _delete() -> None:
            path = self.resolve_path(storage_key)
            if path.is_file():
                path.unlink()

        await asyncio.to_thread(_delete)
        logger.info("file deleted key=%s", storage_key)

    async def exists(self, storage_key: str) -> bool:
        def _exists() -> bool:
            return self.resolve_path(storage_key).is_file()

        return await asyncio.to_thread(_exists)


_storage: LocalFileStorage | None = None


def get_file_storage() -> LocalFileStorage:
    """获取默认文件存储单例。"""
    global _storage
    if _storage is None:
        _storage = LocalFileStorage()
    return _storage

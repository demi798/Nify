"""文档正文提取（同步 IO，供 asyncio.to_thread 调用）。"""

from __future__ import annotations

from pathlib import Path

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError


def extract_text(*, file_path: Path, content_type: str, filename: str) -> str:
    """按类型解析正文；扫描版 PDF（无文字层）一期报错。"""
    mime = (content_type or "").lower().strip()
    name = (filename or file_path.name).lower()

    if (
        mime in {"text/plain", "text/markdown", "text/x-markdown"}
        or name.endswith((".txt", ".md", ".markdown"))
    ):
        return _read_utf8(file_path)

    if mime == "application/pdf" or name.endswith(".pdf"):
        return _extract_pdf(file_path)

    # octet-stream：按扩展名兜底
    if mime == "application/octet-stream":
        if name.endswith((".txt", ".md", ".markdown")):
            return _read_utf8(file_path)
        if name.endswith(".pdf"):
            return _extract_pdf(file_path)

    raise AppError(
        ErrorCode.BAD_REQUEST,
        f"一期不支持的文件类型：{content_type or name}",
    )


def _read_utf8(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AppError(ErrorCode.BAD_REQUEST, f"读取文件失败：{exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError(ErrorCode.BAD_REQUEST, "文件不是合法 UTF-8 文本") from exc
    if not text.strip():
        raise AppError(ErrorCode.BAD_REQUEST, "文件内容为空")
    return text


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise AppError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "未安装 pypdf，无法解析 PDF",
        ) from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001 — 加密/损坏统一映射
        msg = str(exc).lower()
        if "encrypt" in msg or "password" in msg:
            raise AppError(ErrorCode.BAD_REQUEST, "不支持加密 PDF") from exc
        raise AppError(ErrorCode.BAD_REQUEST, f"PDF 损坏或无法打开：{exc}") from exc

    if getattr(reader, "is_encrypted", False):
        # 尝试空密码；失败则报错
        try:
            ok = reader.decrypt("")  # type: ignore[attr-defined]
            if ok == 0:
                raise AppError(ErrorCode.BAD_REQUEST, "不支持加密 PDF")
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AppError(ErrorCode.BAD_REQUEST, "不支持加密 PDF") from exc

    parts: list[str] = []
    try:
        for page in reader.pages:
            parts.append(page.extract_text() or "")
    except Exception as exc:  # noqa: BLE001
        raise AppError(ErrorCode.BAD_REQUEST, f"PDF 文字提取失败：{exc}") from exc

    text = "\n".join(parts).strip()
    if not text:
        raise AppError(
            ErrorCode.BAD_REQUEST,
            "扫描版 PDF（无文字层）一期不支持，请上传可复制文本的 PDF 或 TXT/MD",
        )
    return text

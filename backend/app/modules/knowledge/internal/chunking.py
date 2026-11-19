"""文本分块：递归按段落 > 句子 > 字符切分。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.modules.knowledge.constants import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？.!?])\s*")


@dataclass(slots=True)
class ChunkDTO:
    """管线中间态：分块 → 向量化 → 落库。"""

    chunk_index: int
    content: str
    token_count: int
    embedding: list[float] | None = field(default=None)


def estimate_tokens(text: str) -> int:
    """中英混合粗估：CJK 约 1 token/字，其它约 4 chars/token。"""
    if not text:
        return 0
    cjk = 0
    other = 0
    for ch in text:
        code = ord(ch)
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0xF900 <= code <= 0xFAFF
        ):
            cjk += 1
        elif not ch.isspace():
            other += 1
    return max(1, cjk + (other + 3) // 4) if (cjk or other) else 0


def split_chunks(
    text: str,
    *,
    chunk_size: int = CHUNK_SIZE_TOKENS,
    overlap: int = CHUNK_OVERLAP_TOKENS,
) -> list[ChunkDTO]:
    """递归分割：段落（\\n\\n）> 句子 > 字符截断；带 overlap。"""
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    pieces = _recursive_split(cleaned, chunk_size=chunk_size)
    if not pieces:
        return []

    # 合并过短片段并应用 overlap 窗口
    merged = _merge_with_overlap(pieces, chunk_size=chunk_size, overlap=overlap)
    out: list[ChunkDTO] = []
    for i, content in enumerate(merged):
        content = content.strip()
        if not content:
            continue
        out.append(
            ChunkDTO(
                chunk_index=len(out),
                content=content,
                token_count=estimate_tokens(content),
            )
        )
    return out


def _recursive_split(text: str, *, chunk_size: int) -> list[str]:
    if estimate_tokens(text) <= chunk_size:
        return [text]

    # 1) 段落
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) > 1:
        return _split_list(paras, chunk_size=chunk_size, joiner="\n\n")

    # 2) 句子
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if len(sentences) > 1:
        return _split_list(sentences, chunk_size=chunk_size, joiner="")

    # 3) 字符硬切（按估算 token）
    return _hard_cut(text, chunk_size=chunk_size)


def _split_list(parts: list[str], *, chunk_size: int, joiner: str) -> list[str]:
    buckets: list[str] = []
    buf = ""
    for part in parts:
        candidate = f"{buf}{joiner}{part}" if buf else part
        if buf and estimate_tokens(candidate) > chunk_size:
            buckets.extend(_recursive_split(buf, chunk_size=chunk_size))
            buf = part
        else:
            buf = candidate
    if buf:
        buckets.extend(_recursive_split(buf, chunk_size=chunk_size))
    return buckets


def _hard_cut(text: str, *, chunk_size: int) -> list[str]:
    """按字符近似切：目标每段约 chunk_size tokens。"""
    if not text:
        return []
    # 粗略：每 token ~1 字（偏中文）
    step = max(32, chunk_size)
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        out.append(text[i : i + step])
        i += step
    return out


def _merge_with_overlap(
    pieces: list[str], *, chunk_size: int, overlap: int
) -> list[str]:
    """将递归结果串成最终块，相邻块保留 overlap tokens 的后缀前缀。"""
    if not pieces:
        return []
    result: list[str] = []
    buf = ""
    for piece in pieces:
        candidate = f"{buf}\n{piece}".strip() if buf else piece
        if buf and estimate_tokens(candidate) > chunk_size:
            result.append(buf.strip())
            # overlap：取上一块尾部
            buf = _tail_by_tokens(buf, overlap)
            buf = f"{buf}\n{piece}".strip() if buf else piece
            if estimate_tokens(buf) > chunk_size:
                # overlap+piece 仍过大：直接放下一段
                result.extend(_recursive_split(piece, chunk_size=chunk_size))
                buf = _tail_by_tokens(result[-1], overlap) if result else ""
        else:
            buf = candidate
    if buf.strip():
        result.append(buf.strip())
    return result


def _tail_by_tokens(text: str, overlap: int) -> str:
    if overlap <= 0 or not text:
        return ""
    # 从尾部累加字符直到达到 overlap tokens
    acc = ""
    for ch in reversed(text):
        acc = ch + acc
        if estimate_tokens(acc) >= overlap:
            break
    return acc.strip()

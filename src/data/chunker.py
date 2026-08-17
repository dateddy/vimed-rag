"""Chia văn bản thành chunk theo token với size/overlap đọc từ config.

Ghi chú: scaffold dùng "token = từ tách theo khoảng trắng" để giữ phần này
thuần logic (không nạp tokenizer của bge-m3). Khi Gate 0 GO có thể thay hàm
``_tokenize`` bằng tokenizer thật mà không đổi giao diện.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.config import ChunkingConfig
from src.schemas import ChunkRecord


def _tokenize(text: str) -> list[str]:
    """Tách token thô theo khoảng trắng."""
    return text.split()


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Chia một văn bản thành các chunk chồng lấn.

    Cửa sổ trượt độ dài ``size`` token, bước nhảy ``size - overlap``. Đảm bảo
    KHÔNG mất token ở biên: chunk cuối luôn bao gồm token cuối cùng.

    Args:
        text: văn bản đầu vào (đã được làm sạch).
        size: số token mỗi chunk (> 0).
        overlap: số token chồng lấn giữa 2 chunk liền kề (>= 0, < size).

    Returns:
        Danh sách chunk (chuỗi). Rỗng nếu ``text`` không có token.
    """
    if size <= 0:
        raise ValueError("size phải > 0")
    if not 0 <= overlap < size:
        raise ValueError("overlap phải nằm trong [0, size)")

    tokens = _tokenize(text)
    if not tokens:
        return []

    step = size - overlap
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        window = tokens[start : start + size]
        chunks.append(" ".join(window))
        if start + size >= len(tokens):
            break
        start += step
    return chunks


def chunk_documents(
    docs: list[str],
    cfg: ChunkingConfig,
) -> list[str]:
    """Chunk nhiều document dùng size/overlap từ config (không magic number)."""
    result: list[str] = []
    for doc in docs:
        result.extend(chunk_text(doc, cfg.size, cfg.overlap))
    return result


def chunk_records(
    docs: Iterable,
    size: int,
    overlap: int,
) -> list[ChunkRecord]:
    """Cắt :class:`RawDocument` thành :class:`ChunkRecord` sẵn sàng để index.

    Mỗi chunk **thừa hưởng nguyên** ``doc.specialties`` (tuple, tất cả khoa
    khớp) chứ không phải ``doc.specialty`` số ít — DEC-017. Thu về số ít ở
    đây là cách âm thầm nhất để đánh rơi 15 bài thuộc cả hai khoa: index vẫn
    chạy, số point vẫn đúng, chỉ có filter khoa ở Tuần 3 là thiếu bài.

    Args:
        docs: các ``RawDocument`` từ ``load_documents()``.
        size: token/chunk. ``overlap``: token chồng lấn.

    Returns:
        ChunkRecord theo đúng thứ tự bài, ``chunk_idx`` chạy từ 0 trong mỗi bài.
    """
    records: list[ChunkRecord] = []
    for doc in docs:
        pieces = chunk_text(doc.text, size, overlap)
        for idx, text in enumerate(pieces):
            records.append(
                ChunkRecord(
                    doc_id=doc.doc_id,
                    chunk_idx=idx,
                    n_chunks=len(pieces),
                    text=text,
                    specialties=tuple(doc.specialties),
                    title=doc.title,
                    source=doc.source,
                )
            )
    return records

"""Làm sạch văn bản y tế tiếng Việt trước khi chunk.

Các bước thuần (không phụ thuộc model/data thật):
- Chuẩn hóa Unicode NFC (quan trọng với tiếng Việt có dấu).
- Loại thẻ HTML và giải mã một số entity phổ biến.
- Gộp khoảng trắng thừa.
- Lọc bài quá ngắn (min-length).
- Khử trùng lặp thô (rough dedup) theo nội dung đã chuẩn hóa.
"""

from __future__ import annotations

import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Vài entity HTML hay gặp; đủ dùng cho scaffold (không kéo bs4 vào core).
_ENTITIES = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
}


def strip_html(text: str) -> str:
    """Xóa thẻ HTML và giải mã entity cơ bản."""
    for entity, repl in _ENTITIES.items():
        text = text.replace(entity, repl)
    return _TAG_RE.sub(" ", text)


def normalize_text(text: str) -> str:
    """Chuẩn hóa NFC + gỡ HTML + gộp khoảng trắng, trả về chuỗi đã strip."""
    text = unicodedata.normalize("NFC", text)
    text = strip_html(text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def clean_documents(
    docs: list[str],
    min_length: int = 30,
) -> list[str]:
    """Làm sạch danh sách document và loại bài ngắn / trùng lặp.

    Args:
        docs: danh sách văn bản thô.
        min_length: số ký tự tối thiểu (sau chuẩn hóa) để giữ lại.

    Returns:
        Danh sách văn bản đã chuẩn hóa, đủ dài, không trùng (giữ thứ tự xuất hiện).
    """
    seen: set[str] = set()
    result: list[str] = []
    for doc in docs:
        norm = normalize_text(doc)
        if len(norm) < min_length:
            continue
        key = norm.casefold()  # dedup thô: bỏ qua khác biệt hoa/thường
        if key in seen:
            continue
        seen.add(key)
        result.append(norm)
    return result

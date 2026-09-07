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

# Byline "Bài viết được tư vấn chuyên môn bởi ... Vinmec <Nơi>" — 12,4% bài
# (175/1410, đo 2026-08-19). Nó mang TÊN BÁC SĨ + TÊN BỆNH VIỆN, nên để nguyên
# thì tầng generation trích dẫn thành "BS X khẳng định…" — quy một câu suy ra
# từ văn bản giáo dục thành lời một người thật.
#
# ⚠️ **KHÔNG áp ở ingestion.** Corpus đang index VẪN CÒN byline: DEC-020 đã cân
# và kết luận không đáng chạy lại ingestion chỉ vì nó. Hàm này dùng ở tầng
# ĐỌC RA — soạn `reference_contexts` (scripts/build_testset.py) và dựng ngữ cảnh
# trước khi vào prompt (src/generation/context.py).
#
# Bản v1 (bắt buộc kết thúc bằng dấu chấm) chỉ bắt 138/175 — `normalize_text`
# gộp khoảng trắng nên 37 byline chạy thẳng vào thân bài không có dấu chấm.
# Bản dưới bắt 175/175.
# Đánh đổi đã biết: `{0,3}` có thể ăn thêm 1 từ đầu thân bài nếu từ đó viết hoa.
BYLINE = re.compile(
    r"Bài viết được tư vấn chuyên môn bởi.{0,250}?Vinmec(?:\s+[A-ZĐÀ-Ỹ][a-zà-ỹ]+){0,3}\.?\s*",
    re.S,
)


def strip_byline(text: str) -> str:
    """Cắt byline "Bài viết được tư vấn chuyên môn bởi… Vinmec…" khỏi văn bản.

    Bản CÓ THẨM QUYỀN của phép cắt này. `scripts/build_testset.py` import lại
    từ đây thay vì giữ regex riêng: hai bản song song thì test set và prompt cắt
    khác nhau, và chênh lệch đó không có gì bắt được.
    """
    return BYLINE.sub("", text).strip()

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

"""Dựng ngữ cảnh cho prompt + kiểm trích dẫn — THUẦN, không gọi LLM.

Tách khỏi ``generator.py`` có chủ đích: đây là phần **kiểm được bằng test mà
không tốn một lượt API nào**, và cũng là phần dễ sai âm thầm nhất (đánh số lệch
một bậc thì mọi trích dẫn trong báo cáo trỏ sai nguồn).

Ba việc:

1. ``format_context`` — đánh số ``[n]`` khớp **đúng thứ tự** ``chunks`` mà
   pipeline truyền xuống, và **cắt byline** trước khi văn bản chạm prompt.
2. ``strip_invalid_citations`` — xoá ``[n]`` trỏ ra ngoài số nguồn thực có.
3. ``ensure_disclaimer`` — chốt câu miễn trừ, kể cả khi model quên.
"""

from __future__ import annotations

import re

from src.data.cleaner import strip_byline
from src.schemas import RetrievedChunk

# Khớp nguyên văn câu cuối mà cả hai prompt sinh (generation + generation_caution).
DISCLAIMER = (
    "Thông tin chỉ mang tính tham khảo, không thay thế tư vấn của bác sĩ."
)

_CITE_RE = re.compile(r"\[(\d{1,2})\]")


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Ghép chunk thành khối ``{context}`` đánh số ``[1]``, ``[2]``…

    Số ``[n]`` là **vị trí trong danh sách** (1-based), không phải ``chunk_idx``:
    UI và bảng eval đều ánh xạ ngược theo vị trí, nên đổi cách đánh số ở đây là
    làm sai mọi trích dẫn ở hạ nguồn.

    Tiêu đề đi kèm vì model cần biết đoạn nói về bài nào; **URL thì không** —
    nó tốn token và mời model in link vào câu trả lời, trong khi UI đã có
    ``source`` để tự dựng liên kết.
    """
    blocks: list[str] = []
    for i, c in enumerate(chunks, 1):
        head = c.title or c.doc_id
        if c.chunk_idx is not None and c.n_chunks:
            head = f"{head} (đoạn {c.chunk_idx + 1}/{c.n_chunks})"
        blocks.append(f"[{i}] {head}\n{strip_byline(c.text)}")
    return "\n\n".join(blocks)


def citations(text: str) -> list[int]:
    """Mọi số ``[n]`` xuất hiện trong ``text``, theo thứ tự, có lặp."""
    return [int(m) for m in _CITE_RE.findall(text)]


def invalid_citations(text: str, n_chunks: int) -> list[int]:
    """Các ``[n]`` trỏ ra ngoài ``1..n_chunks`` — trích dẫn bịa."""
    return sorted({n for n in citations(text) if n < 1 or n > n_chunks})


def strip_invalid_citations(text: str, n_chunks: int) -> str:
    """Xoá ``[n]`` không có nguồn tương ứng.

    Vì sao XOÁ chứ không để nguyên: ``[7]`` khi chỉ có 5 nguồn là **trích dẫn
    bịa** — UI Tuần 7 sẽ render một cái neo không trỏ đi đâu, và người đọc hiểu
    là "có nguồn". Bỏ dấu đi thì câu đó thành một khẳng định không trích dẫn,
    vẫn sai nhưng **không giả vờ có căn cứ**. Đây là lớp "grounded generation"
    của defense-in-depth, làm bằng luật thuần chứ không hỏi lại LLM.

    Không dùng để "sửa" câu trả lời cho đẹp: số bị xoá phải được đếm và báo cáo
    (Tuần 6 dùng nó làm một chỉ báo hallucination rẻ tiền, không cần judge).
    """
    if not invalid_citations(text, n_chunks):
        return text
    out = _CITE_RE.sub(
        lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_chunks else "", text
    )
    # Xoá dấu ngoặc để lại khoảng trắng đôi / khoảng trắng trước dấu câu.
    out = re.sub(r"[ \t]{2,}", " ", out)
    return re.sub(r"\s+([,.;:!?])", r"\1", out).strip()


def ensure_disclaimer(text: str) -> str:
    """Chốt câu miễn trừ ở cuối, kể cả khi model quên làm theo prompt.

    Prompt đã yêu cầu, nhưng yêu cầu trong prompt là **mong đợi**, không phải
    bảo đảm; câu miễn trừ thì phải là bảo đảm.
    """
    if DISCLAIMER in text:
        return text
    return f"{text.rstrip()}\n\n{DISCLAIMER}"

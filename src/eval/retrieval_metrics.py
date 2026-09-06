"""Metric truy hồi cho Tuần 3 — T3.4. Thuần Python, KHÔNG LLM, không phụ thuộc.

Ground truth là ``reference_context_ids`` của nhóm E, ghi ở **cấp BÀI**
(``doc_id``), không phải UUID chunk — DEC-025e. Lý do ở đó: point ID là
UUID5(``doc_id:chunk_idx``) mà ``chunk_idx`` **khác nhau giữa collection 256 và
512**, nên ghi UUID chunk thì ablation chunk-size không so được.

Hệ quả bắt buộc cho mọi hàm ở đây: danh sách xếp hạng đưa vào phải là
**doc_id đã bỏ trùng, giữ nguyên thứ tự** (:func:`dedup_docs`). Một bài dài
sinh nhiều chunk, top-5 chunk có thể chỉ là **1 bài** — không dedup thì
recall@5 tự phồng lên và mọi con số trong báo cáo đều sai theo.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def dedup_docs(doc_ids: Iterable[str]) -> list[str]:
    """Bỏ ``doc_id`` trùng, giữ thứ hạng của lần xuất hiện ĐẦU tiên.

    Lần đầu = thứ hạng tốt nhất mà retriever cho bài đó, nên giữ nó là đúng
    ngữ nghĩa "bài này được xếp hạng bao nhiêu".
    """
    seen: set[str] = set()
    out: list[str] = []
    for d in doc_ids:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _hits(ranked: Sequence[str], relevant: set[str], k: int) -> list[int]:
    """Vector 0/1 độ dài ``k`` — bài ở hạng i có nằm trong ground truth không."""
    return [1 if d in relevant else 0 for d in ranked[:k]]


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    """Tỉ lệ bài đúng lọt vào top-k.

    Nhóm E hiện có **đúng 1** ``reference_context_id`` mỗi câu, nên ở bộ dữ
    liệu này recall@k trùng hit@k và chỉ nhận giá trị 0 hoặc 1. Vẫn viết dạng
    tổng quát để test set mở rộng (35–40 câu, có thể nhiều bài đúng) dùng lại
    được mà không phải sửa.
    """
    if not relevant:
        return 0.0
    return sum(_hits(ranked, relevant, k)) / len(relevant)


def mrr_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    """Nghịch đảo thứ hạng của bài đúng ĐẦU TIÊN; 0 nếu không có trong top-k."""
    for i, d in enumerate(ranked[:k], start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    """nDCG nhị phân (rel = 0/1), chiết khấu ``1/log2(rank+1)``.

    IDCG lấy theo ``min(len(relevant), k)`` bài đúng xếp trên cùng — nếu lấy
    theo ``len(relevant)`` thì câu có nhiều bài đúng hơn ``k`` sẽ không bao
    giờ đạt 1.0 dù retriever làm hoàn hảo trong khả năng của top-k.
    """
    if not relevant:
        return 0.0
    dcg = sum(h / math.log2(i + 2) for i, h in enumerate(_hits(ranked, relevant, k)))
    ideal = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal))
    return dcg / idcg if idcg else 0.0


def mean(values: Iterable[float]) -> float:
    """Trung bình, rỗng thì 0.0 (tránh ZeroDivisionError rải rác ở script)."""
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def evaluate(
    ranked_per_query: Sequence[Sequence[str]],
    relevant_per_query: Sequence[set[str]],
    ks: Sequence[int] = (1, 3, 5, 10, 20),
) -> dict[str, float]:
    """Gộp metric trung bình trên toàn bộ truy vấn.

    Trả về dict phẳng ``{"recall@5": ..., "mrr@5": ..., "ndcg@5": ...}`` cho
    mọi ``k`` trong ``ks`` — dạng phẳng để đổ thẳng ra CSV/Markdown.

    ``ranked_per_query`` phải đã qua :func:`dedup_docs`.
    """
    if len(ranked_per_query) != len(relevant_per_query):
        raise ValueError(
            f"lệch số truy vấn: {len(ranked_per_query)} ranked "
            f"vs {len(relevant_per_query)} ground truth"
        )
    out: dict[str, float] = {}
    for k in ks:
        pairs = list(zip(ranked_per_query, relevant_per_query))
        out[f"recall@{k}"] = mean(recall_at_k(r, g, k) for r, g in pairs)
        out[f"mrr@{k}"] = mean(mrr_at_k(r, g, k) for r, g in pairs)
        out[f"ndcg@{k}"] = mean(ndcg_at_k(r, g, k) for r, g in pairs)
    return out

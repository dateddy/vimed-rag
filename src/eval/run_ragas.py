"""Đánh giá chất lượng RAG bằng RAGAS.

# GATED — Tuần 6. Không chạy trong scaffold.
"""

from __future__ import annotations

from src.schemas import PipelineResult


def evaluate_ragas(results: list[PipelineResult]) -> dict[str, float]:
    """Tính các chỉ số RAGAS (faithfulness, answer_relevancy, context_precision...).

    # GATED — Tuần 6: dựng dataset (question/answer/contexts/ground_truth) và
    gọi RAGAS. Trả về dict metric → điểm.
    """
    raise NotImplementedError("GATED: Tuần 6 — chạy RAGAS thật")

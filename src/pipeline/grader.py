"""Grader thuần: quy đổi rerank score của context thành GraderState.

KHÔNG gọi model/LLM. Chỉ so sánh điểm tin cậy cao nhất với 2 ngưỡng lấy
từ config (correct_threshold, incorrect_threshold).
"""

from __future__ import annotations

from src.config import GraderConfig
from src.schemas import GraderState, RetrievedChunk


class Grader:
    """Đánh giá độ liên quan của context dựa trên rerank score."""

    def __init__(self, cfg: GraderConfig) -> None:
        if cfg.incorrect_threshold > cfg.correct_threshold:
            raise ValueError(
                "incorrect_threshold không được lớn hơn correct_threshold"
            )
        self._cfg = cfg

    def score_of(self, chunks: list[RetrievedChunk]) -> float:
        """Điểm đại diện của context = rerank score cao nhất (0 nếu rỗng)."""
        if not chunks:
            return 0.0
        return max(c.score for c in chunks)

    def grade(self, chunks: list[RetrievedChunk]) -> GraderState:
        """Trả về trạng thái grade theo 2 ngưỡng.

        - score >= correct_threshold        -> CORRECT
        - score <  incorrect_threshold      -> INCORRECT
        - ở giữa                            -> AMBIGUOUS
        """
        score = self.score_of(chunks)
        if score >= self._cfg.correct_threshold:
            return GraderState.CORRECT
        if score < self._cfg.incorrect_threshold:
            return GraderState.INCORRECT
        return GraderState.AMBIGUOUS

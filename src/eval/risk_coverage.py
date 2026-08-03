"""Đường cong risk–coverage từ trace của pipeline (để hiệu chỉnh ngưỡng grader).

# GATED — Tuần 6. Không chạy trong scaffold.

Ý tưởng: đọc score ở bước GRADE trong ``trace`` làm điểm tin cậy; quét ngưỡng
để vẽ risk (tỉ lệ sai trên phần đã trả lời) theo coverage (tỉ lệ được trả lời).
Ngưỡng grader thật (correct/incorrect) sẽ được chọn từ đường cong này.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.schemas import PipelineResult


@dataclass
class RiskCoveragePoint:
    threshold: float
    coverage: float
    risk: float


def compute_risk_coverage(
    results: list[PipelineResult],
    correct_labels: list[bool],
) -> list[RiskCoveragePoint]:
    """Tính các điểm (threshold, coverage, risk) để vẽ đường cong.

    # GATED — Tuần 6: trích confidence từ trace, quét ngưỡng, tính risk/coverage.
    """
    raise NotImplementedError("GATED: Tuần 6 — dựng đường cong risk–coverage")

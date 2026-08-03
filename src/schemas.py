"""Các dataclass và enum lõi của ViMed-RAG.

Đây là "hợp đồng dữ liệu" (data contract) dùng chung cho toàn pipeline:
retrieval → grading → generation → trace. Không phụ thuộc model/data thật.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GraderState(str, Enum):
    """Trạng thái đánh giá độ liên quan của context (dựa trên rerank score)."""

    CORRECT = "CORRECT"
    AMBIGUOUS = "AMBIGUOUS"
    INCORRECT = "INCORRECT"


class TerminalAction(str, Enum):
    """Hành động cuối cùng mà pipeline chọn cho một truy vấn."""

    ANSWER = "ANSWER"
    ANSWER_WITH_CAUTION = "ANSWER_WITH_CAUTION"
    ABSTAIN = "ABSTAIN"


@dataclass
class RetrievedChunk:
    """Một đoạn văn bản được truy hồi kèm điểm tin cậy."""

    doc_id: str
    text: str
    specialty: str | None
    score: float  # rerank score — điểm tin cậy chính dùng để grade


@dataclass
class TraceStep:
    """Một bước trong nhật ký thực thi của pipeline.

    ``trace`` gồm nhiều TraceStep, phải đủ chi tiết để Tuần 6 tách metric
    theo nhánh (CORRECT/AMBIGUOUS/INCORRECT) và vẽ đường cong risk–coverage.
    """

    step: str  # RETRIEVE | GRADE | REWRITE | GENERATE | ABSTAIN
    state: str | None
    score: float | None
    note: str = ""


@dataclass
class PipelineResult:
    """Kết quả trả về của ``RAGPipeline.answer``."""

    query: str
    action: TerminalAction
    answer: str
    chunks: list[RetrievedChunk]
    trace: list[TraceStep] = field(default_factory=list)
    rewritten_query: str | None = None

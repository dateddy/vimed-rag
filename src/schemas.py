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
class ChunkRecord:
    """Một chunk ở thời điểm **INDEX** — chưa có điểm, chưa qua truy hồi.

    Tách khỏi :class:`RetrievedChunk` có chủ đích (DEC-021):

    - ``score`` là điểm rerank, **vô nghĩa** lúc index — để nó ở đây là mời gọi
      ghi rác vào payload Qdrant.
    - ``RetrievedChunk.specialty`` là **số ít**. Index qua nó thì 15 bài thuộc
      cả hai khoa chỉ vào được một khoa và Tuần 3 lọc payload sẽ âm thầm đánh
      rơi chúng — đúng lỗi DEC-017 đã cảnh báo. Ở đây dùng ``specialties``
      (tuple, giữ TẤT CẢ khoa khớp) làm trường lọc.
    - ``chunk_idx``/``n_chunks`` cần cho point ID tất định (chạy lại = upsert
      đè, không nhân đôi) và cho trích dẫn "đoạn i/n" ở Tuần 4.
    """

    doc_id: str
    chunk_idx: int
    n_chunks: int
    text: str
    specialties: tuple[str, ...] = ()
    title: str | None = None
    source: str | None = None

    @property
    def specialty(self) -> str | None:
        """Khoa đầu tiên — chỉ để hiển thị/payload 1 giá trị (DEC-017)."""
        return self.specialties[0] if self.specialties else None


@dataclass
class RetrievedChunk:
    """Một đoạn văn bản được truy hồi kèm điểm tin cậy.

    Type ở thời điểm **TRUY HỒI**. Lúc index dùng :class:`ChunkRecord`.
    """

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

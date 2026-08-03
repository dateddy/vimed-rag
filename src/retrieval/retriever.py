"""Interface truy hồi (hybrid dense+sparse → rerank) + FakeRetriever.

Real impl (Qdrant + bge-reranker-v2-m3) bị GATED. FakeRetriever cho phép
điều khiển rerank score theo từng lần gọi để test corrective loop.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.config import AppConfig
from src.retrieval.embedder import Embedder
from src.schemas import RetrievedChunk


@runtime_checkable
class Retriever(Protocol):
    """Giao diện truy hồi: query → danh sách chunk kèm rerank score."""

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        ...


class FakeRetriever:
    """Retriever giả với rerank score điều khiển được.

    Mỗi lần ``retrieve`` trả một context gồm ``n_chunks`` chunk có cùng score
    lấy tuần tự từ ``scores``. Khi hết ``scores`` thì lặp lại phần tử cuối
    (hữu ích để mô phỏng nhánh vẫn INCORRECT sau khi rewrite).

    Ví dụ:
        FakeRetriever([0.1, 0.9]) -> lần 1 score 0.1, lần 2 trở đi score 0.9.
    """

    def __init__(
        self,
        scores: list[float] | None = None,
        n_chunks: int = 3,
        specialty: str | None = None,
    ) -> None:
        self._scores = list(scores) if scores else [0.9]
        self._n_chunks = n_chunks
        self._specialty = specialty
        self._calls = 0
        self.queries: list[str] = []  # log để test kiểm tra query đã dùng

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        self.queries.append(query)
        idx = min(self._calls, len(self._scores) - 1)
        score = self._scores[idx]
        self._calls += 1
        return [
            RetrievedChunk(
                doc_id=f"fake-{idx}-{i}",
                text=f"Đoạn tài liệu mẫu {i} cho: {query}",
                specialty=self._specialty,
                score=score,
            )
            for i in range(self._n_chunks)
        ]


class HybridRetriever:
    """Retriever thật: hybrid search trên Qdrant rồi rerank bge-reranker-v2-m3.

    # GATED — không implement cho tới khi Gate 0 GO (Tuần 3).
    Sẽ: (1) embed query bằng bge-m3, (2) hybrid search top_k_dense trên Qdrant,
    (3) rerank lấy top_k_rerank, gán rerank score vào RetrievedChunk.score.
    """

    def __init__(self, cfg: AppConfig, embedder: Embedder) -> None:
        # GATED — không kết nối Qdrant / tải reranker khi khởi tạo.
        self._cfg = cfg
        self._embedder = embedder

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        raise NotImplementedError(
            "GATED: Tuần 3 — hybrid search Qdrant + rerank bge-reranker-v2-m3"
        )

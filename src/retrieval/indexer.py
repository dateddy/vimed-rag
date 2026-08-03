"""Interface đẩy vector vào vector store + FakeIndexer in-memory.

Real impl (Qdrant) bị GATED — không kết nối Qdrant khi import/test.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.config import QdrantConfig
from src.retrieval.embedder import Embedder
from src.schemas import RetrievedChunk


@runtime_checkable
class Indexer(Protocol):
    """Giao diện lập chỉ mục chunk vào vector store."""

    def index(self, chunks: list[RetrievedChunk]) -> int:
        """Đẩy chunk vào store, trả về số lượng đã index."""
        ...


class FakeIndexer:
    """Indexer giả: lưu chunk trong bộ nhớ (dùng cho test/demo)."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._embedder = embedder
        self.store: list[RetrievedChunk] = []

    def index(self, chunks: list[RetrievedChunk]) -> int:
        self.store.extend(chunks)
        return len(chunks)


class QdrantIndexer:
    """Indexer thật đẩy vector lên Qdrant collection.

    # GATED — không implement cho tới khi Gate 0 GO (Tuần 3).
    Sẽ tạo collection, upsert điểm (dense+sparse) với payload doc_id/specialty.
    """

    def __init__(self, cfg: QdrantConfig, embedder: Embedder) -> None:
        # GATED — không mở kết nối Qdrant khi khởi tạo trong scaffold.
        self._cfg = cfg
        self._embedder = embedder

    def index(self, chunks: list[RetrievedChunk]) -> int:
        raise NotImplementedError("GATED: Tuần 3 — upsert vào Qdrant thật")

"""Interface embedder + FakeEmbedder cho test/demo.

Real impl (bge-m3) bị GATED tới khi Gate 0 GO — không tải model khi import.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from src.config import ModelsConfig


@runtime_checkable
class Embedder(Protocol):
    """Giao diện sinh vector nhúng cho danh sách văn bản."""

    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Trả về list vector (mỗi vector là list[float] độ dài ``dim``)."""
        ...


class FakeEmbedder:
    """Embedder giả: vector tất định theo nội dung (seed = hash text).

    Dùng để test/demo mà không cần GPU hay model thật. Cùng text → cùng vector.
    """

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def _vector_for(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        # Sinh dim số giả ngẫu nhiên tất định trong [0, 1).
        vec: list[float] = []
        for _ in range(self.dim):
            seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
            vec.append((seed % 10_000) / 10_000.0)
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]


class BgeM3Embedder:
    """Embedder thật dùng BAAI/bge-m3 (dense + sparse).

    # GATED — không implement cho tới khi Gate 0 GO (Tuần 2).
    Sẽ nạp FlagEmbedding/sentence-transformers và sinh embedding dense+sparse.
    """

    def __init__(self, cfg: ModelsConfig) -> None:  # noqa: D401
        # GATED — không tải model khi import.
        self._cfg = cfg
        self.dim = 1024  # bge-m3 dense dim (tham khảo)

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("GATED: Tuần 2 — sinh embedding bge-m3 thật")

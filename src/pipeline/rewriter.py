"""Interface viết lại truy vấn + FakeRewriter.

Real impl (gọi LLM để rewrite) bị GATED — không gọi API khi import/test.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.config import GenerationConfig
from src.schemas import RetrievedChunk


@runtime_checkable
class Rewriter(Protocol):
    """Giao diện viết lại query khi context bị đánh giá INCORRECT."""

    def rewrite(self, query: str, chunks: list[RetrievedChunk]) -> str:
        ...


class FakeRewriter:
    """Rewriter giả: thêm hậu tố tất định (không gọi LLM)."""

    def rewrite(self, query: str, chunks: list[RetrievedChunk]) -> str:
        return f"{query} (viết lại)"


class LLMRewriter:
    """Rewriter thật dùng LLM để mở rộng/làm rõ truy vấn.

    # GATED — không implement cho tới khi Gate 0 GO (Tuần 4).
    Sẽ nạp prompt query_rewrite và gọi LLM (tính là +1 LLM call mỗi lần rewrite).
    """

    def __init__(self, cfg: GenerationConfig, api_key: str) -> None:
        # GATED — không khởi tạo client LLM trong scaffold.
        self._cfg = cfg
        self._api_key = api_key

    def rewrite(self, query: str, chunks: list[RetrievedChunk]) -> str:
        raise NotImplementedError("GATED: Tuần 4 — gọi LLM viết lại truy vấn")

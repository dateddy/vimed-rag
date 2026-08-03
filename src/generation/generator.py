"""Interface sinh câu trả lời + FakeGenerator.

Real impl (gemini-2.5-flash) bị GATED — không gọi API khi import/test.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.config import GenerationConfig
from src.schemas import RetrievedChunk


@runtime_checkable
class Generator(Protocol):
    """Giao diện sinh câu trả lời bám context, có citation."""

    def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        caution: bool = False,
    ) -> str:
        ...


class FakeGenerator:
    """Generator giả: trả chuỗi template có citation [n] (không gọi LLM)."""

    def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        caution: bool = False,
    ) -> str:
        tag = "[CẢNH BÁO độ chắc chắn thấp] " if caution else ""
        cites = " ".join(f"[{i + 1}]" for i in range(len(chunks)))
        disclaimer = " (Thông tin tham khảo, không thay thế tư vấn bác sĩ.)"
        return f"{tag}Trả lời mẫu cho: {query} {cites}".strip() + disclaimer


class GeminiGenerator:
    """Generator thật dùng gemini-2.5-flash.

    # GATED — không implement cho tới khi Gate 0 GO (Tuần 4).
    Sẽ: nạp prompt từ config/prompts, ép bám context + citation [n] + disclaimer,
    dùng bản caution khi ``caution=True``, nhiệt độ lấy từ config.
    """

    def __init__(self, cfg: GenerationConfig, api_key: str) -> None:
        # GATED — không khởi tạo client Gemini trong scaffold.
        self._cfg = cfg
        self._api_key = api_key

    def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        caution: bool = False,
    ) -> str:
        raise NotImplementedError("GATED: Tuần 4 — gọi Gemini thật")

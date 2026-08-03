"""Nạp dataset y tế tiếng Việt từ HuggingFace.

# GATED — không tải dataset thật cho tới khi Gate 0 (data sufficiency) GO.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawDocument:
    """Document thô trước khi làm sạch."""

    doc_id: str
    text: str
    specialty: str | None = None
    source: str | None = None


def load_hf_dataset(name: str, split: str = "train") -> list[RawDocument]:
    """Tải dataset từ HuggingFace và map về list[RawDocument].

    # GATED — Tuần 2: dùng `datasets.load_dataset`, lọc theo 2 chuyên khoa
    (config/specialties.yaml), trả về RawDocument. KHÔNG chạy trước Gate 0 GO.
    """
    raise NotImplementedError(
        "GATED: Tuần 2 — tải HF dataset thật (chặn cho tới khi Gate 0 GO)"
    )

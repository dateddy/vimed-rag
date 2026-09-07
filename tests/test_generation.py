"""Test tầng sinh câu trả lời — KHÔNG test nào chạm mạng hay cần API key.

``GeminiGenerator`` nhận ``transport`` tiêm được, nên toàn bộ đường đi
prompt -> model -> hậu xử lý kiểm được bằng một hàm giả. Phần chạm mạng thật
chỉ nằm trong ``_default_transport`` và được chứng minh là **không bị gọi**
(``test_no_network_without_transport``).
"""

from __future__ import annotations

import pytest

from src.config import GenerationConfig
from src.data.cleaner import strip_byline
from src.generation.context import (
    DISCLAIMER,
    citations,
    ensure_disclaimer,
    format_context,
    invalid_citations,
    strip_invalid_citations,
)
from src.generation.generator import FakeGenerator, GeminiGenerator
from src.schemas import RetrievedChunk

BYLINE_TEXT = (
    "Bài viết được tư vấn chuyên môn bởi Bác sĩ Nguyễn Văn A, Khoa Nội tim mạch, "
    "Bệnh viện Đa khoa Quốc tế Vinmec Central Park. "
    "Tăng huyết áp là bệnh lý tim mạch phổ biến."
)


def _chunks(n: int = 3) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            doc_id=f"doc{i}",
            text=f"Nội dung đoạn {i}.",
            specialty="tim_mach",
            score=0.9,
            chunk_idx=i - 1,
            n_chunks=4,
            title=f"Bài {i}",
        )
        for i in range(1, n + 1)
    ]


def _gen(reply: str) -> GeminiGenerator:
    """Generator với transport giả trả `reply` cố định."""
    return GeminiGenerator(
        cfg=GenerationConfig(temperature=0.2),
        api_key="",  # cố ý rỗng: không được dùng tới
        transport=lambda prompt, temperature: reply,
    )


# --------------------------------------------------------------------------- #
# context.py — thuần
# --------------------------------------------------------------------------- #
def test_format_context_numbers_by_position():
    """`[n]` là VỊ TRÍ trong list, không phải chunk_idx — hạ nguồn ánh xạ theo đó."""
    text = format_context(_chunks(3))
    assert text.startswith("[1] Bài 1 (đoạn 1/4)")
    assert "[2] Bài 2 (đoạn 2/4)" in text
    assert "[4]" not in text


def test_format_context_strips_byline_before_prompt():
    """Byline mang tên bác sĩ — lọt vào prompt là hệ thống trích dẫn 'BS X khẳng định…'."""
    chunk = _chunks(1)[0]
    chunk.text = BYLINE_TEXT
    out = format_context([chunk])
    assert "Bác sĩ Nguyễn Văn A" not in out
    assert "Tăng huyết áp là bệnh lý tim mạch phổ biến." in out


def test_strip_byline_is_shared_with_testset_builder():
    """Cùng một phép cắt cho test set và cho prompt (DEC-045)."""
    assert strip_byline(BYLINE_TEXT) == "Tăng huyết áp là bệnh lý tim mạch phổ biến."


def test_format_context_falls_back_to_doc_id_without_title():
    chunk = RetrievedChunk(doc_id="d9", text="x", specialty=None, score=0.5)
    assert format_context([chunk]).startswith("[1] d9\n")


def test_citations_and_invalid_detection():
    assert citations("A [1] B [2] C [1]") == [1, 2, 1]
    assert invalid_citations("A [1] B [7]", n_chunks=5) == [7]
    assert invalid_citations("A [1] B [5]", n_chunks=5) == []


def test_strip_invalid_citations_removes_only_fabricated_ones():
    out = strip_invalid_citations("Câu A [1], câu B [7], câu C [3].", n_chunks=3)
    assert "[7]" not in out
    assert "[1]" in out and "[3]" in out
    assert "  " not in out
    assert " ." not in out and " ," not in out


def test_strip_invalid_citations_is_noop_when_all_valid():
    text = "Câu A [1], câu B [2]."
    assert strip_invalid_citations(text, n_chunks=2) == text


def test_ensure_disclaimer_appends_once():
    assert ensure_disclaimer("Trả lời.").endswith(DISCLAIMER)
    already = f"Trả lời. {DISCLAIMER}"
    assert ensure_disclaimer(already) == already


# --------------------------------------------------------------------------- #
# GeminiGenerator — đường đi đầy đủ với transport giả
# --------------------------------------------------------------------------- #
def test_prompt_carries_context_and_query():
    gen = _gen("x")
    prompt = gen.build_prompt("Tăng huyết áp là gì?", _chunks(2))
    assert "{context}" not in prompt and "{query}" not in prompt
    assert "Tăng huyết áp là gì?" in prompt
    assert "[1] Bài 1" in prompt and "[2] Bài 2" in prompt


def test_caution_prompt_differs_from_normal():
    """AMBIGUOUS phải dùng bản caution — người đọc thấy được mức tin cậy."""
    gen = _gen("x")
    normal = gen.build_prompt("q", _chunks(1), caution=False)
    caution = gen.build_prompt("q", _chunks(1), caution=True)
    assert normal != caution
    assert "độ chắc chắn thấp" in caution


def test_generate_strips_fabricated_citation_and_records_it():
    """Model trích [7] khi chỉ có 3 nguồn -> xoá, nhưng phải ĐẾM được."""
    gen = _gen("Theo tài liệu [1] và [7], huyết áp cao cần theo dõi.")
    answer = gen.generate("q", _chunks(3))
    assert "[7]" not in answer
    assert "[1]" in answer
    assert gen.last_invalid_citations == [7]


def test_generate_appends_disclaimer_when_model_forgets():
    gen = _gen("Trả lời ngắn [1].")
    assert gen.generate("q", _chunks(1)).endswith(DISCLAIMER)


def test_generate_passes_temperature_from_config():
    seen: dict[str, float] = {}

    def transport(prompt: str, temperature: float) -> str:
        seen["t"] = temperature
        return "ok [1]"

    GeminiGenerator(
        cfg=GenerationConfig(temperature=0.2), api_key="", transport=transport
    ).generate("q", _chunks(1))
    assert seen["t"] == 0.2


def test_no_network_without_transport():
    """Dựng generator KHÔNG được chạm mạng; chỉ `generate()` mới đi ra ngoài.

    Không có key thì phải báo lỗi RÕ RÀNG chứ không im lặng trả rỗng — và thông
    điệp nhắc đúng cái bẫy `setx` không áp cho terminal đang mở.
    """
    gen = GeminiGenerator(cfg=GenerationConfig(temperature=0.2), api_key="")
    assert gen._transport is None  # chưa dựng client
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gen._default_transport("prompt", 0.2)


def test_generator_protocol_still_satisfied():
    """FakeGenerator và GeminiGenerator phải thay thế được cho nhau."""
    for gen in (FakeGenerator(), _gen("ok [1]")):
        assert isinstance(gen.generate("q", _chunks(1)), str)

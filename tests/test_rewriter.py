"""Test LLMRewriter — KHÔNG test nào chạm mạng hay cần API key.

Trọng tâm là ``clean_rewritten``: đầu ra model là văn bản tự do, và truy vấn
rác đi vào retriever thì lượt truy hồi thứ hai chắc chắn hỏng — mà ``max_iter=1``
nghĩa là không còn cơ hội sửa. Mỗi test dưới đây là một kiểu hỏng đã thấy ở
model thật khi bị bảo "chỉ trả về truy vấn".
"""

from __future__ import annotations

import pytest

from src.config import GenerationConfig
from src.pipeline.rewriter import (
    MAX_REWRITE_CHARS,
    FakeRewriter,
    LLMRewriter,
    clean_rewritten,
)
from src.schemas import RetrievedChunk

QUERY = "tiểu đường ăn gì"
GOOD = "chế độ ăn cho người đái tháo đường týp 2"


def _rw(reply: str) -> LLMRewriter:
    return LLMRewriter(
        cfg=GenerationConfig(temperature=0.2),
        api_key="",  # cố ý rỗng: không được dùng tới
        transport=lambda prompt, temperature: reply,
    )


# --------------------------------------------------------------------------- #
# clean_rewritten — thuần
# --------------------------------------------------------------------------- #
def test_clean_passes_through_a_good_rewrite():
    assert clean_rewritten(GOOD, fallback=QUERY) == GOOD


def test_clean_strips_label_model_adds_anyway():
    assert clean_rewritten(f"TRUY VẤN VIẾT LẠI: {GOOD}", fallback=QUERY) == GOOD
    assert clean_rewritten(f"Rewritten query: {GOOD}", fallback=QUERY) == GOOD


def test_clean_takes_first_line_when_model_explains():
    raw = f"{GOOD}\n\nGiải thích: tôi đã thêm thuật ngữ y khoa để tìm tốt hơn."
    assert clean_rewritten(raw, fallback=QUERY) == GOOD


def test_clean_strips_quotes_and_bullets():
    assert clean_rewritten(f'"{GOOD}"', fallback=QUERY) == GOOD
    assert clean_rewritten(f"- {GOOD}", fallback=QUERY) == GOOD
    assert clean_rewritten(f"* “{GOOD}”", fallback=QUERY) == GOOD


def test_clean_skips_leading_blank_lines():
    assert clean_rewritten(f"\n\n  {GOOD}\n", fallback=QUERY) == GOOD


@pytest.mark.parametrize("raw", ["", "   ", "\n\n"])
def test_clean_falls_back_on_empty(raw):
    assert clean_rewritten(raw, fallback=QUERY) == QUERY


def test_clean_falls_back_when_model_writes_an_essay():
    """Cả đoạn văn = model giải thích thay vì viết lại -> giữ truy vấn gốc.

    Thà lặp lại câu gốc: kết quả xấu nhất khi đó là ABSTAIN thật thà, không
    phải ABSTAIN vì mình tự phá câu hỏi trước khi truy hồi lần hai.
    """
    essay = "Để tìm kiếm tốt hơn " + "x" * MAX_REWRITE_CHARS
    assert clean_rewritten(essay, fallback=QUERY) == QUERY


def test_clean_keeps_query_exactly_at_the_limit():
    at_limit = "a" * MAX_REWRITE_CHARS
    assert clean_rewritten(at_limit, fallback=QUERY) == at_limit


# --------------------------------------------------------------------------- #
# LLMRewriter — đường đi đầy đủ với transport giả
# --------------------------------------------------------------------------- #
def test_prompt_carries_query_and_no_context_slot():
    """Prompt viết lại CỐ Ý không mang ngữ cảnh (DEC-046)."""
    prompt = _rw("x").build_prompt(QUERY)
    assert QUERY in prompt
    assert "{query}" not in prompt
    assert "{context}" not in prompt


def test_rewrite_ignores_chunks_by_design():
    """Truyền chunk vào cũng không được lọt vào prompt."""
    seen: dict[str, str] = {}

    def transport(prompt: str, temperature: float) -> str:
        seen["p"] = prompt
        return GOOD

    rw = LLMRewriter(
        cfg=GenerationConfig(temperature=0.2), api_key="", transport=transport
    )
    chunk = RetrievedChunk(
        doc_id="d1", text="NỘI DUNG KHÔNG LIÊN QUAN", specialty=None, score=0.1
    )
    assert rw.rewrite(QUERY, [chunk]) == GOOD
    assert "NỘI DUNG KHÔNG LIÊN QUAN" not in seen["p"]


def test_rewrite_records_fallback():
    """`last_fallback` phải phân biệt được rewrite thật với rewrite hỏng."""
    ok = _rw(GOOD)
    ok.rewrite(QUERY, [])
    assert ok.last_fallback is False

    broken = _rw("")
    assert broken.rewrite(QUERY, []) == QUERY
    assert broken.last_fallback is True


def test_rewrite_passes_temperature_from_config():
    seen: dict[str, float] = {}

    def transport(prompt: str, temperature: float) -> str:
        seen["t"] = temperature
        return GOOD

    LLMRewriter(
        cfg=GenerationConfig(temperature=0.2), api_key="", transport=transport
    ).rewrite(QUERY, [])
    assert seen["t"] == 0.2


def test_no_network_without_transport():
    """Dựng rewriter không chạm mạng; thiếu key thì báo lỗi rõ ràng."""
    rw = LLMRewriter(cfg=GenerationConfig(temperature=0.2), api_key="")
    assert rw._transport is None
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        rw._default_transport("prompt", 0.2)


def test_rewriter_protocol_still_satisfied():
    """FakeRewriter và LLMRewriter phải thay thế được cho nhau."""
    for rw in (FakeRewriter(), _rw(GOOD)):
        assert isinstance(rw.rewrite(QUERY, []), str)

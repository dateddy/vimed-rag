"""Test baseline LLM-only — KHÔNG test nào chạm mạng hay cần API key.

Hai nhóm khẳng định, nhóm thứ hai mới là nhóm quan trọng:

1. Baseline chạy đúng (prompt, disclaimer, temperature từ config).
2. **Baseline KHÔNG lẫn được vào đường RAG.** Một baseline cắm nhầm vào
   `RAGPipeline` sẽ tạo ra hệ thống trông như RAG trong `trace` nhưng vứt hết
   ngữ cảnh — kiểu hỏng tệ nhất có thể có ở chương kết quả, vì bảng số trông
   vẫn hợp lý.
"""

from __future__ import annotations

import pytest

from src.config import GenerationConfig, load_prompt
from src.generation.baseline import BaselineGenerator
from src.generation.context import DISCLAIMER
from src.generation.generator import Generator

QUERY = "Tăng huyết áp có nguy hiểm không?"


def _baseline(reply: str) -> BaselineGenerator:
    return BaselineGenerator(
        cfg=GenerationConfig(temperature=0.2),
        api_key="",  # cố ý rỗng: không được dùng tới
        transport=lambda prompt, temperature: reply,
    )


# --------------------------------------------------------------------------- #
# 1. Chạy đúng
# --------------------------------------------------------------------------- #
def test_prompt_carries_query():
    prompt = _baseline("x").build_prompt(QUERY)
    assert QUERY in prompt
    assert "{query}" not in prompt


def test_answer_appends_disclaimer():
    """Chốt miễn trừ ở CẢ HAI nhánh, nếu không khác biệt Tuần 6 lẫn dòng chữ."""
    assert _baseline("Có, khá nguy hiểm.").answer(QUERY).endswith(DISCLAIMER)


def test_passes_temperature_from_config():
    seen: dict[str, float] = {}

    def transport(prompt: str, temperature: float) -> str:
        seen["t"] = temperature
        return "ok"

    BaselineGenerator(
        cfg=GenerationConfig(temperature=0.2), api_key="", transport=transport
    ).answer(QUERY)
    assert seen["t"] == 0.2


def test_no_network_without_transport():
    b = BaselineGenerator(cfg=GenerationConfig(temperature=0.2), api_key="")
    assert b._transport is None
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        b._default_transport("prompt", 0.2)


# --------------------------------------------------------------------------- #
# 2. Không lẫn được vào đường RAG
# --------------------------------------------------------------------------- #
def test_baseline_is_not_a_generator():
    """Không hợp Protocol -> không cắm nhầm vào RAGPipeline được."""
    assert not isinstance(_baseline("x"), Generator)
    assert not hasattr(_baseline("x"), "generate")


def test_baseline_prompt_has_no_context_slot():
    """Có `{context}` trong prompt thì nó thôi là baseline LLM-only."""
    assert "{context}" not in load_prompt("baseline_llm_only")


def test_build_prompt_rejects_a_context_slot(monkeypatch):
    """Ai đó thêm {context} vào prompt sau này -> phải NỔ, không im lặng."""
    monkeypatch.setattr(
        "src.generation.baseline.load_prompt",
        lambda name: "Ngữ cảnh: {context}\nCâu hỏi: {query}",
    )
    with pytest.raises(ValueError, match="baseline"):
        _baseline("x").build_prompt(QUERY)


def test_baseline_prompt_stays_a_fair_opponent():
    """Baseline phải là đối thủ CÔNG BẰNG, không phải hình nộm.

    Bỏ lời mời "nói rõ là không chắc chắn" đi thì baseline bịa nhiều hơn và
    "% giảm hallucination" của Tuần 6 tăng lên vì mình dàn xếp, không vì hệ
    thống tốt. Sai lệch đó KHÔNG nhìn ra được từ bảng kết quả.
    """
    tpl = load_prompt("baseline_llm_only")
    assert "không chắc chắn" in tpl
    assert "trợ lý y tế tiếng Việt" in tpl
    assert DISCLAIMER in tpl

"""Test cache đáp án LLM — thuần đĩa, không chạm mạng, không cần API key.

Cache này sinh ra vì hạn mức **20 lượt/ngày** của free tier (DEC-053): trong lúc
phát triển, mỗi lần chạy lại một script là ăn vào đúng cái quota mà Tuần 6 cần.
Nên hai tính chất phải khoá lại bằng test:

1. Khoá phải phân biệt được model/temperature/prompt — trộn khoá là trả nhầm
   đáp án của cấu hình khác, và sai kiểu đó **im lặng hoàn toàn**.
2. Cache hit KHÔNG được đi ra mạng (đó là toàn bộ lý do nó tồn tại).
"""

from __future__ import annotations

import pytest

from src.llm import LlmCache, gemini_call


def _cache(tmp_path):
    return LlmCache(tmp_path / "llm_cache.json")


def test_key_separates_model_temperature_and_prompt(tmp_path):
    c = _cache(tmp_path)
    base = c.key("gemini-2.5-flash", 0.2, "xin chào")
    assert base != c.key("gemini-2.5-pro", 0.2, "xin chào")
    assert base != c.key("gemini-2.5-flash", 0.9, "xin chào")
    assert base != c.key("gemini-2.5-flash", 0.2, "xin chào bạn")
    assert base == c.key("gemini-2.5-flash", 0.2, "xin chào")


def test_put_then_get_survives_reload(tmp_path):
    """Ghi xuống đĩa ngay, vì tiến trình có thể chết giữa lô dài."""
    c = _cache(tmp_path)
    k = c.key("m", 0.2, "p")
    c.put(k, "đáp án")
    again = LlmCache(tmp_path / "llm_cache.json")
    assert again.get(k) == "đáp án"


def test_miss_and_hit_are_counted(tmp_path):
    c = _cache(tmp_path)
    k = c.key("m", 0.2, "p")
    assert c.get(k) is None
    c.put(k, "x")
    assert c.get(k) == "x"
    assert (c.hits, c.misses) == (1, 1)


def test_cache_hit_never_touches_network(tmp_path):
    """Cache hit phải trả về TRƯỚC cả khi import SDK.

    Nếu test này đỏ thì cache không cứu được quota — đúng thứ nó sinh ra để làm.
    Máy chạy test không cài `google-genai` vẫn phải xanh.
    """
    c = _cache(tmp_path)
    c.put(c.key("gemini-2.5-flash", 0.2, "prompt"), "đáp án đã cache")
    out = gemini_call(
        "prompt", 0.2, api_key="khoa-gia", model="gemini-2.5-flash", cache=c
    )
    assert out == "đáp án đã cache"


def test_cache_hit_marks_usage_as_cached(tmp_path):
    """Bảng chi phí phải phân biệt được lượt cache với lượt gọi thật.

    Không có cờ này thì một lần chạy có cache sẽ báo 0 token và bảng chi phí
    Tuần 7 thành vô nghĩa.
    """
    c = _cache(tmp_path)
    c.put(c.key("m", 0.2, "p"), "x")
    usage: dict = {}
    gemini_call("p", 0.2, api_key="k", model="m", cache=c, usage_out=usage)
    assert usage["cached"] is True
    assert usage["total_tokens"] is None


def test_missing_key_still_raises_before_cache_lookup(tmp_path):
    """Thiếu key vẫn báo lỗi rõ ràng, không bị cache che mất."""
    c = _cache(tmp_path)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gemini_call("p", 0.2, api_key="", model="m", cache=c)

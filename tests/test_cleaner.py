"""Test cho src.data.cleaner: NFC, strip HTML, min-length, dedup thô."""

import unicodedata

from src.data.cleaner import clean_documents, normalize_text, strip_html


def test_strip_html_removes_tags_and_entities():
    out = strip_html("<p>Huyết&nbsp;áp <b>cao</b></p>")
    assert "<" not in out and ">" not in out
    assert "&nbsp;" not in out
    assert "Huyết" in out and "cao" in out


def test_normalize_text_is_nfc():
    # 'e' + combining acute accent -> phải gộp thành 'é' (NFC).
    decomposed = "café"
    out = normalize_text(decomposed)
    assert out == unicodedata.normalize("NFC", "café")
    assert unicodedata.is_normalized("NFC", out)


def test_normalize_collapses_whitespace():
    assert normalize_text("a\n\t  b   c") == "a b c"


def test_clean_documents_drops_short():
    docs = ["ngắn", "x" * 50]
    out = clean_documents(docs, min_length=30)
    assert len(out) == 1
    assert out[0] == "x" * 50


def test_clean_documents_dedup_rough():
    long = "Bệnh tiểu đường cần theo dõi đường huyết thường xuyên mỗi ngày."
    docs = [long, long.upper(), long]  # trùng nội dung (khác hoa/thường)
    out = clean_documents(docs, min_length=10)
    assert len(out) == 1

"""Test cho src.data.loader: chính sách gán khoa DEC-016 + build/save/load.

Toàn bộ test chạy trên row GIẢ — không tải HuggingFace, không cần HF_TOKEN.
Nếu một test ở đây bắt đầu cần mạng thì loader đã vi phạm ràng buộc "không
chạm dataset thật lúc test".
"""

import json

import pytest

from src.config import DataConfig
from src.data.loader import (
    RawDocument,
    build_documents,
    compile_specialty_patterns,
    load_documents,
    make_doc_id,
    match_specialties,
    save_documents,
    specialty_counts,
)

SPECIALTIES = {
    "tim_mach": ["tim mạch", "huyết áp", "cholesterol"],
    "tieu_duong": ["tiểu đường", "insulin"],
}


def make_cfg(min_count: int = 3, min_chars: int = 10) -> DataConfig:
    """DataConfig nhỏ cho test — ngưỡng thấp để không phải viết bài 25 keyword."""
    return DataConfig(
        dataset="fake/dataset",
        split="test",
        title_col="title",
        content_col="content",
        min_article_chars=min_chars,
        processed_dir="data/processed",
        specialty_min_keyword_count=min_count,
    )


@pytest.fixture
def patterns():
    return compile_specialty_patterns(SPECIALTIES)


# --------------------------------------------------------------------------- #
# match_specialties — chính sách DEC-016
# --------------------------------------------------------------------------- #
def test_keyword_in_title_matches_regardless_of_count(patterns):
    # Ở tiêu đề là đủ, dù thân bài không nhắc lại lần nào.
    hits = match_specialties(
        "Bệnh tiểu đường type 2", "Nội dung không nhắc lại từ khoá.", patterns, 25
    )
    assert hits == ["tieu_duong"]


def test_body_below_threshold_does_not_match(patterns):
    # 2 lần < ngưỡng 3 -> loại. Đây chính là ca "Nho khô có tốt cho bạn không?".
    body = "Thực phẩm này giúp giảm cholesterol và ổn định cholesterol."
    assert match_specialties("Nho khô có tốt cho bạn không?", body, patterns, 3) == []


def test_body_at_threshold_matches(patterns):
    body = "cholesterol cao làm tăng huyết áp; theo dõi huyết áp mỗi ngày."
    # tim_mach: cholesterol 1 + huyết áp 2 = 3 >= 3.
    assert match_specialties("Ăn uống lành mạnh", body, patterns, 3) == ["tim_mach"]


def test_counts_are_summed_across_keywords_of_one_specialty(patterns):
    # 3 keyword khác nhau, mỗi cái 1 lần -> vẫn đạt ngưỡng 3.
    body = "Bệnh tim mạch, chỉ số huyết áp và cholesterol đều cần theo dõi."
    assert "tim_mach" in match_specialties("Sức khoẻ", body, patterns, 3)


def test_word_boundary_prevents_substring_match(patterns):
    # "insulinoma" là u tuỵ, không phải bài tiểu đường -> không được khớp "insulin".
    body = "insulinoma insulinoma insulinoma insulinoma"
    assert match_specialties("Khối u hiếm gặp", body, patterns, 3) == []


def test_match_is_case_and_html_insensitive(patterns):
    hits = match_specialties("<b>TIỂU ĐƯỜNG</b> thai kỳ", "", patterns, 25)
    assert hits == ["tieu_duong"]


def test_article_can_match_both_specialties(patterns):
    hits = match_specialties("Biến chứng tim mạch của tiểu đường", "", patterns, 25)
    assert hits == ["tim_mach", "tieu_duong"]


def test_no_match_returns_empty(patterns):
    assert match_specialties("Gãy xương cẳng tay", "Bó bột 6 tuần.", patterns, 3) == []


# --------------------------------------------------------------------------- #
# build_documents
# --------------------------------------------------------------------------- #
def test_build_documents_tags_and_counts():
    rows = [
        {"title": "Bệnh tiểu đường type 2", "content": "Nội dung đủ dài để giữ lại."},
        {"title": "Suy tim mạch mạn tính", "content": "Nội dung đủ dài để giữ lại."},
        {"title": "Gãy xương cẳng tay", "content": "Bó bột trong sáu tuần liền."},
    ]
    docs, stats = build_documents(rows, SPECIALTIES, make_cfg(), source="fake/dataset")

    assert len(docs) == 2
    assert stats.total == 2
    assert stats.per_specialty == {"tim_mach": 1, "tieu_duong": 1}
    assert stats.skipped_no_specialty == 1
    assert stats.both == 0
    assert all(doc.source == "fake/dataset" for doc in docs)


def test_build_documents_skips_short_and_duplicate():
    long_body = "Theo dõi đường huyết đều đặn giúp kiểm soát bệnh tốt hơn."
    rows = [
        {"title": "Tiểu đường", "content": long_body},
        {"title": "Tiểu đường", "content": long_body},  # trùng
        {"title": "Tiểu đường", "content": ""},  # quá ngắn
    ]
    docs, stats = build_documents(rows, SPECIALTIES, make_cfg(min_chars=40))

    assert len(docs) == 1
    assert stats.skipped_duplicate == 1
    assert stats.skipped_short == 1


def test_build_documents_records_both_specialties():
    rows = [
        {
            "title": "Biến chứng tim mạch ở người tiểu đường",
            "content": "Nội dung đủ dài để không bị loại vì quá ngắn.",
        }
    ]
    docs, stats = build_documents(rows, SPECIALTIES, make_cfg())

    assert docs[0].specialties == ("tim_mach", "tieu_duong")
    assert docs[0].specialty == "tim_mach"  # khoa đầu theo thứ tự config
    assert stats.both == 1
    assert stats.per_specialty == {"tim_mach": 1, "tieu_duong": 1}


def test_build_documents_handles_missing_and_none_columns():
    rows = [{"content": None}, {}, {"title": None, "content": None}]
    docs, stats = build_documents(rows, SPECIALTIES, make_cfg())

    assert docs == []
    assert stats.skipped_short == 3


def test_doc_id_is_deterministic_across_runs():
    rows = [{"title": "Tiểu đường", "content": "Nội dung đủ dài để giữ lại nhé."}]
    first, _ = build_documents(rows, SPECIALTIES, make_cfg())
    second, _ = build_documents(rows, SPECIALTIES, make_cfg())

    assert first[0].doc_id == second[0].doc_id == make_doc_id(first[0].text)


def test_stats_meets_floor():
    rows = [
        {"title": f"Tiểu đường bài {i}", "content": "Nội dung đủ dài để giữ lại."}
        for i in range(3)
    ]
    _, stats = build_documents(rows, SPECIALTIES, make_cfg())

    assert stats.per_specialty["tieu_duong"] == 3
    assert not stats.meets_floor(2)  # tim_mach = 0 -> không đạt
    assert not stats.meets_floor(150)


def test_threshold_comes_from_config_not_hardcoded():
    """Đổi ngưỡng trong config phải đổi kết quả — chống hard-code 25 trong loader."""
    rows = [
        {
            "title": "Ăn uống lành mạnh",
            "content": "Giảm cholesterol, ổn định huyết áp, đo huyết áp hằng ngày.",
        }
    ]
    lenient, _ = build_documents(rows, SPECIALTIES, make_cfg(min_count=3))
    strict, _ = build_documents(rows, SPECIALTIES, make_cfg(min_count=99))

    assert lenient[0].specialties == ("tim_mach",)
    assert strict == []


# --------------------------------------------------------------------------- #
# save / load / đếm
# --------------------------------------------------------------------------- #
def test_save_and_load_roundtrip(tmp_path):
    docs = [
        RawDocument(
            doc_id="abc123",
            text="Tiểu đường type 2 cần theo dõi đường huyết.",
            specialty="tieu_duong",
            source="fake/dataset",
            title="Tiểu đường type 2",
            specialties=("tieu_duong",),
        )
    ]
    out = tmp_path / "nested" / "corpus.jsonl"
    assert save_documents(docs, out) == 1

    # Ghi đúng UTF-8, không escape tiếng Việt -> đọc bằng mắt được.
    raw = out.read_text(encoding="utf-8").strip()
    assert "Tiểu đường" in raw
    assert json.loads(raw)["specialties"] == ["tieu_duong"]

    assert load_documents(out) == docs


def test_specialty_counts_counts_both_specialties():
    docs = [
        RawDocument("a", "x", "tim_mach", specialties=("tim_mach",)),
        RawDocument("b", "y", "tim_mach", specialties=("tim_mach", "tieu_duong")),
    ]
    assert specialty_counts(docs) == {"tim_mach": 2, "tieu_duong": 1}


# --------------------------------------------------------------------------- #
# ràng buộc: import không kéo theo dataset thật
# --------------------------------------------------------------------------- #
def test_importing_loader_does_not_import_datasets():
    """`datasets` phải được import TRỄ, bên trong load_hf_dataset."""
    import ast
    import inspect

    import src.data.loader as loader

    tree = ast.parse(inspect.getsource(loader))
    module_level_imports = {
        alias.name.split(".")[0]
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    module_level_imports |= {
        node.module.split(".")[0]
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "datasets" not in module_level_imports

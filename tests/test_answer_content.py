"""Test cho `src/eval/answer_content.py` — tầng NỘI DUNG của câu trả lời (B4).

Thuần văn bản: không LLM, không mạng, không đọc `data/`.
"""

from __future__ import annotations

from src.eval.answer_content import (
    REFUSAL_WINDOW,
    coverage_two_layers,
    is_refusal_text,
    refusal_ids,
)

# Ba câu trả lời THẬT, chép nguyên văn từ `data/processed/runs.jsonl`.
E21 = (
    "Ngữ cảnh được cung cấp không chứa thông tin về vai trò của siêu âm tim "
    "trong chẩn đoán bệnh cơ tim phì đại.\n\nThông tin chỉ mang tính tham "
    "khảo, không thay thế tư vấn của bác sĩ."
)
A01 = (
    "Ngữ cảnh không chứa thông tin về vai trò của siêu âm tim trong chẩn "
    "đoán, đánh giá, xác định nguyên nhân và mức độ nghiêm trọng của âm thổi "
    "tim (tiếng thổi ở tim, tiếng tim bất thường).\n\nThông tin chỉ mang tính "
    "tham khảo, không thay thế tư vấn của bác sĩ."
)
E01 = (
    "Biến chứng loét chân ở bệnh nhân tiểu đường có thể dẫn đến những biến "
    "chứng nguy hiểm như hoại tử các ngón chân, tàn phế, cắt cụt chi [1]."
)


def rec(id_, group, answer, action="ANSWER"):
    return {"id": id_, "group": group, "answer": answer, "action": action}


class TestIsRefusalText:
    def test_hai_ca_that(self):
        assert is_refusal_text(E21)
        assert is_refusal_text(A01)

    def test_cau_that_khong_bi_cham_nham(self):
        assert not is_refusal_text(E01)

    def test_rong(self):
        assert not is_refusal_text("")
        assert not is_refusal_text(None)  # type: ignore[arg-type]

    def test_chi_quet_cua_so_dau(self):
        """Ghi chú "tài liệu không đề cập…" ở CUỐI một câu trả lời thật."""
        dai = "x" * (REFUSAL_WINDOW + 50)
        assert not is_refusal_text(dai + " tài liệu không đề cập tới liều trẻ em")


class TestCoverageTwoLayers:
    """⚠️ Bất biến của B4 — số chính là tầng HÀNH ĐỘNG, không phải nội dung."""

    def test_con_so_that_cua_lo_hien_tai(self):
        """17/21 theo action · 16/21 theo nội dung — E-21 là câu chênh."""
        recs = (
            [rec(f"E-{i:02d}", "E", E01) for i in range(1, 17)]     # 16 câu thật
            + [rec("E-21", "E", E21)]                               # 1 câu từ chối
            + [rec(f"E-{i:02d}", "E", "", action="ABSTAIN") for i in (17, 18, 19, 20)]
        )
        out = coverage_two_layers(
            recs, answered=lambda r: r["action"] == "ANSWER", group="E"
        )
        assert out["n"] == 21
        assert out["action"] == 17          # SỐ CHÍNH — mọi DEC đang trích
        assert out["content"] == 16         # số độ nhạy
        assert out["refusal_ids"] == ["E-21"]

    def test_chenh_dung_bang_so_cau_tu_choi(self):
        recs = [rec("E-01", "E", E01), rec("E-21", "E", E21)]
        out = coverage_two_layers(recs, answered=lambda r: True)
        assert out["action"] - out["content"] == len(out["refusal_ids"])

    def test_chi_dem_trong_nhom_duoc_hoi(self):
        """A-01 cũng là câu từ chối nhưng KHÔNG được lọt vào coverage nhóm E."""
        recs = [rec("E-01", "E", E01), rec("A-01", "A", A01)]
        out = coverage_two_layers(recs, answered=lambda r: True, group="E")
        assert out["n"] == 1
        assert out["refusal_ids"] == []

    def test_khong_ai_tra_loi_thi_ca_hai_bang_0(self):
        recs = [rec("E-01", "E", E01, action="ABSTAIN")]
        out = coverage_two_layers(recs, answered=lambda r: False)
        assert out["action"] == 0 and out["content"] == 0

    def test_nhom_rong(self):
        out = coverage_two_layers([], answered=lambda r: True)
        assert out == {"n": 0, "action": 0, "content": 0, "refusal_ids": []}


class TestRefusalIds:
    def test_dung_hai_ca_tren_lo_that(self):
        recs = [
            rec("E-01", "E", E01),
            rec("E-21", "E", E21),
            rec("A-01", "A", A01),
            rec("A-02", "A", E21, action="ABSTAIN"),  # ABSTAIN -> không tính
        ]
        assert refusal_ids(recs) == ["A-01", "E-21"]

    def test_answer_with_caution_cung_tinh(self):
        """Nhánh AMBIGUOUS vẫn TRẢ LỜI, nên nó cũng nằm trong mẫu số."""
        recs = [rec("E-05", "E", E21, action="ANSWER_WITH_CAUTION")]
        assert refusal_ids(recs) == ["E-05"]


def test_module_khong_vay_muon_gi_nang():
    """Ràng buộc #2: thuần văn bản, import không kéo theo gì."""
    import subprocess
    import sys

    mã = (
        "import sys; import src.eval.answer_content as m; "
        "nang = {'ragas','openai','torch','transformers','qdrant_client'}; "
        "du = nang & set(sys.modules); "
        "assert not du, du; print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", mã], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout

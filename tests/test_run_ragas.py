"""Test cho `src/eval/run_ragas.py`.

Toàn bộ chạy bằng **judge giả** — không mạng, không API, và **không cần
`ragas` cài trong máy** (ràng buộc #2). Đó là lý do `Judge` được thiết kế
thành một callable ba tham số thay vì để module ôm lấy đối tượng của ragas.
"""

from __future__ import annotations

import pytest

from src.eval.answer_content import is_refusal_text
from src.eval.run_ragas import (
    DEFAULT_JUDGE_MODEL,
    FaithRow,
    FaithSummary,
    retrieval_metrics,
    score_records,
)

# Hai câu trả lời THẬT, chép nguyên văn từ `data/processed/runs.jsonl`.
ANSWER_E21 = (
    "Ngữ cảnh được cung cấp không chứa thông tin về vai trò của siêu âm tim "
    "trong chẩn đoán bệnh cơ tim phì đại.\n\nThông tin chỉ mang tính tham "
    "khảo, không thay thế tư vấn của bác sĩ."
)
ANSWER_A01 = (
    "Ngữ cảnh không chứa thông tin về vai trò của siêu âm tim trong chẩn "
    "đoán, đánh giá, xác định nguyên nhân và mức độ nghiêm trọng của âm thổi "
    "tim (tiếng thổi ở tim, tiếng tim bất thường).\n\nThông tin chỉ mang tính "
    "tham khảo, không thay thế tư vấn của bác sĩ."
)
ANSWER_E01 = (
    "Biến chứng loét chân ở bệnh nhân tiểu đường có thể dẫn đến những biến "
    "chứng nguy hiểm như hoại tử các ngón chân, tàn phế, cắt cụt chi [1]."
)


def rec(id_, group="E", answer=ANSWER_E01, n_ctx=5, gold=None):
    return {
        "id": id_,
        "group": group,
        "user_input": "câu hỏi?",
        "answer": answer,
        "retrieved": [
            {"doc_id": f"d{i}", "text": f"đoạn {i}"} for i in range(n_ctx)
        ],
        "reference_context_ids": gold or [],
    }


def judge_const(value):
    return lambda q, a, c: value


# ------------------------------------------------------- is_refusal_text
class TestIsRefusalText:
    def test_hai_ca_that_tren_59_cau(self):
        """`E-21` và `A-01` — đúng 2 ca trên toàn bộ lô, đã quét xác nhận."""
        assert is_refusal_text(ANSWER_E21)
        assert is_refusal_text(ANSWER_A01)

    def test_cau_tra_loi_that_khong_bi_cham_nham(self):
        assert not is_refusal_text(ANSWER_E01)

    def test_rong_va_none(self):
        assert not is_refusal_text("")
        assert not is_refusal_text(None)  # type: ignore[arg-type]

    def test_chi_quet_phan_dau(self):
        """Câu trả lời THẬT có nhắc 'tài liệu không đề cập' ở CUỐI thì không tính.

        Nếu quét cả bài, một câu trả lời đầy đủ kèm ghi chú *"tài liệu không đề
        cập tới liều cho trẻ em"* sẽ bị đếm nhầm thành lời từ chối, và mẫu số
        B4 phình ra một cách âm thầm.
        """
        dai = ANSWER_E01 + " " + "Chi tiết thêm về điều trị. " * 30
        assert not is_refusal_text(dai + " Tài liệu không đề cập tới liều trẻ em.")

    def test_bat_duoc_bien_the_chua_du_thong_tin(self):
        assert is_refusal_text("Ngữ cảnh được cung cấp chưa đủ thông tin để trả lời.")


# ------------------------------------------------------- score_records
class TestScoreRecords:
    def test_tach_cau_tu_choi_khoi_trung_binh(self):
        """⚠️ Bất biến QUAN TRỌNG NHẤT của module.

        Câu từ chối ra faithfulness 0,0 (đo thật 2026-09-11). Gộp nó vào trung
        bình thì hệ càng an toàn điểm càng thấp — bảng sẽ nói ngược sự thật.
        """
        recs = [rec("E-01"), rec("E-21", answer=ANSWER_E21)]
        judge = lambda q, a, c: 0.0 if is_refusal_text(a) else 0.8  # noqa: E731
        s = score_records(recs, judge, arm="corrective")

        assert len(s.rows) == 2
        assert len(s.substantive) == 1
        assert len(s.refusals) == 1
        assert s.mean_faithfulness == pytest.approx(0.8)  # KHÔNG phải 0.4

    def test_khong_co_thuoc_tinh_trung_binh_toan_bo(self):
        """Cố ý không tồn tại — để không ai vô tình gọi nhầm."""
        s = FaithSummary(arm="x")
        assert not hasattr(s, "mean_all")
        assert not hasattr(s, "mean_overall")

    def test_rong_thi_tra_none_chu_khong_phai_0(self):
        """0,0 và 'không có dữ liệu' là hai tình trạng khác hẳn nhau."""
        s = score_records([rec("E-21", answer=ANSWER_E21)], judge_const(0.0),
                          arm="corrective")
        assert s.mean_faithfulness is None

    def test_bo_qua_ban_ghi_khong_co_ngu_canh(self):
        recs = [rec("E-01"), rec("E-02", n_ctx=0)]
        s = score_records(recs, judge_const(1.0), arm="corrective")
        assert [r.id for r in s.rows] == ["E-01"]

    def test_llm_only_muon_ngu_canh_cua_nhanh_khac(self):
        """Nhánh LLM-only không truy hồi -> phải mượn ngữ cảnh, có nhãn riêng."""
        baseline = [{"id": "E-01", "group": "E", "user_input": "q",
                     "answer": ANSWER_E01}]
        s = score_records(
            baseline, judge_const(0.3), arm="llm_only",
            contexts_by_id={"E-01": ["đoạn a", "đoạn b"]},
        )
        assert len(s.rows) == 1
        assert s.rows[0].n_contexts == 2
        assert s.mean_faithfulness == pytest.approx(0.3)

    def test_llm_only_thieu_ngu_canh_thi_bo_qua(self):
        baseline = [{"id": "X-99", "group": "A", "user_input": "q", "answer": "a"}]
        s = score_records(baseline, judge_const(1.0), arm="llm_only",
                          contexts_by_id={})
        assert s.rows == []


# ------------------------------------------------- hai máy dò B4 đối chứng
class TestHaiMayDo:
    def test_khop_nhau_thi_disagreement_rong(self):
        recs = [rec("E-01"), rec("E-21", answer=ANSWER_E21)]
        judge = lambda q, a, c: 0.0 if is_refusal_text(a) else 0.8  # noqa: E731
        s = score_records(recs, judge, arm="corrective")
        assert s.zero_scored_ids == ["E-21"]
        assert s.disagreement() == []

    def test_cau_tra_loi_that_ma_bia_het_cung_ra_0(self):
        """Lệch KHÔNG phải lỗi — hai máy dò đo hai thứ khác nhau.

        Một câu trả lời thật nhưng bịa hoàn toàn cũng ra 0,0 mà không phải lời
        từ chối. `disagreement()` chỉ CHỈ CHỖ để soi tay, không phán quyết.
        """
        recs = [rec("E-01"), rec("E-21", answer=ANSWER_E21)]
        s = score_records(recs, judge_const(0.0), arm="corrective")
        assert set(s.zero_scored_ids) == {"E-01", "E-21"}
        assert s.disagreement() == ["E-01"]


# --------------------------------------------------- metric truy hồi
class TestRetrievalMetrics:
    def test_dung_lai_retrieval_metrics_khong_dung_ragas(self):
        recs = [rec("E-01", gold=["d0"]), rec("E-02", gold=["d2"])]
        out = retrieval_metrics(recs, ks=(1, 5))
        assert out["n_queries"] == 2.0
        assert out["recall@5"] == pytest.approx(1.0)
        assert out["recall@1"] == pytest.approx(0.5)   # chỉ E-01 có vàng ở hạng 1

    def test_bo_qua_cau_khong_co_ground_truth(self):
        """Nhóm A/B không có `reference_context_ids` -> KHÔNG tính là 0.

        Tính 0 cho câu vốn không có đáp án vàng là bịa ra một thất bại không
        tồn tại, và nó sẽ kéo tụt mọi con số truy hồi của bảng.
        """
        recs = [rec("E-01", gold=["d0"]), rec("A-01", group="A")]
        out = retrieval_metrics(recs, ks=(5,))
        assert out["n_queries"] == 1.0
        assert out["recall@5"] == pytest.approx(1.0)

    def test_khong_co_cau_nao_thi_tra_dict_rong(self):
        assert retrieval_metrics([rec("A-01", group="A")]) == {}


# ------------------------------------------------------------- judge thật
class TestJudgeThat:
    def test_khong_import_ragas_o_cap_module(self):
        """Ràng buộc #2: import module này KHÔNG được kéo ragas/openai vào."""
        import subprocess
        import sys

        mã = (
            "import sys; import src.eval.run_ragas; "
            "assert 'ragas' not in sys.modules, 'run_ragas kéo ragas lúc import'; "
            "assert 'openai' not in sys.modules, 'run_ragas kéo openai lúc import'; "
            "print('ok')"
        )
        r = subprocess.run([sys.executable, "-c", mã], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "ok" in r.stdout

    def test_judge_mac_dinh_khac_ho_voi_generator(self):
        """⚠️ Cả mục đích của việc chọn judge — khoá lại.

        Generator dùng `google/gemini-2.5-flash`. Judge cùng họ Gemini thì phép
        đo mất tính độc lập. Đổi mặc định sang `google/*` phải là quyết định
        có ý thức, không phải một lần sửa chuỗi cho tiện.
        """
        assert not DEFAULT_JUDGE_MODEL.startswith("google/")
        assert DEFAULT_JUDGE_MODEL == "openai/gpt-5"


def test_src_khong_import_langchain_hay_langgraph():
    """⛔ RÀNG BUỘC CỨNG #1, khoá bằng máy chứ không bằng lời hứa.

    `ragas` kéo về **35 gói**, trong đó có **langgraph 1.2.11** — đúng thư viện
    mà ràng buộc #1 gọi tên. DEC-022 phân định rằng điều đó chấp nhận được vì
    ragas là eval chạy OFFLINE, còn `RAGPipeline._route()` vẫn Python thuần.

    Phân định ấy chỉ đứng vững chừng nào **code của repo không thật sự dùng**
    hai thư viện đó. Test này là chỗ kiểm điều kiện ấy — để câu trả lời trước
    hội đồng là một phép kiểm chạy được, không phải một lời cam đoan.
    """
    import ast
    from pathlib import Path

    cam = ("langchain", "langgraph")
    root = Path(__file__).resolve().parents[1] / "src"
    pham: list[str] = []

    for path in root.rglob("*.py"):
        cay = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(cay):
            ten: list[str] = []
            if isinstance(n, ast.Import):
                ten = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                ten = [n.module]
            for t in ten:
                if t.split(".")[0].replace("_", "") in cam or any(
                    t.startswith(c) for c in cam
                ):
                    pham.append(f"{path.relative_to(root)}:{n.lineno} -> {t}")

    assert not pham, "src/ import thư viện bị cấm bởi ràng buộc #1:\n" + "\n".join(pham)


def test_faithrow_bat_bien():
    r = FaithRow(id="E-01", group="E", arm="corrective", faithfulness=0.7,
                 n_contexts=5, refusal=False)
    assert r.substantive
    with pytest.raises(Exception):
        r.faithfulness = 0.9  # type: ignore[misc]

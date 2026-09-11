"""Khoá bảng 4 nhánh + bản ghi Static RAG.

Trọng tâm KHÔNG phải "hàm chạy được" mà là ba chỗ bảng này có thể sai lặng lẽ:

1. ``corrective_t1`` dựng lại từ lượt 1 — nhầm một trạng thái là bảng vẫn ra số
   nhưng chênh lệch 3->4 (giá trị vòng lặp, DEC-057) sai dấu.
2. Ô **theo cấu tạo** của ``static_rag`` phải được đánh dấu, không được lẫn vào
   ô đo được (bẫy DEC-051).
3. ``llm_only`` phải ra ``None``, KHÔNG ra 0 — 0 đọc thành "đã đo và bằng không".
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.arms import (  # noqa: E402
    ARMS,
    answered_at_turn1,
    arm_row,
    build_table,
    count_group,
    fmt_cell,
)
from src.eval.trace_export import (  # noqa: E402
    build_static_record,
    chunk_from_json,
    chunk_json,
)
from src.schemas import RetrievedChunk  # noqa: E402


def corrective(qid, group, action, turn1_state=None, n_turns=1):
    """Bản ghi corrective tối thiểu. ``turn1_state=None`` = không có lượt nào."""
    turns = []
    if turn1_state is not None:
        turns = [{"i": i, "state": turn1_state if i == 0 else "INCORRECT"}
                 for i in range(n_turns)]
    return {
        "id": qid, "group": group, "system": "corrective",
        "action": action, "turns": turns,
    }


def baseline(qid, group):
    return {"id": qid, "group": group, "system": "baseline_llm_only", "answer": "x"}


def static(qid, group, expected):
    return build_static_record(
        {"id": qid, "group": group, "expected_action": expected, "user_input": "q"},
        "câu trả lời", [{"doc_id": "d", "score": 0.5}],
    )


# --------------------------------------------------------------------------- #
# 1. corrective_t1 — ba trạng thái, đừng gộp
# --------------------------------------------------------------------------- #
def test_turn1_incorrect_thi_khong_tra_loi_du_hе_that_da_tra_loi():
    """Câu lọt lưới SAU rewrite (A-01/A-08 của DEC-056) phải bị nhánh t1 chặn.

    Đây là ô làm nên chênh lệch 3->4. Sai ở đây thì kết quả âm của DEC-057
    biến mất khỏi bảng mà bảng vẫn ra số.
    """
    rec = corrective("A-01", "A", "ANSWER", turn1_state="INCORRECT", n_turns=2)
    assert answered_at_turn1(rec) is False
    assert count_group([rec], "corrective_t1", ("A", "B"))["answered"] == 0
    assert count_group([rec], "corrective", ("A", "B"))["answered"] == 1


def test_turn1_correct_thi_hai_nhanh_trung_nhau():
    rec = corrective("E-01", "E", "ANSWER", turn1_state="CORRECT")
    assert answered_at_turn1(rec) is True
    assert count_group([rec], "corrective_t1", ("E",))["answered"] == 1


def test_ambiguous_o_luot_1_van_la_tra_loi():
    """AMBIGUOUS -> ANSWER_WITH_CAUTION, vẫn là đã trả lời (ANSWERING_ACTIONS)."""
    rec = corrective("A-08", "A", "ANSWER_WITH_CAUTION", turn1_state="AMBIGUOUS")
    assert answered_at_turn1(rec) is True


def test_khong_co_luot_nao_la_policy_gate_chan_giu_nguyen_ket_cuc():
    """Nhóm D: không rewrite nào chạm tới được, nhánh t1 phải giữ nguyên ABSTAIN."""
    rec = corrective("D-01", "D", "ABSTAIN", turn1_state=None)
    assert answered_at_turn1(rec) is False
    d = arm_row([rec], "corrective_t1")["policy_blocked"]
    assert d["blocked"] == 1 and d["n"] == 1


# --------------------------------------------------------------------------- #
# 2. Ô theo cấu tạo phải được đánh dấu
# --------------------------------------------------------------------------- #
def test_static_rag_danh_dau_ba_o_theo_cau_tao():
    row = arm_row([static("A-01", "A", "ABSTAIN")], "static_rag")
    assert set(row["by_construction"]) == {"leakage", "coverage", "policy_blocked"}


def test_cac_nhanh_khac_khong_co_o_nao_theo_cau_tao():
    for arm in ("llm_only", "corrective_t1", "corrective"):
        assert arm_row([], arm)["by_construction"] == []


def test_static_rag_luon_tra_loi_nen_leakage_bang_toan_bo_nhom():
    recs = [static("A-01", "A", "ABSTAIN"), static("B-01", "B", "ABSTAIN")]
    assert count_group(recs, "static_rag", ("A", "B")) == {
        "n": 2, "answered": 2, "ids": ["A-01", "B-01"], "measured": True
    }


def test_fmt_cell_gan_dau_thap_cho_o_theo_cau_tao():
    cell = {"n": 30, "answered": 30}
    assert fmt_cell(cell).endswith("%)")
    assert fmt_cell(cell, by_construction=True).endswith("†")


# --------------------------------------------------------------------------- #
# 3. llm_only phải là None, không phải 0
# --------------------------------------------------------------------------- #
def test_llm_only_ra_none_chu_khong_ra_khong():
    cell = count_group([baseline("A-01", "A")], "llm_only", ("A", "B"))
    assert cell["answered"] is None, "0 đọc thành 'đã đo và bằng không'"
    assert cell["measured"] is False
    assert cell["n"] == 1, "vẫn phải đếm được mẫu số"


def test_fmt_cell_noi_ro_can_ragas():
    assert "RAGAS" in fmt_cell({"n": 30, "answered": None})


def test_delta_lien_quan_toi_llm_only_la_none():
    table = build_table([baseline("A-01", "A"), static("A-01", "A", "ABSTAIN")])
    d = next(x for x in table["deltas"] if x["to"] == "static_rag")
    assert d["leakage"] is None


# --------------------------------------------------------------------------- #
# 4. Bảng đầy đủ — chênh lệch đúng chiều
# --------------------------------------------------------------------------- #
def test_chenh_lech_t1_toi_day_du_bat_duoc_ket_qua_am_dec057():
    """Vòng lặp làm lọt thêm 1 câu A/B -> delta leakage phải DƯƠNG."""
    recs = [
        corrective("A-01", "A", "ANSWER", turn1_state="INCORRECT", n_turns=2),
        corrective("A-02", "A", "ABSTAIN", turn1_state="INCORRECT", n_turns=2),
        static("A-01", "A", "ABSTAIN"),
        static("A-02", "A", "ABSTAIN"),
    ]
    table = build_table(recs)
    d = next(x for x in table["deltas"] if x["to"] == "corrective")
    assert d["leakage"] == 1, "vòng lặp thêm 1 câu lọt lưới"

    d2 = next(x for x in table["deltas"] if x["to"] == "corrective_t1")
    assert d2["leakage"] == -2, "hiệu chỉnh chặn cả 2 câu static đã trả lời"


def test_bang_du_bon_nhanh_dung_thu_tu_cong_don():
    table = build_table([])
    assert table["arms"] == ARMS == (
        "llm_only", "static_rag", "corrective_t1", "corrective"
    )
    assert [d["to"] for d in table["deltas"]] == list(ARMS[1:])


# --------------------------------------------------------------------------- #
# 5. chunk_json <-> chunk_from_json khứ hồi
# --------------------------------------------------------------------------- #
def test_chunk_khu_hoi_giu_nguyen_moi_truong_dua_vao_prompt():
    c = RetrievedChunk(
        doc_id="abc", text="nội dung", specialty="tim_mach", score=0.87,
        chunk_idx=1, n_chunks=3, title="Tiêu đề", source="nguồn",
    )
    back = chunk_from_json(chunk_json(c))
    for f in ("doc_id", "text", "specialty", "score", "chunk_idx",
              "n_chunks", "title", "source"):
        assert getattr(back, f) == getattr(c, f), f


def test_chunk_khu_hoi_mat_specialties_va_do_la_co_y():
    c = RetrievedChunk(
        doc_id="a", text="t", specialty="tim_mach", score=0.5,
        specialties=("tim_mach", "tieu_duong"),
    )
    assert chunk_from_json(chunk_json(c)).specialties == ()


def test_chunk_from_json_khong_no_khi_thieu_text():
    """``with_text=False`` vẫn dựng lại được, chỉ mất nội dung."""
    c = RetrievedChunk(doc_id="a", text="t", specialty=None, score=0.5)
    assert chunk_from_json(chunk_json(c, with_text=False)).text == ""


# --------------------------------------------------------------------------- #
# 6. build_static_record — cờ cảnh báo phải đi theo bản ghi
# --------------------------------------------------------------------------- #
def test_static_record_mang_co_theo_cau_tao():
    rec = static("A-01", "A", "ABSTAIN")
    assert rec["action_by_construction"] is True
    assert rec["action"] == "ANSWER"
    assert rec["system"] == "static_rag"


def test_static_record_leaked_dung_theo_expected_action():
    assert static("A-01", "A", "ABSTAIN")["leaked"] is True
    assert static("E-01", "E", "ANSWER")["leaked"] is False


def test_static_record_khong_bao_gio_tu_choi():
    """Không có TerminalAction nào khác -> refused luôn False, kể cả nhóm E."""
    for grp, exp in (("A", "ABSTAIN"), ("E", "ANSWER"), ("D", "ABSTAIN")):
        assert static(f"{grp}-01", grp, exp)["refused"] is False


# --------------------------------------------------------------------------- #
# PA 3 (DEC-062) — cờ biến thể khái niệm + độ nhạy
# --------------------------------------------------------------------------- #
from src.eval.arms import (  # noqa: E402
    content_leakage,
    flagged_ids,
    mechanism_split,
)


def _var(qid, cls, conf="clear"):
    return {"id": qid, "class": cls, "confidence": conf}


def _ver(qid, asserts, concept=None):
    r = {"id": qid, "asserts_about_entity": asserts}
    if concept is not None:
        r["concept_in_corpus"] = concept
    return r


def test_bien_the_biet_duoc_KHONG_lam_lung_lay_nhan():
    """Biệt dược vắng + hoạt chất có -> nhãn ABSTAIN VẪN ĐÚNG, không gắn cờ.

    Sai chỗ này là bỏ luôn A-09/A-10/A-11/B-10 khỏi mẫu số, tức vứt 4 câu mà
    nhãn hoàn toàn đứng vững — thông tin theo sản phẩm không suy ra được từ
    bài viết về hoạt chất.
    """
    v = [_var("A-11", "variant_generic_of_brand"), _var("A-02", "variant_same_concept")]
    assert flagged_ids(v) == {"A-02"}


def test_no_variant_khong_gan_co():
    assert flagged_ids([_var("B-09", "no_variant")]) == set()


def test_co_yeu_tach_duoc_khoi_co_ro():
    v = [_var("A-02", "variant_same_concept", "clear"),
         _var("A-04", "variant_same_concept", "weak")]
    assert flagged_ids(v, include_weak=True) == {"A-02", "A-04"}
    assert flagged_ids(v, include_weak=False) == {"A-02"}


def test_do_nhay_khong_dung_toi_con_so_chinh():
    """`headline` phải giữ NGUYÊN mẫu số — đó là toàn bộ lý do chọn PA 3.

    Bỏ câu khỏi mẫu số là quyết định diễn giải; con số chính không được đụng
    tới, nếu không thì lại đúng lỗi chọn theo kết quả mà PA 3 sinh ra để tránh.
    """
    ver = [_ver("A-02", True, True), _ver("A-11", True, True), _ver("B-09", False)]
    var = [_var("A-02", "variant_same_concept"),
           _var("A-11", "variant_generic_of_brand"),
           _var("B-09", "no_variant")]
    out = content_leakage(ver, var)
    assert (out["headline"]["leaked"], out["headline"]["n"]) == (2, 3)
    assert (out["strict"]["leaked"], out["strict"]["n"]) == (1, 2)
    assert out["strict"]["dropped"] == ["A-02"]


def test_co_gan_ca_cho_cau_he_thong_da_tu_choi_dung():
    """Cờ theo TIÊU CHÍ, không theo kết cục — nếu không, độ nhạy cũng bị chọn lọc.

    `A-17` có biến thể trong corpus nhưng Static RAG đã từ chối đúng. Nó vẫn
    phải bị loại khỏi mẫu số ở nhánh `strict`.
    """
    ver = [_ver("A-17", False), _ver("A-02", True, True)]
    var = [_var("A-17", "variant_same_concept"), _var("A-02", "variant_same_concept")]
    out = content_leakage(ver, var)
    assert out["strict"]["n"] == 0
    assert set(out["strict"]["dropped"]) == {"A-02", "A-17"}


def test_nhan_chua_quyet_khong_vao_mau_so():
    ver = [_ver("A-01", None), _ver("B-09", False)]
    assert content_leakage(ver, [])["headline"]["n"] == 1


def test_tach_thay_the_thuc_the_khoi_bia_tu_do():
    """Hai cơ chế cần vá khác nhau -> không được gộp vào một con số."""
    ver = [_ver("A-11", True, True), _ver("A-13", True, False), _ver("B-09", False)]
    out = mechanism_split(ver)
    assert out["substitution"] == ["A-11"]
    assert out["fabrication"] == ["A-13"]
    assert out["unknown"] == []


def test_thieu_concept_in_corpus_thi_bao_unknown_chu_khong_im_lang():
    out = mechanism_split([_ver("A-08", True)])
    assert out["unknown"] == ["A-08"]
    assert out["substitution"] == [] and out["fabrication"] == []

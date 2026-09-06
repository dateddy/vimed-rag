"""Test metric truy hồi (Tuần 3 — T3.4).

Bất biến quan trọng nhất: **phải dedup theo `doc_id` trước khi tính**. Ground
truth nhóm E ở cấp BÀI (DEC-025e), mà một bài dài sinh nhiều chunk — top-5
chunk có thể chỉ là 1 bài. Quên dedup thì recall@5 tự phồng và **mọi con số
trong báo cáo sai theo**, không có gì khác báo động.

Toàn bộ file thuần Python, không mạng, không model.
"""

import pytest

from src.eval.retrieval_metrics import (
    dedup_docs,
    evaluate,
    mean,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)


# --------------------------------------------------------------------------- #
# dedup — cái bẫy chunk-vs-bài
# --------------------------------------------------------------------------- #
def test_dedup_giu_thu_hang_lan_dau():
    assert dedup_docs(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_dedup_rong():
    assert dedup_docs([]) == []


def test_nam_chunk_cua_mot_bai_chi_tinh_la_mot():
    """Top-5 toàn chunk của bài 'a' -> chỉ có 1 bài, không phải 5."""
    chunks = ["a", "a", "a", "a", "a"]
    assert len(dedup_docs(chunks)) == 1


def test_khong_dedup_thi_recall_phong_len():
    """Minh hoạ hậu quả: cùng dữ liệu, dedup hay không cho kết quả khác nhau."""
    chunks = ["x", "x", "x", "x", "a"]  # 'a' đúng, nằm hạng 5
    relevant = {"a"}

    # Không dedup: 'a' vẫn ở hạng 5 -> lọt top-5.
    assert recall_at_k(chunks, relevant, 5) == 1.0
    # Dedup: chỉ còn ["x", "a"] -> 'a' lên hạng 2, MRR khác hẳn.
    deduped = dedup_docs(chunks)
    assert mrr_at_k(chunks, relevant, 5) == pytest.approx(1 / 5)
    assert mrr_at_k(deduped, relevant, 5) == pytest.approx(1 / 2)


# --------------------------------------------------------------------------- #
# recall
# --------------------------------------------------------------------------- #
def test_recall_bai_dung_o_top1():
    assert recall_at_k(["a", "b", "c"], {"a"}, 5) == 1.0


def test_recall_bai_dung_ngoai_top_k():
    assert recall_at_k(["b", "c", "a"], {"a"}, 2) == 0.0


def test_recall_nhieu_bai_dung():
    """Tổng quát cho test set mở rộng: 1/2 bài đúng lọt top-3."""
    assert recall_at_k(["a", "x", "y", "b"], {"a", "b"}, 3) == pytest.approx(0.5)


def test_recall_khong_co_ground_truth_tra_0():
    assert recall_at_k(["a"], set(), 5) == 0.0


# --------------------------------------------------------------------------- #
# MRR
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("pos,expected", [(1, 1.0), (2, 0.5), (3, 1 / 3), (4, 0.25)])
def test_mrr_theo_thu_hang(pos, expected):
    ranked = ["x"] * (pos - 1) + ["a"]
    assert mrr_at_k(ranked, {"a"}, 10) == pytest.approx(expected)


def test_mrr_lay_bai_dung_dau_tien():
    assert mrr_at_k(["x", "a", "b"], {"a", "b"}, 5) == pytest.approx(0.5)


def test_mrr_ngoai_top_k_tra_0():
    assert mrr_at_k(["x", "y", "a"], {"a"}, 2) == 0.0


# --------------------------------------------------------------------------- #
# nDCG
# --------------------------------------------------------------------------- #
def test_ndcg_hoan_hao_bang_1():
    assert ndcg_at_k(["a", "b", "x"], {"a", "b"}, 5) == pytest.approx(1.0)


def test_ndcg_khong_trung_bang_0():
    assert ndcg_at_k(["x", "y"], {"a"}, 5) == 0.0


def test_ndcg_giam_theo_thu_hang():
    top1 = ndcg_at_k(["a", "x", "y"], {"a"}, 5)
    top3 = ndcg_at_k(["x", "y", "a"], {"a"}, 5)
    assert top1 == pytest.approx(1.0)
    assert 0.0 < top3 < top1


def test_ndcg_nhieu_bai_dung_hon_k_van_dat_duoc_1():
    """IDCG lấy min(len(relevant), k) — nếu không, k nhỏ không bao giờ đạt 1."""
    assert ndcg_at_k(["a", "b"], {"a", "b", "c"}, 2) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# evaluate — gộp
# --------------------------------------------------------------------------- #
def test_evaluate_tra_dict_phang_du_moi_k():
    out = evaluate([["a"], ["b"]], [{"a"}, {"b"}], ks=(1, 5))
    assert out["recall@1"] == 1.0
    assert out["mrr@5"] == 1.0
    assert set(out) == {
        "recall@1", "mrr@1", "ndcg@1",
        "recall@5", "mrr@5", "ndcg@5",
    }


def test_evaluate_trung_binh_tren_cac_truy_van():
    """1 câu đúng ở hạng 1, 1 câu trượt -> recall trung bình 0.5."""
    out = evaluate([["a"], ["x"]], [{"a"}, {"b"}], ks=(5,))
    assert out["recall@5"] == pytest.approx(0.5)


def test_evaluate_lech_so_truy_van_bao_loi():
    with pytest.raises(ValueError, match="lệch số truy vấn"):
        evaluate([["a"]], [{"a"}, {"b"}])


def test_mean_rong_tra_0():
    assert mean([]) == 0.0

"""Khoá đường cong risk–coverage.

Trọng tâm KHÔNG phải "hàm chạy được" mà là bốn chỗ đường cong này có thể sai
lặng lẽ — và cả bốn đều ra số trông hợp lý khi sai:

1. **Nhóm D lọt vào đường cong.** D bị policy gate chặn TRƯỚC retrieval nên
   không có điểm tin cậy nào; đưa vào là bịa số, mà mẫu số vẫn đẹp (59 thay vì
   51) nên không ai thấy.
2. **Quy ước biên ``>=`` đổi thành ``>``.** Lệch đúng một câu, và lệch ở đúng
   những ca sát biên — tức đúng những ca đường cong sinh ra để soi.
3. **``risk`` của tập rỗng trả 0.0.** Nó vẽ ra một điểm "hoàn hảo" ở coverage 0
   và kéo biên hiệu quả sai hẳn.
4. **Vách bị làm mượt.** Nếu có ngưỡng nào cho coverage 18 với leakage < 9 thì
   kết luận "câu E kế tiếp giá 9 câu lọt" sai — và đó là kết luận chính.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.risk_coverage import (  # noqa: E402
    RiskCoveragePoint,
    candidate_thresholds,
    cliff,
    compare_sources,
    compute_risk_coverage,
    coverage_gap,
    dominates,
    free_band,
    is_on_frontier,
    operating_point,
    pareto_frontier,
    point_at,
    scores_from_calibration,
    scores_from_runs,
)


def s(qid, group, lg):
    return {"id": qid, "group": group, "logit": lg}


def bipolar():
    """Bản thu nhỏ của phân bố thật: A/B thấp, E lưỡng cực, một vực ở giữa.

    3 câu A/B ở {-2, 0, +1}, 4 câu E ở {-1.5, -1, +3, +4}. Ngưỡng +2 cho
    coverage 2/4 với leakage 0/3; muốn thêm câu E phải tụt xuống dưới -1, và
    khi đó 2/3 câu A/B lọt. Cùng hình dạng bậc thang với dữ liệu thật.
    """
    return [
        s("A-1", "A", -2.0), s("A-2", "A", 0.0), s("B-1", "B", 1.0),
        s("E-1", "E", -1.5), s("E-2", "E", -1.0), s("E-3", "E", 3.0),
        s("E-4", "E", 4.0),
    ]


# --------------------------------------------------------------------------- #
# 1. Nhóm D phải nằm NGOÀI đường cong
# --------------------------------------------------------------------------- #
def test_nhom_D_bi_loai_khoi_calibration():
    payload = {"scores": [
        {"qid": "A-01", "group": "A", "max_logit": 1.0},
        {"qid": "E-01", "group": "E", "max_logit": 5.0},
        {"qid": "D-01", "group": "D", "max_logit": 9.9},
    ]}
    out = scores_from_calibration(payload)
    assert [x["id"] for x in out] == ["A-01", "E-01"]
    assert all(x["group"] != "D" for x in out)


def test_nhom_D_bi_loai_khoi_runs_vi_turns_rong():
    """Câu D có `turns` rỗng (policy gate chặn trước retrieval) -> không có điểm."""
    recs = [
        {"id": "E-01", "group": "E", "system": "corrective",
         "turns": [{"i": 0, "logit": 5.0}]},
        {"id": "D-01", "group": "D", "system": "corrective", "turns": []},
        {"id": "A-01", "group": "A", "system": "corrective",
         "turns": [{"i": 0, "logit": 1.0}]},
    ]
    out = scores_from_runs(recs)
    assert sorted(x["id"] for x in out) == ["A-01", "E-01"]


def test_runs_bo_qua_nhanh_baseline():
    """`runs.jsonl` chứa cả baseline LLM-only — nó không có điểm tin cậy nào."""
    recs = [
        {"id": "E-01", "group": "E", "system": "baseline_llm_only", "turns": []},
        {"id": "E-01", "group": "E", "system": "corrective",
         "turns": [{"i": 0, "logit": 5.0}]},
    ]
    assert len(scores_from_runs(recs)) == 1


def test_runs_suy_nguoc_logit_khi_thieu_truong():
    """Bản ghi cũ chỉ có `score` -> phải suy ngược bằng `trace_export.logit`."""
    recs = [{"id": "E-01", "group": "E", "system": "corrective",
             "turns": [{"i": 0, "score": 0.5}]}]
    out = scores_from_runs(recs)
    assert len(out) == 1
    assert abs(out[0]["logit"]) < 1e-9   # sigmoid 0.5 -> logit 0


# --------------------------------------------------------------------------- #
# 2. Quy ước biên: `>=`, khớp đúng grader thật
# --------------------------------------------------------------------------- #
def test_bien_la_lon_hon_hoac_bang():
    """Câu ĐÚNG BẰNG ngưỡng phải được tính là ĐÃ TRẢ LỜI.

    Grader thật dùng `score >= incorrect_threshold`. Đổi sang `>` là lệch một
    câu ở đúng ca sát biên.
    """
    sc = [s("E-1", "E", 2.0), s("A-1", "A", 2.0)]
    p = point_at(sc, 2.0)
    assert p.cov_e == 1, "câu E đúng bằng ngưỡng phải được trả lời"
    assert p.leak_ab == 1, "câu A/B đúng bằng ngưỡng phải tính là lọt"


def test_ngat_ngay_tren_bien_thi_khong_ai_duoc_tra_loi():
    sc = [s("E-1", "E", 2.0), s("A-1", "A", 2.0)]
    p = point_at(sc, 2.0000001)
    assert (p.cov_e, p.leak_ab) == (0, 0)


# --------------------------------------------------------------------------- #
# 3. `risk` của tập rỗng là None, KHÔNG phải 0.0
# --------------------------------------------------------------------------- #
def test_risk_tap_rong_la_None():
    p = point_at(bipolar(), 99.0)
    assert p.n_answered == 0
    assert p.risk is None, "0.0 sẽ vẽ ra một điểm hoàn hảo ở coverage 0"


def test_risk_bang_lot_tren_da_tra_loi():
    p = RiskCoveragePoint(threshold=0.0, n_ab=30, leak_ab=9, n_e=21, cov_e=18)
    assert p.n_answered == 27
    assert p.risk == 9 / 27
    assert p.coverage == 18 / 21
    assert p.leakage == 9 / 30


def test_risk_o_coverage_toi_da_bang_ti_le_test_set():
    """Bẫy lớn nhất của module: risk ở coverage 100% CHỈ là tỉ lệ A/B của test set."""
    sc = bipolar()
    p = min(compute_risk_coverage(sc), key=lambda x: x.threshold)
    assert p.cov_e == p.n_e and p.leak_ab == p.n_ab
    assert p.risk == p.n_ab / (p.n_ab + p.n_e)


# --------------------------------------------------------------------------- #
# 4. Vách không được làm mượt
# --------------------------------------------------------------------------- #
def test_nguong_ung_vien_la_diem_quan_sat_duoc_khong_noi_suy():
    sc = bipolar()
    cands = candidate_thresholds(sc)
    obs = sorted({x["logit"] for x in sc})
    assert cands[:-1] == obs, "không được chèn ngưỡng nào giữa hai điểm quan sát"
    assert cands[-1] > obs[-1], "phải có một ngưỡng trên đỉnh (coverage 0)"


def test_candidate_thresholds_rong_khi_khong_co_diem():
    assert candidate_thresholds([]) == []


def test_khong_ton_tai_diem_re_hon_de_phu_them_cau_E():
    """Kết luận chính: câu E kế tiếp có một cái GIÁ, và không đường vòng nào rẻ hơn."""
    sc = bipolar()
    pts = compute_risk_coverage(sc)
    op = point_at(sc, 2.0)
    assert (op.cov_e, op.leak_ab) == (2, 0)

    c = cliff(pts, from_cov_e=op.cov_e)
    assert c is not None
    assert c["extra_leak"] == 2, "phủ thêm câu E nào cũng tốn đúng 2 câu lọt"
    # Không ngưỡng nào phủ hơn mà lọt ít hơn cái giá đó.
    assert not [p for p in pts if p.cov_e > op.cov_e and p.leak_ab < c["extra_leak"]]


def test_cliff_None_khi_da_cham_dinh_coverage():
    pts = compute_risk_coverage(bipolar())
    assert cliff(pts, from_cov_e=4) is None


def test_coverage_gap_do_dung_do_rong_bac_thang():
    g = coverage_gap(bipolar(), 2.0)
    assert g["lowest_answered"] == 3.0
    assert g["highest_rejected"] == -1.0
    assert g["gap"] == 4.0


def test_coverage_gap_None_khi_moi_cau_E_cung_mot_phia():
    assert coverage_gap(bipolar(), -99.0) is None   # tất cả được trả lời
    assert coverage_gap(bipolar(), +99.0) is None   # tất cả bị từ chối


def test_free_band_ton_tai_va_giam_lot_mien_phi():
    """Dải mà coverage đứng yên trong khi leakage tụt. Rỗng = đánh đổi liên tục."""
    pts = compute_risk_coverage(bipolar())
    band = free_band(pts, cov_e=2)
    assert band is not None
    assert band["leak_saved"] > 0, "phải giảm được lọt mà không mất coverage"
    assert band["lo"].cov_e == band["hi"].cov_e == 2
    assert band["hi"].threshold > band["lo"].threshold


# --------------------------------------------------------------------------- #
# 5. Đơn điệu — hai bất biến của mọi đường cong ngưỡng
# --------------------------------------------------------------------------- #
def test_coverage_va_leakage_don_dieu_khong_tang_theo_nguong():
    pts = sorted(compute_risk_coverage(bipolar()), key=lambda p: p.threshold)
    for a, b in zip(pts, pts[1:]):
        assert b.cov_e <= a.cov_e, "nâng ngưỡng không thể làm phủ nhiều hơn"
        assert b.leak_ab <= a.leak_ab, "nâng ngưỡng không thể làm lọt nhiều hơn"


def test_mau_so_giu_nguyen_tren_moi_diem():
    """Mẫu số đổi giữa các điểm = có câu bị rơi khỏi tập, tức đang đo hai thứ."""
    pts = compute_risk_coverage(bipolar())
    assert len({(p.n_ab, p.n_e) for p in pts}) == 1


# --------------------------------------------------------------------------- #
# 6. Biên hiệu quả tính trên (cov_e, leak_ab), KHÔNG trên risk
# --------------------------------------------------------------------------- #
def test_dominates_can_hon_han_o_it_nhat_mot_chieu():
    a = RiskCoveragePoint(0.0, 30, 5, 21, 17)
    same = RiskCoveragePoint(1.0, 30, 5, 21, 17)
    assert not dominates(a, same), "bằng nhau thì không ai trội ai"
    assert dominates(RiskCoveragePoint(1.0, 30, 4, 21, 17), a)   # lọt ít hơn
    assert dominates(RiskCoveragePoint(1.0, 30, 5, 21, 18), a)   # phủ nhiều hơn
    assert not dominates(RiskCoveragePoint(1.0, 30, 4, 21, 16), a)  # đánh đổi


def test_pareto_loai_diem_bi_troi_han():
    pts = compute_risk_coverage(bipolar())
    front = pareto_frontier(pts)
    assert front, "biên không được rỗng"
    for p in pts:
        if p not in front:
            assert any(dominates(q, p) for q in front)


def test_vung_that_chat_vo_ich_bi_loai_khoi_bien():
    """Ngưỡng cao hơn mức cần để lọt = 0 thì chỉ mất coverage — phải bị trội hẳn."""
    pts = compute_risk_coverage(bipolar())
    front = pareto_frontier(pts)
    zero_leak = [p for p in front if p.leak_ab == 0]
    assert len(zero_leak) == 1, "chỉ điểm phủ nhiều nhất trong vùng lọt-0 được ở lại"
    assert zero_leak[0].cov_e == max(p.cov_e for p in pts if p.leak_ab == 0)


def test_diem_van_hanh_nam_tren_bien():
    sc = bipolar()
    pts = compute_risk_coverage(sc)
    assert is_on_frontier(point_at(sc, 2.0), pts)


def test_diem_van_hanh_ngoai_bien_bi_bat():
    """Ngưỡng quá cao: lọt vẫn 0 nhưng phủ ít hơn -> phải báo NGOÀI biên."""
    sc = bipolar()
    pts = compute_risk_coverage(sc)
    assert not is_on_frontier(point_at(sc, 3.5), pts)


def test_operating_point_nhan_thang_sigmoid():
    """Config lưu sigmoid; hàm phải tự quy đổi, không bắt gọi bên ngoài quy đổi."""
    sc = [s("E-1", "E", 1.0), s("A-1", "A", -1.0)]
    p = operating_point(sc, 0.5)        # sigmoid 0.5 -> logit 0
    assert (p.cov_e, p.leak_ab) == (1, 0)


# --------------------------------------------------------------------------- #
# 7. Đối chứng chéo hai nguồn
# --------------------------------------------------------------------------- #
def test_compare_sources_khop_trong_dung_sai():
    a = [s("E-1", "E", 1.0), s("A-1", "A", -1.0)]
    b = [s("E-1", "E", 1.0 + 1e-7), s("A-1", "A", -1.0)]
    r = compare_sources(a, b)
    assert r["ok"] and r["n_common"] == 2 and not r["mismatched"]


def test_compare_sources_bat_lech_that():
    a = [s("E-1", "E", 1.0)]
    b = [s("E-1", "E", 1.5)]
    r = compare_sources(a, b)
    assert not r["ok"]
    assert r["mismatched"] == ["E-1"]
    assert r["max_diff"] == 0.5


def test_compare_sources_bat_cau_thieu_mot_ben():
    a = [s("E-1", "E", 1.0), s("E-2", "E", 2.0)]
    b = [s("E-1", "E", 1.0)]
    r = compare_sources(a, b)
    assert not r["ok"], "thiếu câu là lệch, dù các câu chung đều khớp"
    assert r["only_a"] == ["E-2"] and r["only_b"] == []


def test_compare_sources_rong():
    r = compare_sources([], [])
    assert r["ok"] and r["n_common"] == 0 and r["max_diff"] == 0.0


# --------------------------------------------------------------------------- #
# 8. Ca biên
# --------------------------------------------------------------------------- #
def test_khong_co_diem_nao():
    assert compute_risk_coverage([]) == []


def test_toan_cau_AB_thi_coverage_luon_0():
    sc = [s("A-1", "A", 1.0), s("B-1", "B", 2.0)]
    for p in compute_risk_coverage(sc):
        assert p.n_e == 0 and p.cov_e == 0
        assert p.coverage == 0.0, "mẫu số 0 không được làm nổ ZeroDivision"


def test_toan_cau_E_thi_leakage_luon_0():
    sc = [s("E-1", "E", 1.0), s("E-2", "E", 2.0)]
    for p in compute_risk_coverage(sc):
        assert p.n_ab == 0 and p.leak_ab == 0
        assert p.leakage == 0.0
        assert p.risk in (None, 0.0)


def test_diem_trung_nhau_khong_lam_hong_duong_cong():
    """Hai câu cùng điểm -> một ngưỡng ứng viên, cả hai cùng đổi phía."""
    sc = [s("E-1", "E", 1.0), s("E-2", "E", 1.0), s("A-1", "A", 0.0)]
    cands = candidate_thresholds(sc)
    assert len(cands) == 3, "hai câu trùng điểm chỉ sinh MỘT ngưỡng ứng viên"
    p = point_at(sc, 1.0)
    assert p.cov_e == 2


def test_thresholds_truyen_tay_duoc_sap_xep():
    sc = bipolar()
    pts = compute_risk_coverage(sc, thresholds=[3.0, -1.0, 1.0])
    assert [p.threshold for p in pts] == [-1.0, 1.0, 3.0]

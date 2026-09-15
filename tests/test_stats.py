"""Test cho `src/eval/stats.py` — module thống kê dùng chung.

⚠️ **VÌ SAO FILE NÀY SINH RA MUỘN (B1).** `stats.py` ra đời ở Session 13 để gộp
ba bản sao của `wilson`/`rule_of_three`/`fmt_pct`/`sign_test`. Lúc gộp có chạy
một phép đối chứng rất kỹ — 1.890 cặp `(k, n)` và 3.005 vector hiệu — nhưng phép
đó chạy **một lần rồi vứt**, không có gì giữ lại trong repo. Nên tới B1, module
mà ba script phụ thuộc vào lại là module **không có một test trực tiếp nào**.
File này vá chỗ đó.

Thuần số: không LLM, không mạng, không đọc `data/`. Chạy mili-giây.
"""

from __future__ import annotations

import math

import pytest

from src.eval.stats import Z, fmt_pct, quantile, rule_of_three, sign_test, wilson


# --------------------------------------------------------------- wilson
class TestWilson:
    def test_khoang_luon_nam_trong_0_1(self):
        """Đây là lý do tồn tại của Wilson trong repo này — Wald thì không."""
        for n in range(1, 61):
            for k in range(n + 1):
                lo, hi = wilson(k, n)
                assert 0.0 <= lo <= hi <= 1.0, f"({k}, {n}) -> ({lo}, {hi})"

    def test_khoang_bao_lay_ti_le_quan_sat(self):
        for n in range(1, 61):
            for k in range(n + 1):
                lo, hi = wilson(k, n)
                assert lo <= k / n <= hi, f"({k}, {n}) không bao p={k / n}"

    def test_0_tren_30_ra_0_den_11_phan_tram(self):
        """Con số B1 chốt đem đi báo cáo. Khoá lại để không trôi."""
        lo, hi = wilson(0, 30)
        assert lo == 0.0
        assert round(100 * hi) == 11

    def test_wald_se_sai_o_dung_cho_nay(self):
        """0/30 thì Wald ra [0, 0] = 'chứng minh được leakage bằng 0' — sai.

        Test này không kiểm `wilson`; nó khoá **lý do** chọn Wilson, để ai đó
        sau này định 'đơn giản hoá' sang Wald thì thấy ngay hậu quả.
        """
        p = 0 / 30
        wald_half = Z * math.sqrt(p * (1 - p) / 30)
        assert wald_half == 0.0
        assert wilson(0, 30)[1] > 0.0

    def test_k_bang_0_cho_can_duoi_dung_bang_0(self):
        for n in range(1, 61):
            assert wilson(0, n)[0] == 0.0

    def test_k_bang_n_cho_can_tren_dung_bang_1(self):
        for n in range(1, 61):
            assert wilson(n, n)[1] == 1.0

    def test_n_cang_lon_khoang_cang_hep(self):
        rong = [wilson(0, n)[1] - wilson(0, n)[0] for n in (10, 20, 30, 60)]
        assert rong == sorted(rong, reverse=True)

    def test_doi_xung_quanh_mot_nua(self):
        for n in (7, 21, 30, 51):
            for k in range(n + 1):
                lo_a, hi_a = wilson(k, n)
                lo_b, hi_b = wilson(n - k, n)
                assert lo_a == pytest.approx(1 - hi_b, abs=1e-12)
                assert hi_a == pytest.approx(1 - lo_b, abs=1e-12)

    def test_n_bang_0_khong_no(self):
        assert wilson(0, 0) == (0.0, 1.0)


# ------------------------------------------------------- rule_of_three
class TestRuleOfThree:
    def test_gia_tri(self):
        assert rule_of_three(30) == pytest.approx(0.10)
        assert rule_of_three(0) == 1.0

    def test_wilson_bao_thu_hon_tu_n_14(self):
        """⚠️ Lý do (3) của B1 CÓ ĐIỀU KIỆN — test này là chỗ ghi điều kiện đó.

        Bản nháp đầu của B1 phát biểu trống *"ở vùng k = 0 Wilson bảo thủ hơn
        quy tắc số ba"*. **Sai.** Với `k = 0`, cận trên Wilson rút gọn thành
        `Z²/(n+Z²)` còn quy tắc số ba là `3/n`, nên Wilson rộng hơn **chỉ khi**

            n > 3Z²/(Z²−3) ≈ 13,69   →   n ≥ 14

        Ở `n = 12` (cỡ riêng nhóm B) thì ngược lại. Kết luận của B1 vẫn đứng vì
        mọi mẫu số repo thực sự trích đều `n ≥ 19` — nhưng nó đứng vì **dải n cụ
        thể**, không vì một tính chất phổ quát. Đừng nới phát biểu ra.
        """
        nguong = 3 * Z * Z / (Z * Z - 3)
        assert 13 < nguong < 14

        for n in (19, 21, 22, 27, 30, 51):  # mọi mẫu số báo cáo thật sự dùng
            assert wilson(0, n)[1] > rule_of_three(n), f"n={n}"

        for n in (5, 10, 12, 13):  # dưới ngưỡng thì ĐẢO CHIỀU
            assert wilson(0, n)[1] < rule_of_three(n), f"n={n}"

    def test_diem_dao_chieu_dung_o_14(self):
        assert wilson(0, 13)[1] < rule_of_three(13)
        assert wilson(0, 14)[1] > rule_of_three(14)

    def test_chi_dinh_nghia_duoc_khi_k_bang_0(self):
        """Lý do (1) của B1: hàm này không nhận `k`, nên `6/30` nó chịu."""
        import inspect

        assert list(inspect.signature(rule_of_three).parameters) == ["n"]


# -------------------------------------------------------------- fmt_pct
class TestFmtPct:
    def test_goi_ten_wilson(self):
        """⚠️ B1: tên phương pháp PHẢI có trong chuỗi. Đừng rút gọn đi."""
        assert "Wilson" in fmt_pct(0, 30)
        assert "Wilson" in fmt_pct(6, 30)
        assert "Wilson" in fmt_pct(17, 21)

    def test_cac_con_so_dem_di_bao_cao(self):
        assert fmt_pct(0, 30) == "0/30 = **0%** (CI 95% Wilson 0–11%)"
        assert fmt_pct(6, 30) == "6/30 = **20%** (CI 95% Wilson 10–37%)"
        assert fmt_pct(17, 21) == "17/21 = **81%** (CI 95% Wilson 60–92%)"

    def test_coverage_noi_dung_16_tren_21(self):
        """B4 — mẫu số thứ hai của coverage. Khoá luôn để báo cáo trích đúng."""
        assert fmt_pct(16, 21) == "16/21 = **76%** (CI 95% Wilson 55–89%)"

    def test_n_bang_0_khong_no(self):
        assert fmt_pct(0, 0) == "0/0 = **—**"

    def test_khop_voi_wilson(self):
        for n in (12, 21, 30, 51):
            for k in range(n + 1):
                lo, hi = wilson(k, n)
                s = fmt_pct(k, n)
                assert f"{100 * lo:.0f}–{100 * hi:.0f}%" in s


# ------------------------------------------------------------ sign_test
class TestSignTest:
    def test_con_so_dec_055(self):
        """18 tụt · 3 tăng · p = 0,0015 — kết quả thực nghiệm mạnh nhất của đề tài."""
        neg, pos, p = sign_test([-1.0] * 18 + [1.0] * 3)
        assert (neg, pos) == (18, 3)
        assert round(p, 4) == 0.0015

    def test_cap_bang_0_bi_loai_khoi_mau_so(self):
        neg, pos, _ = sign_test([-1.0, 0.0, 0.0, 1.0, -1.0])
        assert (neg, pos) == (2, 1)          # 5 phần tử, mẫu số chỉ còn 3

    def test_rong_va_toan_0(self):
        assert sign_test([]) == (0, 0, 1.0)
        assert sign_test([0.0, 0.0, 0.0]) == (0, 0, 1.0)

    def test_mot_phia_tuyet_doi(self):
        neg, pos, p = sign_test([-1.0] * 5)
        assert (neg, pos) == (5, 0)
        assert p == pytest.approx(2 * (1 / 32))

    def test_p_luon_trong_0_1(self):
        import random

        rng = random.Random(0)
        for _ in range(200):
            n = rng.randint(0, 40)
            diffs = [rng.choice([-1.0, 0.0, 1.0]) * rng.random() for _ in range(n)]
            _, _, p = sign_test(diffs)
            assert 0.0 <= p <= 1.0

    def test_can_bang_thi_khong_bac_bo(self):
        _, _, p = sign_test([-1.0] * 10 + [1.0] * 10)
        assert p == 1.0


# ----------------------------------------------------- chống trôi (B1)
def test_khong_co_ban_sao_thu_tu():
    """⛔ Cảnh báo lần thứ tư: đừng chép lại hàm nào của `stats.py`.

    DEC-044 (regex policy) · DEC-045 (regex byline) · DEC-046 (client LLM) ·
    Session 13 (`stats.py`) — bốn lần repo phải đi gỡ bản sao. Test này khoá
    lại: ba script dùng thống kê phải import từ module, không tự định nghĩa.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    ten_ham = {"wilson", "rule_of_three", "sign_test", "fmt_pct", "quantile"}
    for name in ("analyze_leakage.py", "calibrate_threshold.py",
                 "build_risk_coverage.py", "eval_register_shift.py",
                 "bench_latency.py", "build_perf_report.py"):
        path = root / "scripts" / name
        if not path.exists():
            continue
        cay = ast.parse(path.read_text(encoding="utf-8"))
        dinh_nghia = {
            n.name for n in ast.walk(cay)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        trung = dinh_nghia & ten_ham
        assert not trung, f"{name} định nghĩa lại {trung} — import từ src.eval.stats"


# --------------------------------------------------------------------------- #
# quantile — thêm ở Tuần 7 cho bảng latency p50/p95
# --------------------------------------------------------------------------- #


def test_quantile_moc_co_ban():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert quantile(xs, 0.0) == 1.0
    assert quantile(xs, 0.5) == 3.0
    assert quantile(xs, 1.0) == 5.0


def test_quantile_noi_suy_tuyen_tinh():
    """p75 cua [1,2,3,4] roi GIUA 3 va 4 -> 3.25, khong phai 3 hay 4."""
    assert quantile([1.0, 2.0, 3.0, 4.0], 0.75) == 3.25


def test_quantile_khong_phu_thuoc_thu_tu_dau_vao():
    assert quantile([5.0, 1.0, 3.0, 2.0, 4.0], 0.5) == 3.0


def test_quantile_mot_phan_tu():
    assert quantile([7.5], 0.95) == 7.5


def test_quantile_day_rong_thi_NEM():
    """Tra 0.0 cho day rong la cach mot bang latency lang le bao '0 giay'."""
    with pytest.raises(ValueError):
        quantile([], 0.5)


def test_quantile_p_ngoai_khoang_thi_NEM():
    with pytest.raises(ValueError):
        quantile([1.0, 2.0], 1.5)


def test_quantile_KHAC_stdlib_o_n_nho__ly_do_khong_muon_thu_vien():
    """Khoa bang MAY cai docstring noi bang loi.

    `statistics.quantiles()` mac dinh method='exclusive' cho ket qua KHAC noi
    suy tuyen tinh, va khac NHIEU o n nho. Mau ANSWER cua du an chi co 18 cau.
    Neu mot ban sua tuong lai thay hai cai nay tuong duong roi doi sang stdlib,
    test nay do — kem con so chung minh muc chenh.
    """
    import statistics

    xs = [float(i) for i in range(1, 19)]  # n = 18, dung co mau nhanh ANSWER
    cua_ta = quantile(xs, 0.95)
    cua_stdlib = statistics.quantiles(xs, n=100)[94]
    assert cua_ta != cua_stdlib
    assert cua_ta == pytest.approx(17.15)

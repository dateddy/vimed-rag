"""Test cho hai câu văn của `scripts/build_ragas_report.py` **phụ thuộc trạng thái**.

Sinh ra từ audit Tuần 6 (2026-09-14) — ISSUE-073 và ISSUE-074.

Cả hai lỗi cùng một hình dạng, và repo đã gặp nó hai lần trước đó (ISSUE-071):
**một câu văn hard-code sống sót qua chính sự kiện làm nó sai.** Chừng nào câu
văn còn được nối thẳng vào danh sách dòng thì không phép kiểm nào chạm tới
được nó; đưa quyết định ra thành hàm thuần là cách duy nhất khoá được bằng máy.

Không chạm mạng, không cần `runs.jsonl` (file đó bị gitignore) — chỉ nạp module
và gọi hai hàm thuần, theo đúng khuôn `test_provenance.py` đã dùng.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _nap(ten: str):
    spec = importlib.util.spec_from_file_location(ten, ROOT / "scripts" / f"{ten}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def brr():
    return _nap("build_ragas_report")


# --------------------------------------------------------------------------- #
# ISSUE-073 — cảnh báo "đừng so hai trung bình rời" phải theo trạng thái lô chấm
# --------------------------------------------------------------------------- #
def test_lo_con_do_thi_VAN_canh_bao(brr):
    """⚠️ Chiều quan trọng hơn: lô dở mà mất cảnh báo là hỏng nặng hơn lỗi gốc.

    Khi còn câu chưa chấm, hai trung bình rời thật sự đứng trên hai tập câu
    khác nhau — so chúng rồi gọi đó là hiệu ứng chính là cái bẫy câu cảnh báo
    sinh ra để chặn. Vá ISSUE-073 mà tắt luôn chiều này là chữa lợn lành.
    """
    txt = brr.canh_bao_hai_trung_binh(True)
    assert "ĐỪNG so hai trung bình rời" in txt
    assert "hai tập câu khác nhau" in txt


def test_lo_xong_thi_KHONG_con_canh_bao(brr):
    """⛔ ISSUE-073 — lô xong thì câu cảnh báo trở thành sai."""
    txt = brr.canh_bao_hai_trung_binh(False)
    assert "ĐỪNG so hai trung bình rời" not in txt
    assert "đã xong" in txt


def test_canh_bao_khong_neu_ten_su_co_da_qua(brr):
    """Không nhắc `403` nữa: nêu tên một sự cố cụ thể đã qua thì câu văn hết
    hạn cùng sự cố ấy, và lần sau lô dở vì lý do khác thì nó lại sai lần nữa."""
    assert "403" not in brr.canh_bao_hai_trung_binh(True)


# --------------------------------------------------------------------------- #
# ISSUE-074 — mục "Tái lập" phải in đúng cờ đã dùng
# --------------------------------------------------------------------------- #
def test_tai_lap_giu_co_pairable_only(brr):
    """⛔ Cờ này ĐỔI NỘI DUNG báo cáo (16 câu ghép cặp ↔ 51 câu) **và** tốn
    tiền thật khi chạy thiếu nó. Bỏ khỏi lệnh tái lập là chỉ sai đường."""
    lenh = brr.lenh_tai_lap(pairable_only=True,
                            model=brr.DEFAULT_JUDGE_MODEL, limit=0)
    assert "--pairable-only" in lenh


def test_tai_lap_khong_bia_co_khong_dung(brr):
    lenh = brr.lenh_tai_lap(pairable_only=False,
                            model=brr.DEFAULT_JUDGE_MODEL, limit=0)
    assert lenh == "python scripts/build_ragas_report.py"


def test_tai_lap_giu_model_khi_doi_judge(brr):
    """Khoá cache gồm tên model, nên judge khác = phép đo khác. Lệnh tái lập
    giấu chuyện đổi judge là dựng một phép đo không truy ngược được."""
    lenh = brr.lenh_tai_lap(pairable_only=True, model="anthropic/claude-x",
                            limit=0)
    assert "--model anthropic/claude-x" in lenh


def test_tai_lap_bo_qua_cache_only(brr):
    """`--cache-only` chặn gọi API chứ không đổi con số nào — nó KHÔNG thuộc
    lệnh tái lập. Chỉ cờ đổi nội dung mới được liệt kê."""
    assert "cache-only" not in brr.lenh_tai_lap(
        pairable_only=True, model=brr.DEFAULT_JUDGE_MODEL, limit=0)

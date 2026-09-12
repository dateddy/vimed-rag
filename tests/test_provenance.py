"""Khoá cơ chế PROVENANCE của nhãn tay (DEC-014) — sinh ra từ ISSUE-069/072.

## Vì sao file này tồn tại

Repo có **hai** bộ nhãn tay, và chúng dùng **hai tên trường khác nhau**:

===================================  =================  ==========================
file                                 trường             nuôi con số nào
===================================  =================  ==========================
``data/static_leak_review.jsonl``    ``labeled_by``     số CHÍNH ``6/30 = 20%``
``data/concept_variants.jsonl``      ``classified_by``  bảng ĐỘ NHẠY ``3/22``/``3/19``
===================================  =================  ==========================

Mọi công cụ provenance ban đầu **chỉ biết `labeled_by`**. Hệ quả đo được
(ISSUE-069): sau khi Đạt duyệt file thứ nhất, `docs/static-vs-corrective.md` in
một dòng *"Người gán nhãn: dat"* ở **đầu mục**, và bảng độ nhạy nằm dưới dòng
đó — trong khi nhãn nuôi nó vẫn là bản nháp của Claude. Người đọc lấy một dòng
"đã duyệt" và phủ lên cả số liệu chưa duyệt.

DEC-014 coi provenance là **một phần của kết quả**, nên đó là **mô tả sai kết
quả**, không phải chuyện trình bày.

Các test dưới đây khoá ba thứ: bảng ``NHAN`` phải phủ hết mọi file nhãn ·
``--approve`` phải idempotent (không dời ngày duyệt cũ) · báo cáo phải gắn
provenance với **từng con số**, không với cả mục.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _nap(ten: str):
    spec = importlib.util.spec_from_file_location(ten, ROOT / "scripts" / f"{ten}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rsl():
    return _nap("review_static_leaks")


@pytest.fixture(scope="module")
def bat():
    return _nap("build_arms_table")


# ------------------------------------------------------- bảng NHAN phủ đủ
class TestBangNhan:
    def test_phu_het_moi_file_nhan_tay(self, rsl):
        """⛔ Thêm file nhãn tay mới mà quên khai ở đây = tái diễn ISSUE-069.

        Tiêu chí "file nhãn tay": nằm ở `data/` (KHÔNG phải `data/processed/`,
        thư mục đó bị gitignore vì sinh lại được), là `.jsonl`, và mang một
        trường provenance. Nhãn tay là thứ đắt nhất trong repo và không tái tạo
        được — nên nó được commit, và nó phải có người đứng sau.
        """
        khai = {p.name for p, _, _ in rsl.NHAN.values()}
        prov_fields = {"labeled_by", "classified_by", "eyeballed_by", "reviewed_by"}

        thieu = []
        for path in sorted((ROOT / "data").glob("*.jsonl")):
            dong = path.read_text(encoding="utf-8").splitlines()
            if not dong:
                continue
            r = json.loads(dong[0])
            if (prov_fields & set(r)) and path.name not in khai:
                thieu.append(path.name)
        assert not thieu, (
            f"file nhãn có trường provenance nhưng KHÔNG khai trong NHAN: {thieu}. "
            "Chưa khai thì --approve không chạm tới và --tally không tố ra được."
        )

    def test_moi_muc_tro_toi_dung_truong(self, rsl):
        for khoa, (path, truong, mo_ta) in rsl.NHAN.items():
            assert path.exists(), f"{khoa}: {path} không tồn tại"
            r = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            assert truong in r, f"{khoa}: bản ghi không có trường `{truong}`"
            assert mo_ta, f"{khoa}: thiếu mô tả — người đọc cần biết nó nuôi số nào"


# ------------------------------------------------------------- la_nhap()
class TestLaNhap:
    @pytest.mark.parametrize("v", [
        "claude-draft-pass",
        "claude-draft-pass (CHƯA được Đạt duyệt)",
        "",
        None,
    ])
    def test_nhan_ra_ban_nhap(self, rsl, v):
        assert rsl.la_nhap(v)

    def test_thieu_truong_KHONG_phai_da_duyet(self, rsl):
        """Rỗng phải tính là nháp. Nếu không, thêm một file thiếu trường
        provenance sẽ âm thầm được coi như đã duyệt — im lặng và sai."""
        assert rsl.la_nhap(None)
        assert rsl.la_nhap("")

    @pytest.mark.parametrize("v", ["dat (duyệt 2026-09-12)", "dat", "Đạt (2026-09-13)"])
    def test_nhan_ra_da_duyet(self, rsl, v):
        assert not rsl.la_nhap(v)


# --------------------------------------------------- --approve idempotent
class TestApproveIdempotent:
    def test_chi_dong_dau_ban_ghi_con_nhap(self, rsl, tmp_path, monkeypatch):
        """⚠️ Bất biến quan trọng nhất của `--approve`.

        Đóng dấu đè lên bản ghi đã duyệt sẽ **dời ngày** — tức xoá mất *khi
        nào* lời chứng được đưa ra. Chạy lại lệnh phải an toàn.
        """
        f = tmp_path / "nhan.jsonl"
        rsl.ghi_jsonl(f, [
            {"id": "A-01", "labeled_by": "dat (duyệt 2020-01-01)"},
            {"id": "A-02", "labeled_by": "claude-draft-pass"},
            {"id": "A-03"},                       # thiếu trường = nháp
        ])
        monkeypatch.setitem(rsl.NHAN, "leaks", (f, "labeled_by", "test"))
        monkeypatch.setitem(rsl.NHAN, "variants", (tmp_path / "khong-co.jsonl",
                                                   "classified_by", "test"))

        rsl.approve("nguoi-duyet", "leaks")
        sau = {r["id"]: r["labeled_by"] for r in rsl.load_jsonl(f)}

        assert sau["A-01"] == "dat (duyệt 2020-01-01)"   # GIỮ NGUYÊN
        assert sau["A-02"].startswith("nguoi-duyet")
        assert sau["A-03"].startswith("nguoi-duyet")

    def test_chay_lai_khong_doi_gi(self, rsl, tmp_path, monkeypatch):
        f = tmp_path / "nhan.jsonl"
        rsl.ghi_jsonl(f, [{"id": "A-01", "labeled_by": "claude-draft-pass"}])
        monkeypatch.setitem(rsl.NHAN, "leaks", (f, "labeled_by", "test"))
        monkeypatch.setitem(rsl.NHAN, "variants", (tmp_path / "x.jsonl",
                                                   "classified_by", "test"))
        rsl.approve("a", "leaks")
        lan1 = f.read_text(encoding="utf-8")
        rsl.approve("b", "leaks")                 # người khác, chạy lại
        assert f.read_text(encoding="utf-8") == lan1, "chạy lại đã đổi nội dung"


# ------------------------------------------------------------- ghi_jsonl
class TestGhiJsonl:
    def test_moi_ban_ghi_dung_mot_dong(self, rsl, tmp_path):
        """DEC-058: bẻ dòng làm mọi chỗ đọc `json.loads(l)` từng dòng crash."""
        f = tmp_path / "x.jsonl"
        rows = [{"id": f"A-{i:02d}", "note": "dài " * 60} for i in range(1, 11)]
        rsl.ghi_jsonl(f, rows)
        dong = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(dong) == 10
        assert [json.loads(l)["id"] for l in dong] == [r["id"] for r in rows]

    def test_giu_nguyen_tieng_viet_khong_escape(self, rsl, tmp_path):
        f = tmp_path / "x.jsonl"
        rsl.ghi_jsonl(f, [{"id": "A-01", "note": "hẹp van hai lá"}])
        assert "hẹp van hai lá" in f.read_text(encoding="utf-8")


# ------------------------------- báo cáo gắn provenance với TỪNG con số
class TestBaoCao:
    def test_dong_provenance_tach_hai_nguon(self, bat):
        """⛔ Đây chính là ISSUE-069 — khoá lại để không tái diễn."""
        out = bat._dong_provenance(
            [{"id": "A-01", "labeled_by": "dat (duyệt 2026-09-12)"}],
            [{"id": "A-01", "classified_by": "claude-draft-pass"}],
        )
        assert "static_leak_review.jsonl" in out
        assert "concept_variants.jsonl" in out
        assert "dat (duyệt 2026-09-12)" in out
        assert "BẢN NHÁP" in out, "không tố ra được nhãn nháp của bảng độ nhạy"

    def test_ca_hai_duyet_thi_khong_con_canh_bao(self, bat):
        out = bat._dong_provenance(
            [{"id": "A-01", "labeled_by": "dat (duyệt 2026-09-12)"}],
            [{"id": "A-01", "classified_by": "dat (duyệt 2026-09-13)"}],
        )
        assert "BẢN NHÁP" not in out
        assert out.count("✅") == 2

    def test_khong_con_mot_dong_provenance_chung(self):
        """Bản cũ in một dòng `**Người gán nhãn:** …` phủ lên cả mục.

        Nó phải biến mất khỏi bộ sinh — giữ lại là mời ISSUE-069 quay về.
        """
        src = (ROOT / "scripts" / "build_arms_table.py").read_text(encoding="utf-8")
        assert '"**Người gán nhãn:** ' not in src

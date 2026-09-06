"""Test cho lớp rerank (Tuần 3 — T3.2, DEC-037).

Bất biến quan trọng nhất: **logit phải đi qua sigmoid**. Bỏ bước đó thì grader
lấy ngưỡng 0.6/0.3 chấm lên logit thô (đo thật: +4.125 cho cặp đúng, −8.179
cho cặp sai) và cho ra CORRECT hoặc INCORRECT tuyệt đối — pipeline hỏng hoàn
toàn mà **không test nào khác đỏ**, vì mọi test còn lại đều dùng score tự đặt.

Bất biến thứ hai: rerank **không được đánh rơi** 5 trường DEC-035
(``title``/``source``/``chunk_idx``/``n_chunks``/``specialties``). Đánh rơi thì
citation Tuần 4 chết, cũng không test nào khác đỏ.

Không test nào tải model, import torch/transformers hay chạm mạng (ràng buộc
#2). Làm được vì ``BgeReranker`` gom toàn bộ phần chạm model vào đúng một hàm
``_logits`` — test thay mỗi hàm đó là kiểm được cả đường còn lại. Nhờ vậy bộ
test vẫn chạy trên máy chưa cài gì nặng.
"""

import sys

import pytest

from src.config import ModelsConfig
from src.retrieval.reranker import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_LENGTH,
    BgeReranker,
    FakeReranker,
    Reranker,
    sigmoid,
)
from src.schemas import RetrievedChunk


def _chunk(doc_id: str, score: float = 0.0, text: str = "nội dung") -> RetrievedChunk:
    """Chunk đầy đủ 5 trường DEC-035 để kiểm chúng không bị rơi."""
    return RetrievedChunk(
        doc_id=doc_id,
        text=text,
        specialty="tim_mach",
        score=score,
        chunk_idx=3,
        n_chunks=9,
        title=f"Bài {doc_id}",
        source="vinmec",
        specialties=("tim_mach", "tieu_duong"),
    )


# --------------------------------------------------------------------------- #
# Protocol
# --------------------------------------------------------------------------- #
def test_ca_hai_impl_deu_khop_protocol():
    assert isinstance(FakeReranker(), Reranker)
    assert isinstance(BgeReranker(ModelsConfig("e", "r", "l")), Reranker)


# --------------------------------------------------------------------------- #
# FakeReranker — sắp xếp + cắt top_k
# --------------------------------------------------------------------------- #
def test_sap_xep_giam_dan_theo_score_moi():
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    out = FakeReranker(scores=[0.2, 0.9, 0.5]).rerank("q", chunks)

    assert [c.doc_id for c in out] == ["b", "c", "a"]
    assert [c.score for c in out] == [0.9, 0.5, 0.2]


def test_cat_dung_top_k():
    chunks = [_chunk(str(i)) for i in range(20)]
    out = FakeReranker().rerank("q", chunks, top_k=5)
    assert len(out) == 5


def test_khong_truyen_top_k_thi_giu_het():
    chunks = [_chunk(str(i)) for i in range(7)]
    assert len(FakeReranker().rerank("q", chunks)) == 7


def test_danh_sach_rong_tra_ve_rong():
    assert FakeReranker().rerank("q", []) == []


def test_scores_het_thi_lap_phan_tu_cuoi():
    """Cùng quy ước với FakeRetriever — 2 score cho 4 chunk vẫn chạy."""
    chunks = [_chunk(str(i)) for i in range(4)]
    out = FakeReranker(scores=[0.9, 0.1]).rerank("q", chunks)
    assert sorted(c.score for c in out) == [0.1, 0.1, 0.1, 0.9]


# --------------------------------------------------------------------------- #
# DEC-035 — rerank không được đánh rơi trường nào
# --------------------------------------------------------------------------- #
def test_rerank_giu_nguyen_5_truong_dec035():
    out = FakeReranker(scores=[0.7]).rerank("q", [_chunk("a")])[0]

    assert out.title == "Bài a"
    assert out.source == "vinmec"
    assert out.chunk_idx == 3
    assert out.n_chunks == 9
    assert out.specialties == ("tim_mach", "tieu_duong")
    assert out.specialty == "tim_mach"
    assert out.text == "nội dung"
    assert out.score == 0.7  # chỉ score được thay


def test_rerank_khong_sua_chunk_dau_vao():
    """Trả object mới, không mutate — tránh làm hỏng danh sách của caller."""
    goc = _chunk("a", score=0.016)
    FakeReranker(scores=[0.88]).rerank("q", [goc])
    assert goc.score == 0.016


# --------------------------------------------------------------------------- #
# ⛔ DEC-037 — sigmoid. Không cần torch, không cần model.
# --------------------------------------------------------------------------- #
def test_sigmoid_dua_logit_that_ve_khoang_0_1():
    """Hai logit ĐO THẬT trên bge-reranker-v2-m3 ngày 2026-09-06."""
    assert sigmoid(4.125) == pytest.approx(0.9841, abs=1e-4)  # cặp đúng
    assert sigmoid(-8.179) == pytest.approx(0.0003, abs=1e-4)  # cặp sai
    assert sigmoid(0.0) == 0.5


@pytest.mark.parametrize("x", [-800.0, -50.0, -1.0, 0.0, 1.0, 50.0, 800.0])
def test_sigmoid_khong_tran_va_luon_trong_khoang(x):
    """math.exp(-x) tràn khi x rất âm — nhánh âm phải dùng dạng e/(1+e)."""
    y = sigmoid(x)
    assert 0.0 <= y <= 1.0


def test_sigmoid_dong_bien():
    xs = [-9.0, -3.0, 0.0, 3.0, 9.0]
    ys = [sigmoid(x) for x in xs]
    assert ys == sorted(ys)


class _StubBge(BgeReranker):
    """Thay đúng hàm chạm model. Phần còn lại của BgeReranker chạy thật."""

    def __init__(self, logits: list[float], **kw):
        super().__init__(ModelsConfig("e", "BAAI/bge-reranker-v2-m3", "l"), **kw)
        self._fake_logits = logits
        self.seen_pairs: list[tuple[str, str]] = []

    def logits(self, pairs):
        self.seen_pairs = list(pairs)
        return self._fake_logits[: len(pairs)]


def test_score_tra_ve_la_sigmoid_cua_logit():
    """Nếu ai đó bỏ sigmoid, test này đỏ ngay — không chỗ nào khác bắt được."""
    out = _StubBge([4.125, -8.179]).rerank("q", [_chunk("a"), _chunk("b")])

    assert out[0].doc_id == "a"
    assert out[0].score == pytest.approx(0.9841, abs=1e-4)
    assert out[1].score == pytest.approx(0.0003, abs=1e-4)
    assert all(0.0 < c.score < 1.0 for c in out)


def test_ghep_cap_dung_thu_tu_query_roi_chunk():
    r = _StubBge([1.0])
    r.rerank("triệu chứng?", [_chunk("a", text="nội dung a")])
    assert r.seen_pairs == [("triệu chứng?", "nội dung a")]


def test_bge_sap_xep_va_cat_dung():
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    out = _StubBge([0.1, 2.0, 1.0]).rerank("q", chunks, top_k=2)
    assert [c.doc_id for c in out] == ["b", "c"]


def test_bge_giu_nguyen_metadata_dec035():
    out = _StubBge([2.0]).rerank("q", [_chunk("a")])[0]
    assert out.title == "Bài a"
    assert out.specialties == ("tim_mach", "tieu_duong")


def test_tham_so_mac_dinh():
    r = BgeReranker(ModelsConfig("e", "r", "l"))
    assert r._max_length == DEFAULT_MAX_LENGTH == 1024
    assert r._batch_size == DEFAULT_BATCH_SIZE
    assert r._use_fp16 is False  # mặc định CPU


def test_rong_thi_khong_cham_model():
    r = _StubBge([])
    assert r.rerank("q", []) == []
    assert r.seen_pairs == []


# --------------------------------------------------------------------------- #
# Ràng buộc #2 — nạp lười
# --------------------------------------------------------------------------- #
def test_dung_object_khong_nap_model():
    r = BgeReranker(ModelsConfig("e", "r", "l"))
    assert r._model is None
    assert r._tokenizer is None


def test_import_module_khong_keo_torch():
    import src.retrieval.reranker  # noqa: F401

    assert "torch" not in sys.modules, "import reranker.py không được kéo torch"
    assert "transformers" not in sys.modules, "cũng không được kéo transformers"

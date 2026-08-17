"""Test cho lớp index (Tuần 2, DEC-021).

Bất biến quan trọng nhất ở đây là **DEC-017**: chunk phải mang theo TẤT CẢ
khoa của bài. Vi phạm nó không làm test nào khác đỏ và không làm số point sai
— chỉ làm filter khoa ở Tuần 3 thiếu bài. Nên phải có test riêng.

Không test nào được tải model hay mở kết nối mạng (ràng buộc #2).
"""

import pytest

from src.config import IndexConfig, ModelsConfig, QdrantConfig
from src.data.chunker import chunk_records
from src.data.loader import RawDocument
from src.retrieval.embedder import BgeM3Embedder, FakeEmbedder
from src.retrieval.indexer import (
    FakeIndexer,
    QdrantIndexer,
    chunk_payload,
    collection_name,
    point_id,
)


@pytest.fixture
def index_cfg() -> IndexConfig:
    return IndexConfig(
        sizes=[256, 512],
        dense_dim=8,
        distance="Cosine",
        embed_batch=4,
        upsert_batch=2,
        max_length=128,
        use_fp16=False,
    )


def _doc(doc_id: str, text: str, specialties: tuple[str, ...]) -> RawDocument:
    return RawDocument(
        doc_id=doc_id,
        text=text,
        specialty=specialties[0] if specialties else None,
        source="test",
        title=f"tiêu đề {doc_id}",
        specialties=specialties,
    )


# --------------------------------------------------------------------------- #
# DEC-017 — bài trùng khoa
# --------------------------------------------------------------------------- #
def test_chunk_records_giu_ca_hai_khoa():
    """Bài thuộc 2 khoa thì MỌI chunk của nó phải giữ cả 2."""
    doc = _doc("d1", " ".join(str(i) for i in range(10)), ("tim_mach", "tieu_duong"))
    records = chunk_records([doc], size=4, overlap=1)

    assert len(records) > 1, "cần nhiều chunk mới kiểm được"
    for rec in records:
        assert rec.specialties == ("tim_mach", "tieu_duong")


def test_payload_specialties_la_list_khong_phai_chuoi():
    """Qdrant match theo phần tử -> phải là list, không phải chuỗi nối."""
    doc = _doc("d1", "a b c", ("tim_mach", "tieu_duong"))
    payload = chunk_payload(chunk_records([doc], size=4, overlap=1)[0])

    assert payload["specialties"] == ["tim_mach", "tieu_duong"]
    assert payload["specialty"] == "tim_mach"  # chỉ để hiển thị


def test_chunk_idx_dem_lai_tu_0_moi_bai():
    docs = [
        _doc("d1", " ".join(str(i) for i in range(10)), ("tim_mach",)),
        _doc("d2", " ".join(str(i) for i in range(10)), ("tieu_duong",)),
    ]
    records = chunk_records(docs, size=4, overlap=1)

    d1 = [r.chunk_idx for r in records if r.doc_id == "d1"]
    d2 = [r.chunk_idx for r in records if r.doc_id == "d2"]
    assert d1 == list(range(len(d1)))
    assert d2 == list(range(len(d2)))
    assert all(r.n_chunks == len(d1) for r in records if r.doc_id == "d1")


# --------------------------------------------------------------------------- #
# Point ID tất định — chạy lại phải ĐÈ, không nhân đôi
# --------------------------------------------------------------------------- #
def test_point_id_tat_dinh():
    assert point_id("abc", 3) == point_id("abc", 3)


def test_point_id_khac_nhau_theo_chunk_va_doc():
    assert point_id("abc", 0) != point_id("abc", 1)
    assert point_id("abc", 0) != point_id("abd", 0)


def test_index_lai_cung_chunk_khong_sinh_id_moi():
    doc = _doc("d1", " ".join(str(i) for i in range(10)), ("tim_mach",))
    records = chunk_records([doc], size=4, overlap=1)

    first = FakeIndexer()
    first.index(records)
    second = FakeIndexer()
    second.index(chunk_records([doc], size=4, overlap=1))

    assert [p["id"] for p in first.points] == [p["id"] for p in second.points]
    assert len({p["id"] for p in first.points}) == len(records)


def test_collection_name():
    assert collection_name("vimed_rag", 512) == "vimed_rag_512"
    assert collection_name("vimed_rag", 256) == "vimed_rag_256"


# --------------------------------------------------------------------------- #
# Ràng buộc #2 — dựng object KHÔNG được tải model / mở kết nối
# --------------------------------------------------------------------------- #
def test_bge_embedder_khong_tai_model_khi_khoi_tao(index_cfg):
    cfg = ModelsConfig(embedder="BAAI/bge-m3", reranker="x", llm="y")
    emb = BgeM3Embedder(cfg, index_cfg)

    assert emb._model is None
    assert emb.dim == index_cfg.dense_dim


def test_qdrant_indexer_khong_mo_ket_noi_khi_khoi_tao(index_cfg):
    qcfg = QdrantConfig(url="http://khong-ton-tai:6333", collection="vimed_rag")
    indexer = QdrantIndexer(qcfg, FakeEmbedder(dim=8), index_cfg, "vimed_rag_512")

    assert indexer._client is None
    assert indexer.collection == "vimed_rag_512"


# --------------------------------------------------------------------------- #
# FakeEmbedder hybrid — đủ tính chất để test đường ống
# --------------------------------------------------------------------------- #
def test_fake_embed_hybrid_tat_dinh():
    emb = FakeEmbedder(dim=8)
    a = emb.embed_hybrid(["tim mạch", "tiểu đường"])
    b = emb.embed_hybrid(["tim mạch", "tiểu đường"])

    assert a.dense == b.dense
    assert a.sparse == b.sparse
    assert len(a) == 2


def test_fake_embed_hybrid_chung_tu_thi_chung_token_id():
    emb = FakeEmbedder(dim=8)
    batch = emb.embed_hybrid(["huyết áp cao", "huyết áp thấp"])
    chung = set(batch.sparse[0]) & set(batch.sparse[1])

    assert len(chung) == 2  # "huyết" và "áp"


def test_fake_indexer_supports_sparse_duoc_nhan_dien(index_cfg):
    qcfg = QdrantConfig(url="http://x:6333", collection="c")
    assert QdrantIndexer(qcfg, FakeEmbedder(dim=8), index_cfg, "c").supports_sparse

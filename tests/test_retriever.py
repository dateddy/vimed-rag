"""Test cho HybridRetriever (Tuần 3 — T3.1, DEC-034/035/036).

Ba bất biến ở đây đều thuộc loại **hỏng im lặng** — vi phạm chúng không làm
test nào khác đỏ, kết quả vẫn trả về đủ số chunk, chỉ là chunk sai:

1. **DEC-021d** — vector phải gọi đúng TÊN ``dense``/``sparse``.
2. **DEC-017** — lọc khoa phải khớp ``specialties`` (list), KHÔNG ``specialty``
   số ít; và chunk trả về phải giữ TẤT CẢ khoa của bài.
3. **DEC-034** — hybrid phải hợp nhất bằng RRF server-side, không phải tự trộn.

Không test nào mở kết nối hay tải model (ràng buộc #2): client Qdrant được
tiêm vào bằng spy, embedder là ``FakeEmbedder``.
"""

import pytest
from qdrant_client import models

from src.config import (
    AppConfig,
    ChunkingConfig,
    CorrectiveConfig,
    DataConfig,
    GenerationConfig,
    GraderConfig,
    IndexConfig,
    ModelsConfig,
    QdrantConfig,
    RetrievalConfig,
)
from src.retrieval.embedder import FakeEmbedder
from src.retrieval.indexer import DENSE_VECTOR, SPARSE_VECTOR
from src.retrieval.reranker import FakeReranker
from src.retrieval.retriever import HybridRetriever


# --------------------------------------------------------------------------- #
# Đồ giả
# --------------------------------------------------------------------------- #
def _cfg() -> AppConfig:
    return AppConfig(
        models=ModelsConfig("e", "r", "l"),
        # Retriever không đụng khối `data`; điền giả cho đủ contract.
        data=DataConfig("d", "s", "title", "content", 100, "data/processed", 25),
        retrieval=RetrievalConfig(True, 20, 5),
        chunking=ChunkingConfig(512, 50),
        grader=GraderConfig(correct_threshold=0.6, incorrect_threshold=0.3),
        corrective=CorrectiveConfig(max_iter=1),
        generation=GenerationConfig(0.2),
        qdrant=QdrantConfig("http://x", "vimed_rag"),
        index=IndexConfig([256, 512], 8, "Cosine", 16, 128, 128, False),
        specialties={},
    )


class _Point:
    """Điểm Qdrant giả — chỉ cần ``score`` + ``payload``."""

    def __init__(self, score: float, payload: dict) -> None:
        self.score = score
        self.payload = payload


class _Result:
    def __init__(self, points: list[_Point]) -> None:
        self.points = points


class _SpyClient:
    """Client Qdrant giả: ghi lại kwargs của ``query_points``, không chạm mạng."""

    def __init__(self, points: list[_Point] | None = None) -> None:
        self.calls: list[dict] = []
        self._points = points or []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return _Result(self._points)


class _SpyEmbedder(FakeEmbedder):
    """FakeEmbedder có ghi lại đã gọi nhánh nào."""

    def __init__(self, dim: int = 8) -> None:
        super().__init__(dim)
        self.calls: list[str] = []

    def embed(self, texts):
        self.calls.append("embed")
        return super().embed(texts)

    def embed_hybrid(self, texts):
        self.calls.append("embed_hybrid")
        return super().embed_hybrid(texts)


class _DenseOnlyEmbedder:
    """Embedder chỉ có dense — dùng để kiểm nhánh báo lỗi sớm."""

    dim = 8

    def embed(self, texts):
        return [[0.0] * self.dim for _ in texts]


def _payload(**over) -> dict:
    base = {
        "doc_id": "doc-1",
        "chunk_idx": 2,
        "n_chunks": 7,
        "text": "Tăng huyết áp là bệnh mạn tính.",
        "title": "Tăng huyết áp",
        "source": "vinmec",
        "specialties": ["tim_mach"],
        "specialty": "tim_mach",
    }
    base.update(over)
    return base


def _retriever(mode="hybrid", points=None, **kw) -> tuple[HybridRetriever, _SpyClient]:
    client = _SpyClient(points)
    r = HybridRetriever(_cfg(), _SpyEmbedder(), mode=mode, client=client, **kw)
    return r, client


# --------------------------------------------------------------------------- #
# Khởi tạo — không chạm mạng, không nạp model (ràng buộc #2)
# --------------------------------------------------------------------------- #
def test_dung_object_khong_mo_ket_noi():
    r = HybridRetriever(_cfg(), FakeEmbedder())
    assert r._client is None, "__init__ không được dựng client Qdrant"


def test_collection_mac_dinh_theo_chunk_size():
    r = HybridRetriever(_cfg(), FakeEmbedder())
    assert r.collection == "vimed_rag_512"


def test_collection_truyen_tay_de_do_ablation():
    """Cùng một class phải đo được cả 256 lẫn 512 (DEC-004)."""
    r = HybridRetriever(_cfg(), FakeEmbedder(), collection="vimed_rag_256")
    assert r.collection == "vimed_rag_256"


def test_mode_khong_hop_le_bao_loi_ngay():
    with pytest.raises(ValueError, match="mode không hợp lệ"):
        HybridRetriever(_cfg(), FakeEmbedder(), mode="bm25")


@pytest.mark.parametrize("mode", ["hybrid", "sparse"])
def test_mode_can_sparse_ma_embedder_khong_co_thi_bao_loi(mode):
    """Thiếu embed_hybrid phải nổ lúc dựng, không phải lúc query."""
    with pytest.raises(TypeError, match="embed_hybrid"):
        HybridRetriever(_cfg(), _DenseOnlyEmbedder(), mode=mode)


# --------------------------------------------------------------------------- #
# DEC-034 — hybrid = RRF server-side, đúng tên vector (DEC-021d)
# --------------------------------------------------------------------------- #
def test_hybrid_dung_rrf_va_dung_ten_vector():
    r, client = _retriever("hybrid")
    r.search("tăng huyết áp là gì")

    kw = client.calls[0]
    assert kw["collection_name"] == "vimed_rag_512"
    assert isinstance(kw["query"], models.FusionQuery)
    assert kw["query"].fusion == models.Fusion.RRF

    using = [p.using for p in kw["prefetch"]]
    assert using == [DENSE_VECTOR, SPARSE_VECTOR] == ["dense", "sparse"]


def test_hybrid_hai_nhanh_prefetch_cung_lay_top_k_dense():
    r, client = _retriever("hybrid")
    r.search("tăng huyết áp là gì")

    kw = client.calls[0]
    assert kw["limit"] == 20  # retrieval.top_k_dense
    assert [p.limit for p in kw["prefetch"]] == [20, 20]


def test_hybrid_gui_sparse_vector_dung_kieu():
    r, client = _retriever("hybrid")
    r.search("tăng huyết áp là gì")

    sparse_branch = client.calls[0]["prefetch"][1]
    assert isinstance(sparse_branch.query, models.SparseVector)
    assert len(sparse_branch.query.indices) == len(sparse_branch.query.values)
    assert sparse_branch.query.indices, "sparse rỗng thì nhánh từ vựng vô dụng"


# --------------------------------------------------------------------------- #
# Mode đơn — dense / sparse
# --------------------------------------------------------------------------- #
def test_dense_mode_khong_tinh_sparse():
    """Mode dense phải đi nhánh embed() — nếu không thì T3.4 đo sai chi phí."""
    client = _SpyClient()
    emb = _SpyEmbedder()
    HybridRetriever(_cfg(), emb, mode="dense", client=client).search("x")

    assert emb.calls == ["embed"]
    kw = client.calls[0]
    assert kw["using"] == DENSE_VECTOR
    assert "prefetch" not in kw, "mode đơn không được đi đường fusion"


def test_sparse_mode_gui_dung_vector_sparse():
    r, client = _retriever("sparse")
    r.search("x")

    kw = client.calls[0]
    assert kw["using"] == SPARSE_VECTOR
    assert isinstance(kw["query"], models.SparseVector)


# --------------------------------------------------------------------------- #
# DEC-036 — lọc khoa mặc định TẮT; DEC-017 — lọc đúng trường
# --------------------------------------------------------------------------- #
def test_loc_khoa_mac_dinh_tat_o_ca_hai_duong():
    r_hybrid, c_hybrid = _retriever("hybrid")
    r_hybrid.search("x")
    assert all(p.filter is None for p in c_hybrid.calls[0]["prefetch"])

    r_dense, c_dense = _retriever("dense")
    r_dense.search("x")
    assert c_dense.calls[0]["query_filter"] is None


def test_loc_khoa_khop_truong_specialties_khong_phai_specialty():
    """DEC-017: lọc nhầm ``specialty`` số ít làm rơi bài thuộc cả hai khoa."""
    r, client = _retriever("dense", specialty="tim_mach")
    r.search("x")

    flt = client.calls[0]["query_filter"]
    assert isinstance(flt, models.Filter)
    keys = [c.key for c in flt.must]
    assert keys == ["specialties"]
    assert flt.must[0].match.value == "tim_mach"


def test_loc_khoa_ap_cho_ca_hai_nhanh_prefetch():
    r, client = _retriever("hybrid", specialty="tieu_duong")
    r.search("x")

    for branch in client.calls[0]["prefetch"]:
        assert branch.filter is not None
        assert branch.filter.must[0].key == "specialties"


# --------------------------------------------------------------------------- #
# DEC-035 — map payload → RetrievedChunk đủ trường mới
# --------------------------------------------------------------------------- #
def test_map_payload_du_5_truong_moi():
    r, _ = _retriever("hybrid", points=[_Point(0.0164, _payload())])
    chunk = r.search("x")[0]

    assert chunk.doc_id == "doc-1"
    assert chunk.chunk_idx == 2
    assert chunk.n_chunks == 7
    assert chunk.title == "Tăng huyết áp"
    assert chunk.source == "vinmec"
    assert chunk.specialties == ("tim_mach",)
    assert chunk.score == pytest.approx(0.0164)


def test_chunk_hai_khoa_giu_ca_hai_sau_truy_hoi():
    """DEC-017 ở phía retrieve — trước DEC-035 chỗ này rơi mất một khoa."""
    payload = _payload(specialties=["tim_mach", "tieu_duong"], specialty="tim_mach")
    r, _ = _retriever("hybrid", points=[_Point(0.5, payload)])
    chunk = r.search("x")[0]

    assert chunk.specialties == ("tim_mach", "tieu_duong")
    assert chunk.specialty == "tim_mach"  # số ít chỉ để hiển thị


def test_payload_thieu_truong_thi_dung_default_khong_no():
    payload = {"doc_id": "d", "text": "t", "specialties": ["tieu_duong"]}
    r, _ = _retriever("hybrid", points=[_Point(0.1, payload)])
    chunk = r.search("x")[0]

    assert chunk.chunk_idx is None
    assert chunk.title is None
    # Không có `specialty` số ít trong payload -> lấy phần tử đầu của list.
    assert chunk.specialty == "tieu_duong"


# --------------------------------------------------------------------------- #
# Giao diện Retriever
# --------------------------------------------------------------------------- #
def test_retrieve_lay_top_k_dense_ung_vien():
    points = [_Point(0.9 - i / 100, _payload(doc_id=f"d{i}")) for i in range(5)]
    r, client = _retriever("hybrid", points=points)

    chunks = r.retrieve("tăng huyết áp là gì")

    assert [c.doc_id for c in chunks] == ["d0", "d1", "d2", "d3", "d4"]
    assert client.calls[0]["limit"] == 20  # top_k_dense, chưa cắt xuống top_k_rerank


def test_hoa_diem_thi_thu_tu_tat_dinh():
    """DEC-040: RRF k=2 hoà điểm liên tục, Qdrant trả thứ tự không tất định."""
    tied = [
        _Point(0.8333, _payload(doc_id="f425f826", chunk_idx=0)),
        _Point(0.8333, _payload(doc_id="7668be27", chunk_idx=0)),
        _Point(0.4167, _payload(doc_id="cc4dd1c7", chunk_idx=0)),
    ]
    r1, _ = _retriever("hybrid", points=list(tied))
    r2, _ = _retriever("hybrid", points=[tied[1], tied[0], tied[2]])  # đảo thứ tự

    assert [c.doc_id for c in r1.search("x")] == [c.doc_id for c in r2.search("x")]
    # Hoà điểm -> khoá phụ doc_id tăng dần; điểm cao hơn vẫn luôn đứng trước.
    assert [c.doc_id for c in r1.search("x")] == ["7668be27", "f425f826", "cc4dd1c7"]


def test_khong_hoa_diem_thi_giu_dung_thu_hang_theo_score():
    points = [
        _Point(0.71, _payload(doc_id="b")),
        _Point(0.99, _payload(doc_id="z")),
        _Point(0.85, _payload(doc_id="a")),
    ]
    r, _ = _retriever("dense", points=points)
    assert [c.doc_id for c in r.search("x")] == ["z", "a", "b"]


def test_search_ton_trong_limit_truyen_tay():
    r, client = _retriever("hybrid")
    r.search("x", limit=3)
    assert client.calls[0]["limit"] == 3


# --------------------------------------------------------------------------- #
# T3.2 — nối reranker (DEC-033)
# --------------------------------------------------------------------------- #
def test_co_reranker_thi_top20_thanh_top_k_rerank():
    """Đường chạy thật: lấy 20 ứng viên, chấm lại, còn 5."""
    # Điểm PHÂN BIỆT (giảm dần) để phép thử này không lẫn với tie-break DEC-040.
    points = [_Point(0.9 - i * 0.01, _payload(doc_id=f"d{i:02d}")) for i in range(20)]
    client = _SpyClient(points)
    rr = FakeReranker(scores=[0.1 * i for i in range(20)])
    r = HybridRetriever(_cfg(), _SpyEmbedder(), client=client, reranker=rr)

    out = r.retrieve("tăng huyết áp là gì")

    assert client.calls[0]["limit"] == 20  # vẫn lấy top_k_dense ứng viên
    assert len(out) == 5  # rồi cắt còn top_k_rerank
    assert rr.calls == [("tăng huyết áp là gì", 20)]
    # FakeReranker chấm theo VỊ TRÍ, chunk cuối được 1.9 -> lên đầu sau rerank.
    assert out[0].doc_id == "d19"


def test_score_sau_rerank_thay_the_score_fusion():
    """RRF ~0.02 phải bị thay bằng score rerank — nếu không grader chấm nhầm."""
    client = _SpyClient([_Point(0.0164, _payload())])
    r = HybridRetriever(
        _cfg(), _SpyEmbedder(), client=client, reranker=FakeReranker(scores=[0.83])
    )
    assert r.retrieve("x")[0].score == pytest.approx(0.83)


def test_rerank_giu_nguyen_metadata_dec035():
    client = _SpyClient([_Point(0.02, _payload())])
    r = HybridRetriever(
        _cfg(), _SpyEmbedder(), client=client, reranker=FakeReranker(scores=[0.9])
    )
    chunk = r.retrieve("x")[0]

    assert chunk.title == "Tăng huyết áp"
    assert chunk.source == "vinmec"
    assert chunk.chunk_idx == 2
    assert chunk.specialties == ("tim_mach",)


def test_co_reranker_moi_bat_co_scores_are_rerank():
    """Cờ để T3.4 dán nhãn đúng và để chỗ nối pipeline assert trước khi chạy."""
    khong_rerank, _ = _retriever("hybrid")
    assert khong_rerank.scores_are_rerank is False

    co_rerank = HybridRetriever(
        _cfg(), _SpyEmbedder(), client=_SpyClient(), reranker=FakeReranker()
    )
    assert co_rerank.scores_are_rerank is True


def test_khong_reranker_thi_tra_ung_vien_tho():
    """Cấu hình đối chứng của T3.4 phải còn dùng được."""
    points = [_Point(0.02, _payload(doc_id=f"d{i}")) for i in range(20)]
    r, _ = _retriever("hybrid", points=points)
    assert len(r.retrieve("x")) == 20

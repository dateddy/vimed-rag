"""Interface truy hồi + FakeRetriever + HybridRetriever (Tuần 3).

``HybridRetriever`` mở khoá ở Tuần 3 nhưng **không** mở kết nối lúc
``__init__``: client Qdrant dựng lười và ``qdrant_client`` chỉ import bên
trong hàm, y như ``indexer.py``. Import module này không chạm mạng, không nạp
model (ràng buộc #2).

Ba chế độ truy hồi (``mode``) để Tuần 3 lập được bảng so sánh:

===========  =====================================================
``dense``    chỉ vector dense của bge-m3 — ngữ nghĩa
``sparse``   chỉ vector sparse của bge-m3 — từ vựng
``hybrid``   cả hai, hợp nhất bằng RRF server-side (DEC-034)
===========  =====================================================

⚠️ ``sparse`` **KHÔNG phải BM25.** Nó là *learned sparse* của bge-m3 (trọng số
do model học, không phải TF-IDF). Bảng kết quả và báo cáo phải gọi đúng tên,
nếu không sẽ bị hỏi "BM25 index của bạn đâu" mà không có gì để chỉ.

Lọc theo khoa: viết sẵn và test sẵn, nhưng **mặc định TẮT** (DEC-036) — nhãn
khoa cho *câu hỏi* không đáng tin, bật lên là cắt mất bài đúng trước khi
retrieval kịp chạy.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.config import AppConfig
from src.retrieval.embedder import Embedder
from src.retrieval.indexer import DENSE_VECTOR, SPARSE_VECTOR, collection_name
from src.retrieval.reranker import Reranker
from src.schemas import RetrievedChunk

# Các chế độ hợp lệ của HybridRetriever. Tuần 3 đo cả ba.
RETRIEVAL_MODES = ("hybrid", "dense", "sparse")

# Chế độ cần vector sparse -> embedder bắt buộc có embed_hybrid().
_SPARSE_MODES = ("hybrid", "sparse")


@runtime_checkable
class Retriever(Protocol):
    """Giao diện truy hồi: query → danh sách chunk kèm rerank score."""

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        ...


class FakeRetriever:
    """Retriever giả với rerank score điều khiển được.

    Mỗi lần ``retrieve`` trả một context gồm ``n_chunks`` chunk có cùng score
    lấy tuần tự từ ``scores``. Khi hết ``scores`` thì lặp lại phần tử cuối
    (hữu ích để mô phỏng nhánh vẫn INCORRECT sau khi rewrite).

    Ví dụ:
        FakeRetriever([0.1, 0.9]) -> lần 1 score 0.1, lần 2 trở đi score 0.9.
    """

    def __init__(
        self,
        scores: list[float] | None = None,
        n_chunks: int = 3,
        specialty: str | None = None,
    ) -> None:
        self._scores = list(scores) if scores else [0.9]
        self._n_chunks = n_chunks
        self._specialty = specialty
        self._calls = 0
        self.queries: list[str] = []  # log để test kiểm tra query đã dùng

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        self.queries.append(query)
        idx = min(self._calls, len(self._scores) - 1)
        score = self._scores[idx]
        self._calls += 1
        return [
            RetrievedChunk(
                doc_id=f"fake-{idx}-{i}",
                text=f"Đoạn tài liệu mẫu {i} cho: {query}",
                specialty=self._specialty,
                score=score,
            )
            for i in range(self._n_chunks)
        ]


class HybridRetriever:
    """Truy hồi thật trên Qdrant: dense + sparse hợp nhất bằng RRF (DEC-034).

    Vòng đời: dựng object (không chạm mạng) → ``search()``/``retrieve()`` mở
    kết nối ở lần gọi đầu.

    ⚠️ **KHÔNG có ``reranker`` thì KHÔNG được nối vào ``RAGPipeline``.** Thiếu
    nó, ``score`` là điểm *fusion* hoặc similarity thô, **không cùng thang**
    với ``grader.correct_threshold = 0.6`` / ``incorrect_threshold = 0.3`` —
    đúng lớp lỗi im lặng DEC-033. Cấu hình không-rerank vẫn giữ vì T3.4 phải
    đo nó để so; ``scores_are_rerank`` cho biết đang ở nhánh nào.

    Ba thang điểm thô đo thật trên ``vimed_rag_512`` (smoke 2026-09-06, truy
    vấn "Triệu chứng tăng huyết áp?", top-5) — **cả ba đều nguy hiểm theo kiểu
    khác nhau**:

    ===========  ==============  ==========================================
    ``dense``    0.707 – 0.741   cosine. Toàn bộ **> 0.6** -> grader CORRECT
                                 tuyệt đối, nhánh ABSTAIN không bao giờ chạy.
    ``sparse``   0.180 – 0.194   Toàn bộ **< 0.3** -> INCORRECT tuyệt đối.
    ``hybrid``   0.250 – 0.583   RRF của Qdrant dùng **k=2** (``1/(2+rank)``,
                                 rank tính từ 0), KHÔNG phải k=60 quen thuộc.
                                 Điểm vì thế rơi **ngay giữa** hai ngưỡng.
    ===========  ==============  ==========================================

    Dòng ``hybrid`` mới là dòng đáng sợ nhất: nó **không** làm pipeline hỏng
    lộ liễu. Nó sinh ra một hỗn hợp CORRECT/AMBIGUOUS/INCORRECT trông hợp lý,
    biểu đồ risk–coverage vẫn vẽ ra được, chỉ là số đo một đại lượng vô
    nghĩa — thứ hạng RRF, không phải độ liên quan.

    Args:
        cfg: config toàn cục (dùng ``qdrant``, ``retrieval``, ``chunking``).
        embedder: encode truy vấn. Mode ``hybrid``/``sparse`` bắt buộc
            embedder có ``embed_hybrid()`` (``BgeM3Embedder``, ``FakeEmbedder``).
        collection: tên collection đầy đủ. Mặc định suy ra từ
            ``chunking.size`` → ``vimed_rag_512``. Truyền tay để đo ablation
            256 vs 512 bằng cùng một class.
        mode: một trong :data:`RETRIEVAL_MODES`.
        specialty: lọc theo khoa. **Mặc định None = không lọc** (DEC-036).
        reranker: lớp chấm lại top-20 → top-5 (T3.2). Bỏ trống = cấu hình
            "không rerank" mà T3.4 cần để so — nhưng **không nối pipeline
            được**, xem cảnh báo trên.
        client: tiêm client sẵn (dùng cho test). Bỏ trống thì dựng lười.
    """

    def __init__(
        self,
        cfg: AppConfig,
        embedder: Embedder,
        *,
        collection: str | None = None,
        mode: str = "hybrid",
        specialty: str | None = None,
        reranker: Reranker | None = None,
        client=None,
    ) -> None:
        if mode not in RETRIEVAL_MODES:
            raise ValueError(
                f"mode không hợp lệ: {mode!r}. Chọn một trong {RETRIEVAL_MODES}."
            )
        if mode in _SPARSE_MODES and not hasattr(embedder, "embed_hybrid"):
            raise TypeError(
                f"mode={mode!r} cần vector sparse nhưng {type(embedder).__name__} "
                "không có embed_hybrid(). Dùng mode='dense' hoặc đổi embedder."
            )
        self._cfg = cfg
        self._embedder = embedder
        self.collection = collection or collection_name(
            cfg.qdrant.collection, cfg.chunking.size
        )
        self.mode = mode
        self.specialty = specialty
        self._reranker = reranker
        self._client = client  # dựng lười — xem client()

    @property
    def scores_are_rerank(self) -> bool:
        """``score`` đã cùng thang với ngưỡng grader chưa?

        ``False`` = đang ở cấu hình không-rerank, score là RRF/cosine thô.
        T3.4 dùng cờ này để dán nhãn đúng cho từng dòng bảng kết quả, và bất
        cứ chỗ nào nối pipeline cũng nên assert nó ``True`` trước.
        """
        return self._reranker is not None

    # ----------------------------------------------------------------- #
    def client(self):
        """Mở kết nối Qdrant ở lần cần đầu tiên. Import trễ có chủ đích."""
        if self._client is None:
            from qdrant_client import QdrantClient  # import trễ

            self._client = QdrantClient(
                url=self._cfg.qdrant.url,
                api_key=self._cfg.qdrant.api_key or None,
                timeout=60,
            )
        return self._client

    # ----------------------------------------------------------------- #
    def _encode_query(self, query: str, models):
        """Encode truy vấn → (dense, sparse). ``sparse`` là None ở mode dense.

        Mode ``dense`` gọi ``embed()`` chứ không ``embed_hybrid()``: bỏ được
        nhánh sparse của forward pass, và quan trọng hơn là làm phép so 3 cấu
        hình ở T3.4 đo đúng chi phí của từng cấu hình.
        """
        if self.mode == "dense":
            return self._embedder.embed([query])[0], None

        batch = self._embedder.embed_hybrid([query])  # type: ignore[attr-defined]
        raw = batch.sparse[0]
        sparse = models.SparseVector(
            indices=list(raw.keys()), values=list(raw.values())
        )
        return batch.dense[0], sparse

    def _query_filter(self, models):
        """Filter theo khoa, hoặc None khi không lọc (mặc định — DEC-036).

        Khớp trên **``specialties``** (list, có payload index KEYWORD), KHÔNG
        trên ``specialty`` số ít: bài thuộc cả hai khoa phải khớp được cả hai
        filter. Đây đúng là chỗ DEC-017 cảnh báo — dùng nhầm trường thì số
        point trả về vẫn trông hợp lý, chỉ thiếu bài.
        """
        if not self.specialty:
            return None
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="specialties",
                    match=models.MatchValue(value=self.specialty),
                )
            ]
        )

    @staticmethod
    def _to_chunk(point) -> RetrievedChunk:
        """Điểm Qdrant → :class:`RetrievedChunk` (đủ 5 trường mới, DEC-035)."""
        payload = point.payload or {}
        specialties = tuple(payload.get("specialties") or ())
        return RetrievedChunk(
            doc_id=payload.get("doc_id", ""),
            text=payload.get("text", ""),
            specialty=payload.get("specialty")
            or (specialties[0] if specialties else None),
            score=float(point.score),
            chunk_idx=payload.get("chunk_idx"),
            n_chunks=payload.get("n_chunks"),
            title=payload.get("title"),
            source=payload.get("source"),
            specialties=specialties,
        )

    # ----------------------------------------------------------------- #
    def search(self, query: str, limit: int | None = None) -> list[RetrievedChunk]:
        """Lấy ứng viên thô theo ``mode``. Mặc định ``retrieval.top_k_dense``.

        Mode ``hybrid`` chạy RRF **server-side**: hai nhánh prefetch cùng
        ``limit``, Qdrant hợp nhất theo thứ hạng rồi trả về. Một round-trip,
        không kéo 2 danh sách kèm payload về client (DEC-034).
        """
        from qdrant_client import models  # import trễ

        limit = limit or self._cfg.retrieval.top_k_dense
        dense, sparse = self._encode_query(query, models)
        flt = self._query_filter(models)

        if self.mode == "hybrid":
            result = self.client().query_points(
                collection_name=self.collection,
                prefetch=[
                    models.Prefetch(
                        query=dense, using=DENSE_VECTOR, limit=limit, filter=flt
                    ),
                    models.Prefetch(
                        query=sparse, using=SPARSE_VECTOR, limit=limit, filter=flt
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
        else:
            result = self.client().query_points(
                collection_name=self.collection,
                query=dense if self.mode == "dense" else sparse,
                using=DENSE_VECTOR if self.mode == "dense" else SPARSE_VECTOR,
                query_filter=flt,
                limit=limit,
                with_payload=True,
            )

        chunks = [self._to_chunk(p) for p in result.points]
        # ⛔ Ổn định hoá thứ tự khi HOÀ ĐIỂM — DEC-040. RRF của Qdrant dùng k=2
        # nên điểm là tổng vài phân số nhỏ và **hoà rất thường xuyên**; thứ tự
        # Qdrant trả về giữa các bài hoà điểm KHÔNG tất định giữa các lượt chạy.
        # Đo được: E-08 có 2 bài cùng 0,8333, bài vàng lúc hạng 1 lúc hạng 2 →
        # mrr@5 nhảy 0,431 ↔ 0,472 trên 12 câu. Khoá phụ (doc_id, chunk_idx) là
        # tuỳ tiện, nhưng giữa các bài đã hoà điểm thì mọi quy tắc đều tuỳ tiện
        # như nhau — và tái lập được thì hơn hẳn không tái lập được.
        chunks.sort(
            key=lambda c: (-c.score, c.doc_id, c.chunk_idx if c.chunk_idx is not None else -1)
        )
        return chunks

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        """Giao diện :class:`Retriever` — đường chạy đầy đủ của Tuần 3.

        Có ``reranker``: lấy ``top_k_dense`` ứng viên → chấm lại → cắt còn
        ``top_k_rerank``, ``score`` khi đó **là** rerank score (0,1).

        Không có: trả thẳng ``top_k_dense`` ứng viên thô. Đây là cấu hình
        đối chứng của T3.4, **không** phải cấu hình chạy thật — xem cảnh báo
        ở docstring class.
        """
        chunks = self.search(query)
        if self._reranker is None:
            return chunks
        return self._reranker.rerank(
            query, chunks, top_k=self._cfg.retrieval.top_k_rerank
        )

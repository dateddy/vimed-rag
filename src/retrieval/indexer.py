"""Interface đẩy vector vào vector store + FakeIndexer in-memory.

``QdrantIndexer`` đã mở khoá ở Tuần 2 (DEC-021) nhưng **không** mở kết nối lúc
``__init__``: client dựng lười ở lần dùng đầu tiên, và ``qdrant_client`` chỉ
import bên trong hàm. Import module này không chạm mạng (ràng buộc #2).

Chú ý về type: ``index()`` nhận :class:`ChunkRecord` (index-time), KHÔNG phải
``RetrievedChunk`` (retrieve-time). Lý do đầy đủ ở docstring ``ChunkRecord``
và DEC-021 — tóm tắt: ``RetrievedChunk.specialty`` là số ít nên index qua nó
sẽ đánh rơi 15 bài thuộc cả hai khoa.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from src.config import IndexConfig, QdrantConfig
from src.retrieval.embedder import Embedder, EmbeddingBatch
from src.schemas import ChunkRecord

# Tên vector có tên trong Qdrant. Đổi tên = phải recreate collection, và
# Tuần 3 (`HybridRetriever`) phải đổi theo — nên để hằng dùng chung.
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"

# Namespace cố định để sinh point ID tất định. KHÔNG đổi giá trị này: đổi =
# mọi point cũ thành mồ côi, chạy lại sẽ nhân đôi collection thay vì đè.
_POINT_NAMESPACE = uuid.UUID("6f9f1d3a-1c2b-5e47-9a10-000000000001")


@runtime_checkable
class Indexer(Protocol):
    """Giao diện lập chỉ mục chunk vào vector store."""

    def index(self, chunks: list[ChunkRecord]) -> int:
        """Đẩy chunk vào store, trả về số lượng đã index."""
        ...


def collection_name(base: str, size: int) -> str:
    """Tên collection cho một chunk size — ``vimed_rag`` + 512 -> ``vimed_rag_512``.

    Ablation DEC-004 index mỗi size thành một collection riêng để so sánh
    được mà không phải xoá cái nào.
    """
    return f"{base}_{size}"


def point_id(doc_id: str, chunk_idx: int) -> str:
    """ID tất định cho một chunk: UUID5 của ``<doc_id>:<chunk_idx>``.

    Tất định để chạy lại là **upsert đè**, không nhân đôi — session Kaggle hay
    đứt giữa chừng nên đây là tính chất bắt buộc, không phải tối ưu.
    """
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{doc_id}:{chunk_idx}"))


def chunk_payload(chunk: ChunkRecord) -> dict:
    """Payload lưu kèm point.

    ``specialties`` là **list** (không phải chuỗi) để Qdrant match theo phần
    tử: bài thuộc cả hai khoa sẽ khớp cả filter ``tim_mach`` lẫn
    ``tieu_duong``. Đây là điểm DEC-017 cảnh báo — đừng thay bằng
    ``specialty`` số ít.
    """
    return {
        "doc_id": chunk.doc_id,
        "chunk_idx": chunk.chunk_idx,
        "n_chunks": chunk.n_chunks,
        "text": chunk.text,
        "title": chunk.title,
        "source": chunk.source,
        "specialties": list(chunk.specialties),
        "specialty": chunk.specialty,  # tiện hiển thị; KHÔNG dùng để lọc
    }


class FakeIndexer:
    """Indexer giả: lưu chunk trong bộ nhớ (dùng cho test/demo)."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._embedder = embedder
        self.store: list[ChunkRecord] = []
        self.points: list[dict] = []

    def index(self, chunks: list[ChunkRecord]) -> int:
        self.store.extend(chunks)
        self.points.extend(
            {"id": point_id(c.doc_id, c.chunk_idx), "payload": chunk_payload(c)}
            for c in chunks
        )
        return len(chunks)


class QdrantIndexer:
    """Indexer thật đẩy vector dense+sparse lên một collection Qdrant.

    Vòng đời: ``ensure_collection()`` (tạo schema + payload index) rồi
    ``index()`` nhiều lần theo lô. Client Qdrant dựng **lười** — dựng object
    này trong test không mở kết nối nào.

    Args:
        cfg: khối ``qdrant`` (url + api_key). URL/key đọc từ ``.env``.
        embedder: phải có ``embed_hybrid()`` nếu muốn sparse; nếu không có thì
            chỉ index dense (vẫn chạy, nhưng Tuần 3 mất nhánh hybrid).
        index_cfg: khối ``index`` — dim, distance, kích thước lô.
        collection: tên collection đầy đủ (dùng :func:`collection_name`).
    """

    def __init__(
        self,
        cfg: QdrantConfig,
        embedder: Embedder,
        index_cfg: IndexConfig,
        collection: str,
    ) -> None:
        self._cfg = cfg
        self._embedder = embedder
        self._index_cfg = index_cfg
        self.collection = collection
        self._client = None  # dựng lười — xem client()

    # ----------------------------------------------------------------- #
    def client(self):
        """Mở kết nối Qdrant ở lần cần đầu tiên. Import trễ có chủ đích."""
        if self._client is None:
            from qdrant_client import QdrantClient  # import trễ

            self._client = QdrantClient(
                url=self._cfg.url,
                api_key=self._cfg.api_key or None,
                timeout=60,
            )
        return self._client

    @property
    def supports_sparse(self) -> bool:
        """Embedder có sinh được sparse không?"""
        return hasattr(self._embedder, "embed_hybrid")

    # ----------------------------------------------------------------- #
    def ensure_collection(self, recreate: bool = False) -> bool:
        """Tạo collection nếu chưa có. Trả về True nếu vừa tạo mới.

        ``recreate=True`` **xoá sạch** collection cũ rồi tạo lại — chỉ dùng
        khi đổi ``dense_dim``/``distance``, vì nó vứt toàn bộ vector đã embed.

        Luôn tạo **payload index trên ``specialties``**: thiếu nó thì filter
        theo khoa ở Tuần 3 phải quét toàn bộ collection.
        """
        from qdrant_client import models  # import trễ

        client = self.client()
        exists = client.collection_exists(self.collection)

        if exists and not recreate:
            return False
        if exists:
            client.delete_collection(self.collection)

        sparse_cfg = None
        if self.supports_sparse:
            sparse_cfg = {
                SPARSE_VECTOR: models.SparseVectorParams(
                    index=models.SparseIndexParams()
                )
            }

        client.create_collection(
            collection_name=self.collection,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(
                    size=self._index_cfg.dense_dim,
                    distance=models.Distance[self._index_cfg.distance.upper()],
                )
            },
            sparse_vectors_config=sparse_cfg,
        )

        # KEYWORD index trên list -> match theo từng phần tử (DEC-017).
        client.create_payload_index(
            collection_name=self.collection,
            field_name="specialties",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=self.collection,
            field_name="doc_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        return True

    # ----------------------------------------------------------------- #
    def _embed(self, texts: list[str]) -> EmbeddingBatch:
        if self.supports_sparse:
            return self._embedder.embed_hybrid(texts)  # type: ignore[attr-defined]
        return EmbeddingBatch(dense=self._embedder.embed(texts), sparse=[])

    def _points(self, chunks: list[ChunkRecord], batch: EmbeddingBatch) -> list:
        from qdrant_client import models  # import trễ

        points = []
        for i, chunk in enumerate(chunks):
            vector: dict = {DENSE_VECTOR: batch.dense[i]}
            if batch.sparse:
                sv = batch.sparse[i]
                vector[SPARSE_VECTOR] = models.SparseVector(
                    indices=list(sv.keys()), values=list(sv.values())
                )
            points.append(
                models.PointStruct(
                    id=point_id(chunk.doc_id, chunk.chunk_idx),
                    vector=vector,
                    payload=chunk_payload(chunk),
                )
            )
        return points

    def index(self, chunks: list[ChunkRecord]) -> int:
        """Embed rồi upsert một lô chunk. Trả về số point đã ghi.

        Idempotent: point ID tất định nên chạy lại trên cùng chunk là **đè**,
        không nhân đôi.
        """
        if not chunks:
            return 0
        batch = self._embed([c.text for c in chunks])
        self.client().upsert(
            collection_name=self.collection,
            points=self._points(chunks, batch),
            wait=True,
        )
        return len(chunks)

    def index_all(
        self,
        chunks: list[ChunkRecord],
        on_progress=None,
    ) -> int:
        """Index toàn bộ theo lô ``index.upsert_batch``.

        Args:
            chunks: toàn bộ chunk cần index.
            on_progress: callback ``(đã_xong, tổng)`` gọi sau mỗi lô — dùng
                để in tiến độ trong notebook Kaggle mà không nhét ``print``
                vào lớp nghiệp vụ.
        """
        total = len(chunks)
        done = 0
        for lot in _batched(chunks, self._index_cfg.upsert_batch):
            done += self.index(lot)
            if on_progress:
                on_progress(done, total)
        return done

    def count(self) -> int:
        """Số point hiện có trong collection."""
        return self.client().count(self.collection, exact=True).count


def _batched(items: list, size: int) -> Iterator[list]:
    """Chia list thành các lô ``size`` phần tử (lô cuối có thể ngắn hơn)."""
    for start in range(0, len(items), size):
        yield items[start : start + size]

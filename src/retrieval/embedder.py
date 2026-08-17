"""Interface embedder + FakeEmbedder cho test/demo.

``BgeM3Embedder`` đã mở khoá ở Tuần 2 (DEC-021) nhưng model vẫn được nạp
**lười**: import module này KHÔNG kéo theo torch/FlagEmbedding và không chạm
mạng — ràng buộc #2 trong ``brain/contracts/constraints.md``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from src.config import IndexConfig, ModelsConfig

# Sparse vector của bge-m3: token_id -> trọng số. Khác dense ở chỗ thưa và
# không cố định chiều, nên KHÔNG nhét được vào ``list[list[float]]``.
SparseVector = dict[int, float]


@dataclass
class EmbeddingBatch:
    """Kết quả embed hybrid: dense + sparse cho cùng một lô văn bản.

    ``dense[i]`` và ``sparse[i]`` luôn ứng với ``texts[i]``. ``sparse`` rỗng
    khi embedder không hỗ trợ (vd :class:`FakeEmbedder`).
    """

    dense: list[list[float]]
    sparse: list[SparseVector] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.dense)


@runtime_checkable
class Embedder(Protocol):
    """Giao diện sinh vector nhúng cho danh sách văn bản."""

    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Trả về list vector (mỗi vector là list[float] độ dài ``dim``)."""
        ...


@runtime_checkable
class HybridEmbedder(Protocol):
    """Embedder sinh được cả dense lẫn sparse (bge-m3).

    Tách khỏi :class:`Embedder` để ``FakeEmbedder`` và mọi code cũ gọi
    ``embed()`` không phải đổi gì (DEC-021).
    """

    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_hybrid(self, texts: list[str]) -> EmbeddingBatch: ...


class FakeEmbedder:
    """Embedder giả: vector tất định theo nội dung (seed = hash text).

    Dùng để test/demo mà không cần GPU hay model thật. Cùng text → cùng vector.
    """

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def _vector_for(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        # Sinh dim số giả ngẫu nhiên tất định trong [0, 1).
        vec: list[float] = []
        for _ in range(self.dim):
            seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
            vec.append((seed % 10_000) / 10_000.0)
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]

    def embed_hybrid(self, texts: list[str]) -> EmbeddingBatch:
        """Dense giả + sparse giả tất định — đủ để test đường ống index.

        Sparse lấy hash của từng token làm id nên cùng text → cùng sparse,
        và hai text chung từ thì chung id: đủ tính chất để test filter/merge
        mà không cần model thật.
        """
        sparse: list[SparseVector] = []
        for text in texts:
            vec: SparseVector = {}
            for token in text.split():
                tid = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16)
                vec[tid] = vec.get(tid, 0.0) + 1.0
            sparse.append(vec)
        return EmbeddingBatch(dense=self.embed(texts), sparse=sparse)


class BgeM3Embedder:
    """Embedder thật dùng BAAI/bge-m3 (dense + sparse) — Tuần 2, DEC-021.

    Model được nạp **lười** ở lần ``embed*`` đầu tiên, KHÔNG ở ``__init__``:
    dựng object này trong test/scaffold không tải 2.2GB weight và không chạm
    mạng (ràng buộc #2). ``FlagEmbedding`` cũng chỉ import bên trong hàm.

    Dùng ``FlagEmbedding`` chứ không ``sentence-transformers`` vì chỉ nó trả
    được **sparse** trong cùng một lượt forward — mà ``retrieval.hybrid=true``
    thì thiếu sparse là phải chạy lại cả session GPU.
    """

    def __init__(
        self,
        cfg: ModelsConfig,
        index_cfg: IndexConfig | None = None,
        *,
        use_fp16: bool | None = None,
    ) -> None:
        self._cfg = cfg
        self._index_cfg = index_cfg
        self.dim = index_cfg.dense_dim if index_cfg else 1024
        self._max_length = index_cfg.max_length if index_cfg else 1024
        self._batch_size = index_cfg.embed_batch if index_cfg else 16
        if use_fp16 is None:
            use_fp16 = index_cfg.use_fp16 if index_cfg else True
        self._use_fp16 = use_fp16
        self._model = None  # nạp lười — xem _ensure_model()

    # ----------------------------------------------------------------- #
    def _ensure_model(self):
        """Nạp bge-m3 lần đầu cần tới. Import trễ để test chạy offline."""
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel  # import trễ, có chủ đích

            self._model = BGEM3FlagModel(
                self._cfg.embedder, use_fp16=self._use_fp16
            )
        return self._model

    def _encode(self, texts: list[str], *, sparse: bool) -> dict:
        model = self._ensure_model()
        return model.encode(
            texts,
            batch_size=self._batch_size,
            max_length=self._max_length,
            return_dense=True,
            return_sparse=sparse,
            return_colbert_vecs=False,
        )

    @staticmethod
    def _to_sparse(raw) -> SparseVector:
        """Chuẩn hoá ``lexical_weights`` của FlagEmbedding về ``dict[int,float]``.

        FlagEmbedding trả key là **chuỗi** token-id và value là ``np.float32``;
        Qdrant cần ``int``/``float`` thuần, nếu không JSON encode sẽ nổ.
        Trọng số 0 bị loại — giữ lại chỉ làm phình sparse vector.
        """
        return {
            int(k): float(v) for k, v in dict(raw).items() if float(v) > 0.0
        }

    # ----------------------------------------------------------------- #
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Chỉ dense — giữ đúng giao diện :class:`Embedder`."""
        if not texts:
            return []
        out = self._encode(texts, sparse=False)
        return [[float(x) for x in vec] for vec in out["dense_vecs"]]

    def embed_hybrid(self, texts: list[str]) -> EmbeddingBatch:
        """Dense + sparse trong **một** lượt forward (rẻ hơn gọi 2 lần)."""
        if not texts:
            return EmbeddingBatch(dense=[], sparse=[])
        out = self._encode(texts, sparse=True)
        return EmbeddingBatch(
            dense=[[float(x) for x in vec] for vec in out["dense_vecs"]],
            sparse=[self._to_sparse(w) for w in out["lexical_weights"]],
        )

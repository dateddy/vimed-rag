"""Lớp rerank (Tuần 3 — T3.2, DEC-033 → **DEC-037**).

Nhiệm vụ: chấm lại ``top_k_dense`` ứng viên thô mà ``HybridRetriever`` lấy về,
rồi cắt xuống ``top_k_rerank``. Đây cũng là **lớp duy nhất** đưa
``RetrievedChunk.score`` về đúng thang mà ``Grader`` giả định.

⛔ **Vì sao score BẮT BUỘC đi qua sigmoid — đọc trước khi sửa file này.**
Ngưỡng grader là ``correct=0.6`` / ``incorrect=0.3``, tức thang **[0,1]**.
Nhưng ``bge-reranker-v2-m3`` là model 1 nhãn trả **logit thô** — đo được
``+4.125`` cho cặp đúng và ``-8.179`` cho cặp sai. Ném thẳng logit vào grader
là mọi chunk hoặc ``> 0.6`` hoặc ``< 0.3``, nhánh AMBIGUOUS không bao giờ
chạy, mà **không test nào khác đỏ**.

Score thô TRƯỚC rerank cũng không dùng được, cả ba (đo 2026-09-06 trên
``vimed_rag_512``):

===========  ==============  =============================================
``dense``    0.707 – 0.741   toàn bộ > 0.6 -> CORRECT tuyệt đối
``sparse``   0.180 – 0.194   toàn bộ < 0.3 -> INCORRECT tuyệt đối
``hybrid``   0.250 – 0.583   RRF k=2, rơi ngay GIỮA hai ngưỡng
===========  ==============  =============================================

Tệ nhất là ``hybrid``: nó không hỏng lộ liễu mà sinh ra hỗn hợp
CORRECT/AMBIGUOUS/INCORRECT trông hợp lý, Tuần 6 vẫn vẽ được risk–coverage —
chỉ là đo **thứ hạng RRF** thay vì độ liên quan.

**Vì sao tự gọi transformers thay vì dùng FlagEmbedding (DEC-037).**
``FlagEmbedding.FlagReranker`` — lựa chọn của DEC-033 — **không chạy được**
với ``transformers 5.5.4``: nó gọi ``tokenizer.prepare_for_model()``, API đã
bị gỡ ở transformers v5 (kiểm cả ``use_fast=True`` lẫn ``False``, đều không
còn). Hạ transformers xuống 4.x thì phá mất cấu hình embedder đã verify sạch
ở Tuần 2. Nên phần rerank đi thẳng ``AutoModelForSequenceClassification``, và
sigmoid do **chính file này** áp — không phụ thuộc mặc định của thư viện nào.
FlagEmbedding vẫn giữ, nhưng chỉ còn cho ``BgeM3Embedder`` (nhánh sparse).

Model nạp **lười**: import module này không kéo torch/transformers, không
chạm mạng (ràng buộc #2).
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Protocol, runtime_checkable

from src.config import ModelsConfig
from src.schemas import RetrievedChunk

# Cửa sổ subword khi chấm cặp (truy vấn, chunk). Chunk 512 TỪ tiếng Việt ~
# 700-900 subword (cùng đơn vị mà `index.max_length=1024` đã chọn ở DEC-021),
# cộng truy vấn ~20-40 subword. Mặc định 512 của các wrapper reranker là cắt
# cụt đuôi chunk rồi chấm điểm trên văn bản không đầy đủ — không báo lỗi.
DEFAULT_MAX_LENGTH = 1024

# CPU chấm ~20 cặp/truy vấn nên lô nhỏ là đủ; lô lớn chỉ tổ ngốn RAM khi mỗi
# cặp dài 1024 subword.
DEFAULT_BATCH_SIZE = 16


@runtime_checkable
class Reranker(Protocol):
    """Giao diện rerank: chấm lại và sắp xếp ứng viên theo độ liên quan."""

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Trả về chunk đã thay ``score``, sắp giảm dần, cắt còn ``top_k``."""
        ...


def sigmoid(x: float) -> float:
    """Logit → (0,1). Thuần Python, ổn định số học ở cả hai đầu.

    Viết tay thay vì gọi ``torch.sigmoid`` có hai lý do: (1) test được mà
    không cần torch, nên bất biến "score phải nằm trong (0,1)" có test riêng
    chạy trên máy chưa cài gì nặng; (2) phép chuẩn hoá là thứ DEC-037 phải
    bảo vệ, để nó nằm trong repo thì không bản nâng cấp thư viện nào đổi được.

    ``math.exp(-x)`` tràn khi ``x`` rất âm nên nhánh âm dùng dạng ``e/(1+e)``.
    """
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _apply(
    chunks: list[RetrievedChunk],
    scores: list[float],
    top_k: int | None,
) -> list[RetrievedChunk]:
    """Gắn score mới, sắp giảm dần, cắt ``top_k``.

    Dùng ``dataclasses.replace`` chứ KHÔNG dựng ``RetrievedChunk`` mới bằng
    tay: dựng tay là đúng chỗ đánh rơi 5 trường DEC-035 (``title``,
    ``source``, ``chunk_idx``, ``n_chunks``, ``specialties``) — Tuần 4 mất
    citation mà không có test nào đỏ.
    """
    scored = [replace(c, score=float(s)) for c, s in zip(chunks, scores)]
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k] if top_k else scored


class FakeReranker:
    """Reranker giả — điểm điều khiển được, không cần model.

    ``scores`` gán theo **vị trí** chunk đầu vào; hết thì lặp phần tử cuối
    (cùng quy ước với :class:`FakeRetriever`). Bỏ trống thì sinh dãy giảm dần
    ``1.0, 0.9, 0.8, …`` nên thứ tự đầu vào được giữ nguyên — tiện để kiểm
    riêng phần cắt ``top_k`` mà không lẫn với phần sắp xếp.
    """

    def __init__(self, scores: list[float] | None = None) -> None:
        self._scores = list(scores) if scores else None
        self.calls: list[tuple[str, int]] = []  # (query, số chunk) để test soi

    def _score_for(self, i: int) -> float:
        if self._scores is None:
            return max(0.0, 1.0 - 0.1 * i)
        return self._scores[min(i, len(self._scores) - 1)]

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        self.calls.append((query, len(chunks)))
        if not chunks:
            return []
        return _apply(chunks, [self._score_for(i) for i in range(len(chunks))], top_k)


class BgeReranker:
    """Reranker thật ``BAAI/bge-reranker-v2-m3`` qua transformers (DEC-037).

    Model + tokenizer nạp lười ở lần ``rerank`` đầu tiên — dựng object này
    trong test không tải weight và không chạm mạng.

    Đường đi: tokenize cặp ``(truy vấn, chunk)`` → forward → **logit** →
    :func:`sigmoid` → sắp xếp → cắt ``top_k``. Chỉ ``_logits`` chạm model, nên
    test thay mỗi hàm đó là kiểm được toàn bộ phần còn lại.

    Args:
        cfg: khối ``models`` — dùng ``cfg.reranker``.
        use_fp16: T4 bật; CPU phải tắt (fp16 trên CPU chậm hơn fp32).
        max_length: cửa sổ subword cho cặp (truy vấn, chunk).
        batch_size: số cặp mỗi lô.
        device: ``None`` = tự dò (cuda nếu có, không thì cpu).
    """

    def __init__(
        self,
        cfg: ModelsConfig,
        *,
        use_fp16: bool = False,
        max_length: int = DEFAULT_MAX_LENGTH,
        batch_size: int = DEFAULT_BATCH_SIZE,
        device: str | None = None,
    ) -> None:
        self._cfg = cfg
        self._use_fp16 = use_fp16
        self._max_length = max_length
        self._batch_size = batch_size
        self._device = device
        self._model = None  # nạp lười — xem _ensure_model()
        self._tokenizer = None

    # ----------------------------------------------------------------- #
    def _ensure_model(self):
        """Nạp bge-reranker-v2-m3 lần đầu cần tới. Import trễ có chủ đích."""
        if self._model is None:
            import torch  # import trễ
            from transformers import (  # import trễ
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            if self._device is None:
                self._device = "cuda" if torch.cuda.is_available() else "cpu"

            self._tokenizer = AutoTokenizer.from_pretrained(self._cfg.reranker)
            model = AutoModelForSequenceClassification.from_pretrained(
                self._cfg.reranker
            )
            # bge-reranker là model 1 nhãn: logits có shape (N, 1) nên
            # view(-1) ra đúng N điểm. Model 2 nhãn sẽ ra 2N điểm và zip() ở
            # _apply lặng lẽ cắt còn N -> điểm gán LỆCH chunk. Chặn ở đây.
            if model.config.num_labels != 1:
                raise ValueError(
                    f"{self._cfg.reranker} có num_labels="
                    f"{model.config.num_labels}, cần 1. Model này không phải "
                    "cross-encoder reranker 1 nhãn."
                )
            if self._use_fp16:
                model = model.half()
            self._model = model.to(self._device).eval()
        return self._model, self._tokenizer

    def logits(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Chấm **logit thô** theo lô. Đây là hàm DUY NHẤT chạm model.

        Công khai (không phải ``_logits``) vì T3.4 cần chính logit: sau
        sigmoid, mọi đoạn cùng chủ đề dồn về 0,98-0,99 và **mất phân giải**
        đúng ở vùng phải đặt ngưỡng. Logit thì còn tách được. Sigmoid vẫn
        là thứ ``rerank()`` trả ra cho pipeline — xem DEC-037.
        """
        import torch  # import trễ

        model, tok = self._ensure_model()
        out: list[float] = []
        for i in range(0, len(pairs), self._batch_size):
            lot = pairs[i : i + self._batch_size]
            enc = tok(
                [q for q, _ in lot],
                [t for _, t in lot],
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            ).to(self._device)
            with torch.no_grad():
                logits = model(**enc).logits.view(-1).float()
            out.extend(float(x) for x in logits)
        return out

    # ----------------------------------------------------------------- #
    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        pairs = [(query, c.text) for c in chunks]
        # ⛔ ĐỪNG BỎ sigmoid — xem docstring module và DEC-037.
        scores = [sigmoid(x) for x in self.logits(pairs)]
        return _apply(chunks, scores, top_k)

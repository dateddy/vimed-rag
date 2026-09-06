"""
Smoke test HybridRetriever trên Qdrant thật (Tuần 3 — T3.1 + T3.2).
====================================================================
Bắn MỘT truy vấn qua cả ba chế độ (dense / sparse / hybrid) rồi in top-k kèm
tiêu đề bài, để soi bằng mắt xem truy hồi có ra bài liên quan không. Đây là
bước "smoke test" mà plan Tuần 2 yêu cầu nhưng chưa chạy được vì lúc đó chưa
có retriever.

**KHÔNG phải phép đo.** Số liệu Recall@k / MRR / nDCG là việc của T3.4
(`scripts/eval_retrieval.py`) trên 12 câu nhóm E. Ở đây chỉ trả lời một câu
hỏi nhị phân: đường ống có chạy và có trả về bài đúng chủ đề không.

⚠️ `score` in ra **CHƯA phải rerank score** — T3.1 chưa có lớp rerank. Ba mode
ba thang khác nhau: `dense` là cosine (~0.71-0.74), `sparse` ~0.18-0.19, còn
`hybrid` là RRF của Qdrant với **k=2** (`1/(2+rank)`, rank từ 0) nên rơi
~0.25-0.58. ĐỪNG so chúng với `grader.correct_threshold` (xem DEC-033).

CHẠY:
    python scripts/smoke_retrieval.py
    python scripts/smoke_retrieval.py --query "Tiểu đường type 2 ăn gì?"
    python scripts/smoke_retrieval.py --size 256 --top-k 3
    python scripts/smoke_retrieval.py --mode hybrid --specialty tim_mach

Chỉ ĐỌC, không ghi gì lên cluster. Cần QDRANT_URL + QDRANT_API_KEY trong .env
và model bge-m3 đã cache (~2,3 GB). Chạy CPU được: chỉ encode 1 truy vấn.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import load_config  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402
from src.retrieval.retriever import RETRIEVAL_MODES, HybridRetriever  # noqa: E402

DEFAULT_QUERY = "Triệu chứng tăng huyết áp?"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", default=DEFAULT_QUERY, help="truy vấn cần thử")
    ap.add_argument("--size", type=int, default=None, help="chunk size (mặc định: config)")
    ap.add_argument("--collection", default=None, help="ghi đè tên collection")
    ap.add_argument(
        "--mode",
        default="all",
        choices=("all", *RETRIEVAL_MODES),
        help="chế độ truy hồi (mặc định: chạy cả ba để so bằng mắt)",
    )
    ap.add_argument("--top-k", type=int, default=5, help="số chunk in ra")
    ap.add_argument(
        "--specialty",
        default=None,
        help="lọc theo khoa — MẶC ĐỊNH TẮT (DEC-036), chỉ để thử tay",
    )
    ap.add_argument(
        "--rerank",
        action="store_true",
        help="bật bge-reranker-v2-m3 (T3.2). LẦN ĐẦU TẢI ~2,3 GB. "
        "Khi bật thì đi đường retrieve() đầy đủ: top_k_dense -> top_k_rerank, "
        "và score MỚI cùng thang với ngưỡng grader.",
    )
    return ap.parse_args()


def _use_fp16(cfg) -> bool:
    """fp16 chỉ bật khi thật sự có GPU — CPU không chạy fp16."""
    try:
        import torch

        return bool(cfg.index.use_fp16 and torch.cuda.is_available())
    except ImportError:
        return False


def make_embedder(cfg):
    """bge-m3 thật, tự tắt fp16 khi không có GPU."""
    from src.retrieval.embedder import BgeM3Embedder

    fp16 = _use_fp16(cfg)
    print(f"Embedder: {cfg.models.embedder} (fp16={fp16})")
    return BgeM3Embedder(cfg.models, cfg.index, use_fp16=fp16)


def make_reranker(cfg):
    """bge-reranker-v2-m3 qua transformers, logit → sigmoid (DEC-037)."""
    from src.retrieval.reranker import BgeReranker

    fp16 = _use_fp16(cfg)
    ml = cfg.retrieval.rerank_max_length
    print(f"Reranker: {cfg.models.reranker} (fp16={fp16}, max_length={ml}, logit→sigmoid)")
    return BgeReranker(cfg.models, use_fp16=fp16, max_length=ml)


def show(mode: str, chunks, elapsed: float) -> None:
    print(f"\n--- {mode.upper()} ({elapsed:.2f}s) ---")
    if not chunks:
        print("    (rỗng — collection sai tên, hoặc filter khoa cắt sạch?)")
        return
    for i, c in enumerate(chunks, 1):
        pos = f"{c.chunk_idx}/{c.n_chunks}" if c.chunk_idx is not None else "?"
        print(f"{i:2d}. score={c.score:.4f}  doc={c.doc_id}  đoạn {pos}")
        print(f"    [{','.join(c.specialties) or '-'}] {c.title or '(không tiêu đề)'}")
        print(f"    {c.text[:140].replace(chr(10), ' ')}…")


def main() -> int:
    args = parse_args()
    cfg = load_config()
    size = args.size or cfg.chunking.size
    coll = args.collection or collection_name(cfg.qdrant.collection, size)
    modes = list(RETRIEVAL_MODES) if args.mode == "all" else [args.mode]

    print(f"Query   : {args.query!r}")
    print(f"Coll    : {coll}")
    print(f"Lọc khoa: {args.specialty or 'TẮT (DEC-036)'}")

    if args.rerank:
        print(
            f"Đường  : retrieve() — {cfg.retrieval.top_k_dense} ứng viên "
            f"-> rerank -> {cfg.retrieval.top_k_rerank}"
        )
    else:
        print(f"Đường  : search() thô — top-{args.top_k}, CHƯA rerank")

    embedder = make_embedder(cfg)
    reranker = make_reranker(cfg) if args.rerank else None

    # Nạp model TRƯỚC khi bấm giờ, nếu không lần đo đầu gánh cả 2,3 GB weight.
    t0 = time.perf_counter()
    embedder.embed_hybrid(["khởi động"])
    print(f"Nạp embedder + warm-up: {time.perf_counter() - t0:.1f}s")

    if reranker is not None:
        from src.schemas import RetrievedChunk

        t0 = time.perf_counter()
        reranker.rerank(
            "khởi động",
            [RetrievedChunk(doc_id="w", text="khởi động", specialty=None, score=0.0)],
        )
        print(f"Nạp reranker + warm-up: {time.perf_counter() - t0:.1f}s")

    from qdrant_client import QdrantClient

    client = QdrantClient(url=cfg.qdrant.url, api_key=cfg.qdrant.api_key or None, timeout=60)

    # Hâm nóng kết nối TLS TRƯỚC vòng lặp. Không có dòng này thì mode chạy
    # ĐẦU TIÊN gánh cả handshake tới Qdrant Cloud (~1,7s đo được ngày
    # 2026-09-03) và trông chậm gấp 4 lần hai mode sau — kết luận sai về chi
    # phí. T3.4 đo giờ chính thức cũng phải giữ đúng thứ tự này.
    t0 = time.perf_counter()
    client.count(coll, exact=False)
    print(f"Bắt tay TLS + kết nối Qdrant: {time.perf_counter() - t0:.2f}s")

    for mode in modes:
        r = HybridRetriever(
            cfg,
            embedder,
            collection=coll,
            mode=mode,
            specialty=args.specialty,
            reranker=reranker,
            client=client,
        )
        t0 = time.perf_counter()
        if r.scores_are_rerank:
            chunks = r.retrieve(args.query)
        else:
            chunks = r.search(args.query, limit=args.top_k)
        show(mode, chunks, time.perf_counter() - t0)

    if args.rerank:
        g = cfg.grader
        print(
            f"\n✅ score ở trên LÀ rerank score, thang (0,1) — so được với "
            f"correct={g.correct_threshold} / incorrect={g.incorrect_threshold}. "
            "Nhớ: 2 ngưỡng này vẫn là giá trị TẠM, chốt thật ở Tuần 6."
        )
    else:
        print(
            "\n⚠️  score ở trên CHƯA phải rerank score. Đừng so với "
            "grader.correct_threshold — DEC-033. Thêm --rerank để đi đường thật."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

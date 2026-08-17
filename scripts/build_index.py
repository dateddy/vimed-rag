"""
Dựng chỉ mục Qdrant: corpus.jsonl -> chunk -> embed (bge-m3) -> upsert.
=======================================================================
Tuần 2, DEC-021. Mỗi chunk size thành MỘT collection riêng cho ablation
DEC-004: ``vimed_rag_256`` và ``vimed_rag_512``.

Số chunk đã đo sẵn ở DEC-020 — dùng để kiểm chéo sau khi chạy:
    size 512 -> 4.972 point     size 256 -> 10.246 point

CHẠY
----
    # 1. Không GPU, không mạng — kiểm đường ống trước:
    python scripts/build_index.py --size 512 --dry-run

    # 2. Vẫn không GPU, ghi thật lên collection tạm rồi tự xoá:
    python scripts/build_index.py --size 512 --fake --limit 20 --smoke

    # 3. Thật, trên Kaggle T4:
    python scripts/build_index.py --size 512
    python scripts/build_index.py --size 256

Cần ``QDRANT_URL`` + ``QDRANT_API_KEY`` trong env (trừ ``--dry-run``).
KHÔNG cần ``HF_TOKEN``: script đọc ``corpus.jsonl`` đã sinh sẵn.

Chạy lại là AN TOÀN — point ID tất định nên upsert đè, không nhân đôi.
Session đứt giữa chừng thì chạy lại với ``--start <số point đã xong>``.
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
from src.data.chunker import chunk_records  # noqa: E402
from src.data.loader import load_documents  # noqa: E402
from src.retrieval.embedder import FakeEmbedder  # noqa: E402
from src.retrieval.indexer import QdrantIndexer, collection_name  # noqa: E402


def make_embedder(cfg, use_fake: bool):
    """FakeEmbedder (không GPU/mạng) hoặc bge-m3 thật với fp16 tự dò."""
    if use_fake:
        print("!! --fake: dùng FakeEmbedder, vector VÔ NGHĨA về mặt ngữ nghĩa.")
        print("   Chỉ để kiểm đường ống/schema. ĐỪNG ghi vào collection thật.")
        return FakeEmbedder(dim=cfg.index.dense_dim)

    from src.retrieval.embedder import BgeM3Embedder

    use_fp16 = cfg.index.use_fp16
    try:
        import torch

        if not torch.cuda.is_available():
            use_fp16 = False
            print("!! Không thấy GPU — tắt fp16, embed trên CPU sẽ RẤT chậm.")
        else:
            print(f"GPU     : {torch.cuda.get_device_name(0)}")
    except ImportError:
        use_fp16 = False

    print(f"Model   : {cfg.models.embedder} (fp16={use_fp16})")
    return BgeM3Embedder(cfg.models, cfg.index, use_fp16=use_fp16)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=None, help="chunk size (mặc định: config)")
    ap.add_argument("--overlap", type=int, default=None, help="overlap (mặc định: config)")
    ap.add_argument("--corpus", type=Path, default=None, help="đường dẫn corpus.jsonl")
    ap.add_argument("--collection", default=None, help="ghi đè tên collection")
    ap.add_argument("--limit", type=int, default=None, help="chỉ index N chunk đầu")
    ap.add_argument("--start", type=int, default=0, help="bỏ qua N chunk đầu (resume)")
    ap.add_argument("--fake", action="store_true", help="FakeEmbedder — không GPU/mạng")
    ap.add_argument("--dry-run", action="store_true", help="chỉ chunk + in số, không kết nối")
    ap.add_argument(
        "--recreate",
        action="store_true",
        help="XOÁ collection cũ rồi tạo lại (mất toàn bộ vector đã embed)",
    )
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="ghi vào collection tạm '<tên>_smoke' rồi XOÁ sau khi xong",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()

    size = args.size or cfg.chunking.size
    overlap = args.overlap if args.overlap is not None else cfg.chunking.overlap

    if size not in cfg.index.sizes:
        print(f"!! size={size} không nằm trong index.sizes={cfg.index.sizes}.")
        print("   Ablation DEC-004 chỉ chốt 2 size này — thêm size = thêm collection.")

    corpus = args.corpus or Path(cfg.data.processed_dir) / "corpus.jsonl"
    if not corpus.exists():
        print(f"!! Không thấy {corpus}.")
        print("   Local: python scripts/run_ingestion.py")
        print("   Kaggle: gắn Dataset chứa corpus.jsonl rồi truyền --corpus")
        return 1

    coll = args.collection or collection_name(cfg.qdrant.collection, size)
    if args.smoke:
        coll = f"{coll}_smoke"

    docs = load_documents(corpus)
    chunks = chunk_records(docs, size, overlap)

    print(f"Corpus  : {corpus} ({len(docs)} bài)")
    print(f"Chunking: size={size} overlap={overlap} -> {len(chunks)} chunk")
    print(f"Đích    : collection '{coll}' @ {cfg.qdrant.url or '(chưa set QDRANT_URL)'}")

    if args.start:
        chunks = chunks[args.start :]
        print(f"--start={args.start}: bỏ qua, còn {len(chunks)} chunk.")
    if args.limit:
        chunks = chunks[: args.limit]
        print(f"--limit={args.limit}: chỉ index {len(chunks)} chunk.")

    if not chunks:
        print("!! Không còn chunk nào để index.")
        return 1

    if args.dry_run:
        both = sum(1 for c in chunks if len(c.specialties) > 1)
        print("\n--- DRY RUN (không kết nối Qdrant) ---")
        print(f"  point sẽ ghi     : {len(chunks)}")
        print(f"  chunk 2 khoa     : {both}  <- phải > 0, nếu 0 là DEC-017 bị vi phạm")
        print(f"  payload mẫu      : {chunks[0].__dict__ | {'text': '...'}}")
        return 0

    embedder = make_embedder(cfg, args.fake)
    indexer = QdrantIndexer(cfg.qdrant, embedder, cfg.index, coll)

    created = indexer.ensure_collection(recreate=args.recreate)
    print(f"Collection {'vừa tạo' if created else 'đã có sẵn (upsert đè)'}"
          f" · sparse={'có' if indexer.supports_sparse else 'KHÔNG'}")

    t0 = time.time()

    def progress(done: int, total: int) -> None:
        elapsed = time.time() - t0
        rate = done / elapsed if elapsed else 0.0
        eta = (total - done) / rate if rate else 0.0
        print(f"  {done:6d}/{total}  {done / total:5.1%}  "
              f"{rate:5.1f} chunk/s  ETA {eta / 60:5.1f} phút", flush=True)

    n = indexer.index_all(chunks, on_progress=progress)
    print(f"\nĐã upsert {n} point trong {(time.time() - t0) / 60:.1f} phút.")
    print(f"Collection '{coll}' hiện có {indexer.count()} point.")

    if args.smoke:
        indexer.client().delete_collection(coll)
        print(f"--smoke: đã XOÁ collection tạm '{coll}'.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

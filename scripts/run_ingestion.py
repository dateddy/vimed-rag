"""Ingestion giai đoạn 1: load → clean → gán khoa → `data/processed/`.

Gate 0 = GO (`brain/contracts/gates.md`) nên giai đoạn này đã mở khoá. Chính
sách gán khoa theo DEC-016, ngưỡng đọc từ `config/config.yaml` khối `data`.

Giai đoạn 2 (chunk → embed → index Qdrant) vẫn GATED: `BgeM3Embedder` chờ
Tuần 2, `QdrantIndexer` chờ Tuần 3. Script này dừng đúng ở ranh giới đó.

CHẠY:
    # corpus là dataset gated -> cần HF_TOKEN trong env (mở terminal mới sau setx)
    python scripts/run_ingestion.py
    python scripts/run_ingestion.py --limit 2000    # smoke test trên tập con
    python scripts/run_ingestion.py --stats-only    # không ghi file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Cho phép chạy trực tiếp `python scripts/run_ingestion.py` từ gốc repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config  # noqa: E402
from src.data.loader import build_documents, save_documents  # noqa: E402

# Ép stdout UTF-8 để in tiếng Việt trên console Windows (cp1252) không lỗi.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Tiêu chí #1 của Gate 0 — xem `brain/contracts/gates.md`. Đây là ngưỡng gate,
# không phải tham số pipeline, nên để ở đây thay vì config.
MIN_ARTICLES_PER_SPECIALTY = 150

OUTPUT_NAME = "corpus.jsonl"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="chỉ xử lý N bài đầu (smoke test; KHÔNG dùng cho corpus chính thức)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"file JSONL đầu ra (mặc định <processed_dir>/{OUTPUT_NAME})",
    )
    ap.add_argument(
        "--stats-only",
        action="store_true",
        help="chỉ in thống kê, không ghi file",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()
    data_cfg = cfg.data

    print(f"Dataset : {data_cfg.dataset} (split: {data_cfg.split})")
    print(
        f"Chính sách gán khoa (DEC-016): TITLE hoặc "
        f">= {data_cfg.specialty_min_keyword_count} lần"
    )
    print(f"Khoa    : {', '.join(cfg.specialties)}")
    print("\nĐang tải corpus... (dataset gated — cần HF_TOKEN)")

    from datasets import load_dataset  # import trễ: chỉ tải khi thật sự chạy

    dataset = load_dataset(data_cfg.dataset, split=data_cfg.split)
    print(f"Đã tải {len(dataset)} bài thô.")

    rows = dataset
    if args.limit:
        rows = dataset.select(range(min(args.limit, len(dataset))))
        print(f"!! --limit={args.limit}: chỉ xử lý {len(rows)} bài (smoke test).")

    docs, stats = build_documents(
        rows, cfg.specialties, data_cfg, source=data_cfg.dataset
    )

    print("\n--- THỐNG KÊ THEO KHOA ---")
    for spec, n in stats.per_specialty.items():
        ok = n >= MIN_ARTICLES_PER_SPECIALTY
        print(
            f"  {spec:12s}: {n:5d} bài   [{'PASS' if ok else 'FAIL'}] "
            f"(cần >={MIN_ARTICLES_PER_SPECIALTY})"
        )
    both_pct = stats.both / stats.total if stats.total else 0.0
    print(f"  {'tổng':12s}: {stats.total:5d} bài   (trùng cả 2 khoa: "
          f"{stats.both} = {both_pct:.1%})")
    print(
        f"\n  đã loại: {stats.skipped_short} bài ngắn (<{data_cfg.min_article_chars} "
        f"ký tự) · {stats.skipped_duplicate} trùng · "
        f"{stats.skipped_no_specialty} không thuộc 2 khoa"
    )

    passed = stats.meets_floor(MIN_ARTICLES_PER_SPECIALTY)
    if not passed:
        print(
            "\n!! Có khoa dưới ngưỡng Gate 0. Đừng index — xem lại "
            "`data.specialty_min_keyword_count` hoặc config/specialties.yaml."
        )

    if args.stats_only:
        print("\n--stats-only: không ghi file.")
    else:
        out = args.out or Path(data_cfg.processed_dir) / OUTPUT_NAME
        n = save_documents(docs, out)
        print(f"\nĐã ghi {n} bài -> {out}")

    print(
        "\nGIAI ĐOẠN 2 VẪN GATED: chunk -> embed (BgeM3Embedder, Tuần 2) -> "
        "index (QdrantIndexer, Tuần 3)."
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

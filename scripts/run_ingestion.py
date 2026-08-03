"""End-to-end ingestion: load → clean → chunk → embed → index Qdrant.

# GATED — CẢNH BÁO: KHÔNG chạy với data thật cho tới khi
`scripts/gate0_data_check.py` trả GO. Script này chủ động chặn.

Khi Gate 0 GO, wiring dự kiến (dùng các thành phần đã inject-able):
    cfg    = load_config()
    raw    = load_hf_dataset(...)             # loader (GATED tới Tuần 2)
    docs   = clean_documents([r.text ...])     # cleaner (ĐÃ CÓ)
    chunks = chunk_documents(docs, cfg.chunking)  # chunker (ĐÃ CÓ)
    idx    = QdrantIndexer(cfg.qdrant, BgeM3Embedder(cfg.models))  # GATED
    idx.index([...])
"""

from __future__ import annotations

import sys

# Ép stdout UTF-8 để in tiếng Việt trên console Windows (cp1252) không lỗi.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    print(
        "GATED: run_ingestion bị chặn.\n"
        "Chạy `python scripts/gate0_data_check.py` trước; chỉ tiếp tục khi kết quả là GO."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

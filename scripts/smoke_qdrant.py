"""Smoke test kết nối Qdrant Cloud (DEC-018) — đóng DoD Tuần 1.

Chạy: python scripts/smoke_qdrant.py
Đọc QDRANT_URL / QDRANT_API_KEY từ .env qua load_config(). Không ghi gì lên cluster.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # cp1252 cắn tiếng Việt trên Windows

from src.config import load_config  # noqa: E402


def main() -> int:
    cfg = load_config()
    url, api_key = cfg.qdrant.url, cfg.qdrant.api_key

    if not url:
        print("FAIL: QDRANT_URL rỗng. Điền REST endpoint của cluster vào .env —")
        print("      dạng https://<cluster-id>.<region>.cloud.qdrant.io:6333")
        print("      (KHÔNG phải URL trang dashboard cloud.qdrant.io/accounts/...)")
        return 1
    if url.startswith("https://cloud.qdrant.io/"):
        print("FAIL: QDRANT_URL đang là URL trang dashboard, không phải REST endpoint.")
        print("      Lấy đúng endpoint ở mục 'Endpoint' trên trang cluster overview.")
        return 1
    if "cloud.qdrant.io" in url and not api_key:
        print("FAIL: dùng Qdrant Cloud thì bắt buộc có QDRANT_API_KEY trong .env.")
        return 1

    from qdrant_client import QdrantClient

    print(f"Đang kết nối: {url}")
    client = QdrantClient(url=url, api_key=api_key or None, timeout=15)
    collections = client.get_collections().collections

    print(f"OK — kết nối được. {len(collections)} collection: "
          f"{[c.name for c in collections] or '(rỗng, đúng như mong đợi)'}")
    print("==> DoD Tuần 1 'Qdrant chạy' ĐÓNG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

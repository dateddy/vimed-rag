"""
Kiểm chỉ mục Qdrant sau khi build_index chạy xong (Tuần 2, DEC-021).
====================================================================
Chạy NGAY sau mỗi lần index, TRƯỚC khi đóng session Kaggle. Bốn thứ được
kiểm, thứ tự từ rẻ tới đắt:

1. SỐ POINT  — phải khớp số đã chốt ở DEC-020 (512 -> 4.972 · 256 -> 10.246).
   Lệch = corpus khác, hoặc chunking bị đổi, hoặc session đứt giữa chừng.
2. SCHEMA    — có đúng named vector `dense` + sparse `sparse` không, dim đúng
   `index.dense_dim` không.
3. FILTER KHOA — **quan trọng nhất**. Đếm point theo từng khoa và kiểm bài
   thuộc CẢ HAI khoa có khớp cả hai filter không. Đây là bất biến DEC-017:
   nếu payload lưu `specialty` số ít thay vì `specialties` list thì bước này
   là chỗ DUY NHẤT phát hiện ra — số point tổng vẫn đúng.
4. SEARCH THỬ — bắn 1 vector ngẫu nhiên để chắc index HNSW đã dựng và trả
   được kết quả kèm payload. KHÔNG kiểm chất lượng ngữ nghĩa (việc của Tuần 3).

CHẠY:
    python scripts/verify_index.py --size 512
    python scripts/verify_index.py --size 256
    python scripts/verify_index.py --collection vimed_rag_512

Chỉ ĐỌC, không ghi gì lên cluster. Cần QDRANT_URL + QDRANT_API_KEY.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import load_config  # noqa: E402
from src.retrieval.indexer import (  # noqa: E402
    DENSE_VECTOR,
    SPARSE_VECTOR,
    collection_name,
)

# Số chunk đã chốt ở DEC-020 — nguồn sự thật để đối chiếu.
EXPECTED_POINTS = {512: 4972, 256: 10246}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=None, help="chunk size (mặc định: config)")
    ap.add_argument("--collection", default=None, help="ghi đè tên collection")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()
    size = args.size or cfg.chunking.size
    coll = args.collection or collection_name(cfg.qdrant.collection, size)

    from qdrant_client import QdrantClient, models

    client = QdrantClient(url=cfg.qdrant.url, api_key=cfg.qdrant.api_key or None, timeout=60)

    if not client.collection_exists(coll):
        print(f"FAIL: collection '{coll}' không tồn tại. Chạy build_index trước.")
        return 1

    print(f"Collection: {coll}")
    failures: list[str] = []

    # --- 1. Số point ----------------------------------------------------
    n = client.count(coll, exact=True).count
    expected = EXPECTED_POINTS.get(size)
    print(f"\n[1] SỐ POINT: {n}")
    if expected is None:
        print(f"    (size={size} không có số chốt trong DEC-020 — bỏ qua đối chiếu)")
    elif n == expected:
        print(f"    PASS — khớp DEC-020 ({expected}).")
    else:
        print(f"    FAIL — DEC-020 chốt {expected}, lệch {n - expected:+d}.")
        print("    Nguyên nhân hay gặp: session đứt giữa chừng (chạy lại build_index,")
        print("    point ID tất định nên an toàn) hoặc corpus/chunking đã đổi.")
        failures.append("số point")

    # --- 2. Schema -------------------------------------------------------
    info = client.get_collection(coll)
    vectors = info.config.params.vectors or {}
    sparse = info.config.params.sparse_vectors or {}
    print("\n[2] SCHEMA")
    if DENSE_VECTOR in vectors:
        dim = vectors[DENSE_VECTOR].size
        dist = vectors[DENSE_VECTOR].distance
        ok = dim == cfg.index.dense_dim
        print(f"    dense '{DENSE_VECTOR}': dim={dim} distance={dist}"
              f"  [{'PASS' if ok else 'FAIL'}]")
        if not ok:
            failures.append(f"dense dim {dim} != {cfg.index.dense_dim}")
    else:
        print(f"    FAIL — không có named vector '{DENSE_VECTOR}'.")
        failures.append("thiếu dense vector")

    if SPARSE_VECTOR in sparse:
        print(f"    sparse '{SPARSE_VECTOR}': có  [PASS]")
    else:
        print(f"    FAIL — không có sparse '{SPARSE_VECTOR}'."
              " retrieval.hybrid=true sẽ không chạy được ở Tuần 3.")
        failures.append("thiếu sparse vector")

    # --- 3. Filter khoa — bất biến DEC-017 -------------------------------
    print("\n[3] FILTER KHOA (DEC-017)")
    per_spec: dict[str, int] = {}
    for spec in cfg.specialties:
        flt = models.Filter(
            must=[models.FieldCondition(key="specialties", match=models.MatchValue(value=spec))]
        )
        per_spec[spec] = client.count(coll, count_filter=flt, exact=True).count
        print(f"    {spec:12s}: {per_spec[spec]:6d} point")

    tong_cong_don = sum(per_spec.values())
    trung = tong_cong_don - n
    print(f"    tổng cộng dồn: {tong_cong_don} · tổng point: {n}"
          f" -> chunk thuộc 2 khoa: {trung}")
    if trung > 0:
        print("    PASS — bài trùng khoa khớp CẢ HAI filter, đúng DEC-017.")
    else:
        print("    FAIL — 0 chunk khớp 2 khoa. Payload nhiều khả năng đang lưu")
        print("    `specialty` số ít thay vì `specialties` list. Tuần 3 sẽ âm thầm")
        print("    đánh rơi 15 bài. Xem src/retrieval/indexer.py:chunk_payload.")
        failures.append("filter 2 khoa")

    if any(v == 0 for v in per_spec.values()):
        print("    FAIL — có khoa 0 point: payload index chưa dựng hoặc tên khoa lệch.")
        failures.append("khoa rỗng")

    # --- 4. Search thử ---------------------------------------------------
    print("\n[4] SEARCH THỬ (chỉ kiểm index dựng xong, KHÔNG kiểm chất lượng)")
    probe = [0.1] * cfg.index.dense_dim
    hits = client.query_points(
        coll, query=probe, using=DENSE_VECTOR, limit=3, with_payload=True
    ).points
    if hits:
        print(f"    PASS — trả {len(hits)} kết quả.")
        for h in hits:
            payload = h.payload or {}
            title = (payload.get("title") or "(không tiêu đề)")[:55]
            print(f"      score={h.score:.4f} · {payload.get('specialties')} · {title}")
    else:
        print("    FAIL — search không trả kết quả nào.")
        failures.append("search rỗng")

    # --- Kết luận ---------------------------------------------------------
    print("\n" + "=" * 60)
    if failures:
        print(f"KẾT LUẬN: FAIL ({len(failures)}) — {', '.join(failures)}")
        return 1
    print("KẾT LUẬN: PASS — collection sẵn sàng cho Tuần 3 (hybrid + rerank).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

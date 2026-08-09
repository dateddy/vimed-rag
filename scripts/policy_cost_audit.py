"""
Chính sách gán khoa: đo ĐỘ CHÍNH XÁC KẾT NẠP và CHI PHÍ INDEX.
================================================================
`policy_audit.py` trả lời "bao nhiêu bài" và "trùng khoa bao nhiêu %".
Session 4 phát hiện cả hai cột đó đều KHÔNG đủ để chốt chính sách:

1. `both%` bão hoà quá sớm. Từ ngưỡng >=15 nó đã xuống 2.1% — nhìn như corpus
   đã sạch — trong khi 80% bài `tim_mach` vẫn lọt vào chỉ nhờ đếm keyword
   trong thân bài. Giảm `both%` KHÔNG có nghĩa là bài được gán đúng khoa.

2. Không cột nào nói corpus có nhét vừa Qdrant Cloud free 1GB không, mà Tuần 2
   phải index HAI collection (chunk 256 + 512, DEC-004).

Script này bổ sung 2 phép đo đó.

TITLE-HIT — proxy độ chính xác kết nạp:
    tỉ lệ bài được gán khoa X mà keyword của X nằm ở TIÊU ĐỀ.
    Bài nói về tăng huyết áp gần như luôn có từ đó ở tiêu đề; bài "Nho khô có
    tốt cho bạn không?" thì không, dù nhắc cholesterol 13 lần. Không hoàn hảo
    (bài đúng khoa vẫn có thể có tiêu đề ẩn dụ) nhưng đo được và tái lập được.

KẾT QUẢ SESSION 4 → DEC-016 chốt "TITLE hoặc >=25":
    - >=8  (khuyến nghị cũ): title-hit 19%, riêng tim_mach 9% → loại
    - >=25 (đã chốt):        title-hit 61%, cân 2 khoa 727/698, storage ~8%
    - chính sách cũ "có mặt là tính": 171k vector = 89% free tier → không deploy được

CHẠY:
  # cần HF_TOKEN vì corpus là dataset gated. ~2-3 phút.
  python scripts/policy_cost_audit.py

KHÔNG được import bởi `src/` hay `tests/` — script chạy tay, tải dataset thật.
Tên file cố ý KHÔNG chứa `test` để pytest không bao giờ thu thập nhầm.
"""

import importlib.util
import random
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_GATE = Path(__file__).resolve().parent / "gate0_data_check.py"
_spec = importlib.util.spec_from_file_location("gate0", _GATE)
g0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g0)

from datasets import load_dataset  # noqa: E402 — sau khi nạp gate script

# bge-m3 dense; float32. Sparse vector + index overhead CHƯA tính → số thật cao hơn.
DENSE_DIM = 1024
BYTES_PER_FLOAT = 4
QDRANT_FREE_BYTES = 1024 ** 3
CHUNK_CONFIGS = ((512, 50), (256, 50))  # DEC-004: phải index cả hai

print("Đang tải corpus...")
ds = load_dataset(g0.CORPUS_DATASET, split=g0.CORPUS_SPLIT)

KW = g0.SPECIALTY_KEYWORDS
SPECS = list(KW)
pats = {
    s: [re.compile(r"(?<!\w)" + re.escape(k) + r"(?!\w)") for k in kws]
    for s, kws in KW.items()
}

arts = []
seen = set()
for row in ds:
    title = g0.clean_article(str(row.get("title", "")))
    body = g0.clean_article(str(row.get("content", "")))
    full = f"{title} {body}"
    if len(full) < g0.MIN_ARTICLE_CHARS:
        continue
    key = full[:200]
    if key in seen:
        continue
    seen.add(key)
    n_title = g0.normalize_text(title)
    n_full = g0.normalize_text(full)
    arts.append({
        "title": title,
        "words": len(full.split()),
        "chars": len(full),
        "counts": {s: sum(len(p.findall(n_full)) for p in ps) for s, ps in pats.items()},
        "in_title": {s: any(p.search(n_title) for p in ps) for s, ps in pats.items()},
    })

print(f"Tổng bài sau clean + dedup: {len(arts)}\n")


def n_chunks(words: int, size: int, overlap: int) -> int:
    """Đếm chunk theo ĐÚNG thuật toán của `src/data/chunker.chunk_text`.

    Chunker của repo tách token bằng khoảng trắng (`text.split()`), không dùng
    tokenizer bge-m3 — nên đếm bằng số từ là khớp với code thật.
    """
    if words <= 0:
        return 0
    step = size - overlap
    n, start = 0, 0
    while start < words:
        n += 1
        if start + size >= words:
            break
        start += step
    return n


def dominant(c, ratio=2.0, floor=3):
    best = max(SPECS, key=lambda s: c[s])
    if c[best] < floor:
        return []
    return [best] + [s for s in SPECS
                     if s != best and c[s] >= c[best] / ratio and c[s] >= floor]


def title_or(k):
    return lambda a: [s for s in SPECS if a["in_title"][s] or a["counts"][s] >= k]


POLICIES = {
    "có mặt là tính (cũ)": lambda a: [s for s in SPECS if a["counts"][s] > 0],
    "khoa trội (>=3, 1/2)": lambda a: dominant(a["counts"]),
    "TITLE thuần": lambda a: [s for s in SPECS if a["in_title"][s]],
    "TITLE hoặc >=8": title_or(8),
    "TITLE hoặc >=12": title_or(12),
    "TITLE hoặc >=15": title_or(15),
    "TITLE hoặc >=20": title_or(20),
    "TITLE hoặc >=25  <-- CHỐT": title_or(25),
    "TITLE hoặc >=30": title_or(30),
    "TITLE hoặc >=40": title_or(40),
}

print("PHẦN 1 — độ chính xác kết nạp")
print("(xx%) = tỉ lệ bài được gán có keyword ở TITLE. both% = trùng cả 2 khoa.\n")
hdr = "  ".join(f"{s[:10]:>12s}" for s in SPECS)
print(f"{'chính sách':28s} {hdr}   {'tổng':>6s} {'both':>6s} {'title-hit':>10s}")
print("-" * 96)

for name, fn in POLICIES.items():
    n = {s: 0 for s in SPECS}
    hit = {s: 0 for s in SPECS}
    both = any_ = 0
    for a in arts:
        tags = fn(a)
        for s in tags:
            n[s] += 1
            if a["in_title"][s]:
                hit[s] += 1
        both += len(tags) > 1
        any_ += bool(tags)
    tot = sum(n.values()) or 1
    cells = "  ".join(f"{n[s]:6d}({hit[s] / (n[s] or 1):3.0%})" for s in SPECS)
    gate = "PASS" if all(n[s] >= g0.MIN_ARTICLES_PER_SPECIALTY for s in SPECS) else "FAIL"
    print(f"{name:28s} {cells}   {any_:6d} {both / (any_ or 1):5.1%} "
          f"{sum(hit.values()) / tot:9.1%}  [{gate}]")

print("\n\nPHẦN 2 — chi phí index (Qdrant Cloud free = 1GB, phải chứa CẢ 2 collection)\n")
print(f"{'chính sách':28s} {'bài':>6s} {'chunk512':>9s} {'chunk256':>9s} "
      f"{'vector':>8s} {'dense':>7s} {'+payload':>9s} {'% free':>7s}")
print("-" * 96)

for name, fn in POLICIES.items():
    sel = [a for a in arts if fn(a)]
    counts = [sum(n_chunks(a["words"], sz, ov) for a in sel) for sz, ov in CHUNK_CONFIGS]
    vec = sum(counts)
    dense = vec * DENSE_DIM * BYTES_PER_FLOAT
    payload = sum(a["chars"] for a in sel) * sum(sz / (sz - ov) for sz, ov in CHUNK_CONFIGS)
    total = dense + payload
    pct = total / QDRANT_FREE_BYTES
    flag = "VỪA" if pct < 0.75 else ("SÁT" if pct < 1.0 else "TRÀN")
    print(f"{name:28s} {len(sel):6d} {counts[0]:9d} {counts[1]:9d} {vec:8d} "
          f"{dense / 1e6:6.0f}M {total / 1e6:8.0f}M {pct:6.0%} {flag}")

print("\n(chưa tính sparse vector + index overhead → con số THẬT còn cao hơn)")

print("\n\nPHẦN 3 — soi tiêu đề thật của chính sách đã chốt")
print("[T] = keyword nằm ở tiêu đề. Đọc để bắt bài lọt sai khoa.\n")
random.seed(0)
fn = POLICIES["TITLE hoặc >=25  <-- CHỐT"]
for s in SPECS:
    sel = [a for a in arts if s in fn(a)]
    other = [o for o in SPECS if o != s][0]
    print(f"--- {s} ({len(sel)} bài) — 12 tiêu đề ngẫu nhiên:")
    for a in random.sample(sel, min(12, len(sel))):
        mark = "T" if a["in_title"][s] else " "
        print(f"  [{mark}] {s[:4]}={a['counts'][s]:3d} {other[:4]}={a['counts'][other]:3d}"
              f" | {a['title'][:74]}")
    print()

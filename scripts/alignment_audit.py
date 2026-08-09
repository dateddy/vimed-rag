"""
Siết corpus có phá tiêu chí #3 (alignment) của Gate 0 không?
=============================================================
Gate 0 chạy 2026-08-07 đo alignment trên corpus RỘNG (mọi bài khớp >=1 keyword,
~16.9k bài). Nhưng việc kế tiếp là siết lại chính sách gán khoa — có phương án
cắt corpus đi 16 lần. Câu hỏi bắt buộc phải trả lời TRƯỚC khi chốt:

    thu nhỏ corpus thì đáp án eval có còn nằm trong corpus không?

Nếu không, verdict GO của Gate 0 không còn hiệu lực với corpus mới, và theo
`brain/contracts/gates.md` thì NO-GO #3 là "NGHIÊM TRỌNG, DỪNG".

Script lặp lại ĐÚNG phép đo alignment của `gate0_data_check.py` (cùng TF-IDF,
cùng ngưỡng, cùng seed 42 nên cùng mẫu 30 QA) nhưng chạy trên corpus đã lọc
theo từng chính sách -> so được táo với táo.

KẾT QUẢ PHIÊN 3: cả 4 chính sách đều PASS (thấp nhất 29/30 = 97%, sàn 60%).
=> Được tự do chọn chính sách theo chất lượng tag, không bị Gate 0 trói.
Đây là bằng chứng để trả lời hội đồng nếu bị hỏi về việc thu nhỏ corpus.

CHẠY:
  # cần HF_TOKEN vì corpus là dataset gated. ~2-3 phút.
  python scripts/alignment_audit.py

KHÔNG được import bởi `src/` hay `tests/` — script chạy tay, tải dataset thật.
"""

import importlib.util
import re
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

_GATE = Path(__file__).resolve().parent / "gate0_data_check.py"
_spec = importlib.util.spec_from_file_location("gate0", _GATE)
g0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g0)

from datasets import load_dataset  # noqa: E402 — sau khi nạp gate script
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.metrics.pairwise import cosine_similarity  # noqa: E402

KW = g0.SPECIALTY_KEYWORDS
SPECS = list(KW)
pats = {
    s: [re.compile(r"(?<!\w)" + re.escape(k) + r"(?!\w)") for k in kws]
    for s, kws in KW.items()
}

print("Chuẩn bị corpus...")
ds = load_dataset(g0.CORPUS_DATASET, split=g0.CORPUS_SPLIT)
docs = []
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
    docs.append({
        "norm": n_full,
        "counts": {s: sum(len(p.findall(n_full)) for p in ps) for s, ps in pats.items()},
        "title_hit": {s: any(p.search(n_title) for p in ps) for s, ps in pats.items()},
    })

# Mẫu QA phải GIỐNG HỆT Gate 0 (seed 42) thì mới so sánh được với verdict gốc.
print("Chuẩn bị mẫu QA (seed 42, giống hệt Gate 0)...")
eds = load_dataset(g0.EVAL_DATASET, split=g0.EVAL_SPLIT)
matched_qa = [
    (str(r.get("question", "")), str(r.get("answer", "")))
    for r in eds
    if g0.matched_specialties(f"{r.get('question', '')} {r.get('answer', '')}", KW)
]
rng = np.random.default_rng(42)
idx = rng.choice(
    len(matched_qa),
    size=min(g0.ALIGNMENT_SAMPLE_N, len(matched_qa)),
    replace=False,
)
answers = [g0.normalize_text(matched_qa[i][1]) for i in idx]
print(f"  mẫu {len(answers)} đáp án trên {len(matched_qa)} QA khớp khoa\n")


def dominant(d, ratio=2.0, floor=3):
    c = d["counts"]
    best = max(SPECS, key=lambda s: c[s])
    if c[best] < floor:
        return []
    return [best] + [
        s for s in SPECS
        if s != best and c[s] >= c[best] / ratio and c[s] >= floor
    ]


POLICIES = {
    "A. hiện tại (có mặt là tính)": lambda d: [s for s in SPECS if d["counts"][s] > 0],
    "D. keyword trong TITLE": lambda d: [s for s in SPECS if d["title_hit"][s]],
    "E. TITLE hoặc >=8 lần": lambda d: [
        s for s in SPECS if d["title_hit"][s] or d["counts"][s] >= 8
    ],
    "F. khoa trội (>=3, kia <1/2)": dominant,
    # Chính sách ĐÃ CHỐT cho loader.py — DEC-016. Giữ 4 dòng trên làm đối chứng.
    "== CHỐT: TITLE hoặc >=25 (DEC-016)": lambda d: [
        s for s in SPECS if d["title_hit"][s] or d["counts"][s] >= 25
    ],
}

print(f"{'chính sách':32s} {'#doc':>7s} {'found':>10s} {'median':>8s} {'mean':>7s}  verdict")
print("-" * 80)
for name, fn in POLICIES.items():
    kept = [d["norm"] for d in docs if fn(d)]
    if not kept:
        print(f"{name:32s} {0:7d}   corpus rỗng")
        continue
    vec = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", min_df=1)
    dm = vec.fit_transform(kept)
    am = vec.transform(answers)
    ms = cosine_similarity(am, dm).max(axis=1)
    found = int((ms >= g0.ALIGNMENT_SIM_FLOOR).sum())
    ratio = found / len(ms)
    ok = ratio >= g0.ALIGNMENT_PASS_RATIO
    print(f"{name:32s} {len(kept):7d} {found:3d}/{len(ms):<3d} {ratio:4.0%} "
          f"{np.median(ms):8.3f} {ms.mean():7.3f}  [{'PASS' if ok else 'FAIL'}]")

print(f"\nSàn: max-sim >= {g0.ALIGNMENT_SIM_FLOOR} và "
      f">= {g0.ALIGNMENT_PASS_RATIO:.0%} số QA phải 'tìm thấy' (theo gates.md).")
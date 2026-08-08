"""
So sánh CHÍNH SÁCH gán khoa trên corpus thật.
==============================================
Câu hỏi script này trả lời: làm sao phân biệt "bài NÓI VỀ khoa X" với
"bài chỉ nhắc tới X một lần trong đoạn biến chứng"?

Bối cảnh (Session 3): siết `config/specialties.yaml` KHÔNG làm giảm trùng khoa
(38.7% bài vẫn khớp cả 2). Nguyên nhân là quy tắc "keyword có mặt ở đâu cũng
tính" áp lên bài vinmec dài ~7.8KB — bài tiểu đường luôn có đoạn biến chứng tim
mạch, bài tim mạch luôn liệt kê tiểu đường ở yếu tố nguy cơ. Đó là y học đúng.
Nên biến cần chỉnh là CHÍNH SÁCH, không phải từ vựng.

Script này sinh ra bảng 4 phương án trong `brain/state/STATUS.md`, việc kế
tiếp #1. Chạy lại sau khi đổi keyword hoặc trước khi chốt policy cho `loader.py`.

LƯU Ý ĐỌC KẾT QUẢ: cột `both%` là mục tiêu cần giảm, nhưng đừng tối ưu mù —
phương án TITLE thuần cho both ~1% nhưng corpus tụt còn ~850 bài, mỏng cho
retrieval. Cân với số bài/khoa và với thời gian embed Tuần 2 (ablation chunk
256 vs 512 = phải embed corpus HAI lần, xem DEC-004).

Kiểm tra alignment (Gate 0 tiêu chí #3) có sống sót qua từng chính sách không
thì cần script riêng — phiên 3 đã đo: cả 4 phương án đều PASS.

CHẠY:
  # cần HF_TOKEN vì corpus là dataset gated
  python scripts/policy_audit.py

KHÔNG được import bởi `src/` hay `tests/` — script chạy tay, tải dataset thật.
Tên file cố ý KHÔNG chứa `test` để pytest không bao giờ thu thập nhầm.
"""

import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_GATE = Path(__file__).resolve().parent / "gate0_data_check.py"
_spec = importlib.util.spec_from_file_location("gate0", _GATE)
g0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g0)

from datasets import load_dataset  # noqa: E402 — sau khi nạp gate script

print("Đang tải corpus...")
ds = load_dataset(g0.CORPUS_DATASET, split=g0.CORPUS_SPLIT)

KW = g0.SPECIALTY_KEYWORDS
SPECS = list(KW)
pats = {
    s: [re.compile(r"(?<!\w)" + re.escape(k) + r"(?!\w)") for k in kws]
    for s, kws in KW.items()
}

# Tách title/body vì "keyword nằm ở TITLE" là tín hiệu bài NÓI VỀ chủ đề đó,
# khác hẳn keyword nằm lọt trong đoạn biến chứng ở cuối bài.
rows = []
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
    rows.append((
        {s: sum(len(p.findall(n_full)) for p in ps) for s, ps in pats.items()},
        {s: any(p.search(n_title) for p in ps) for s, ps in pats.items()},
    ))

print(f"Tổng bài sau clean + dedup: {len(rows)}\n")


def report(name, assign_fn):
    tally = Counter()
    for counts, in_title in rows:
        tags = assign_fn(counts, in_title)
        for s in tags:
            tally[s] += 1
        if len(tags) > 1:
            tally["__both__"] += 1
        if tags:
            tally["__any__"] += 1
    both = tally["__both__"]
    any_ = tally["__any__"] or 1
    line = "  ".join(f"{s}={tally[s]:6d}" for s in SPECS)
    ok = all(tally[s] >= g0.MIN_ARTICLES_PER_SPECIALTY for s in SPECS)
    print(f"{name:40s} {line}   both={both:5d} ({both / any_:5.1%})  "
          f"[{'PASS' if ok else 'FAIL'} >={g0.MIN_ARTICLES_PER_SPECIALTY}/khoa]")


def dominant(c, ratio=2.0, floor=3):
    """Gán cho khoa có nhiều keyword nhất; chỉ giữ khoa kia nếu nó bám sát."""
    best = max(SPECS, key=lambda s: c[s])
    if c[best] < floor:
        return []
    return [best] + [
        s for s in SPECS
        if s != best and c[s] >= c[best] / ratio and c[s] >= floor
    ]


report("A. hiện tại: có mặt ở đâu cũng tính",
       lambda c, t: [s for s in SPECS if c[s] > 0])
report("B. keyword xuất hiện >=3 lần",
       lambda c, t: [s for s in SPECS if c[s] >= 3])
report("C. keyword xuất hiện >=5 lần",
       lambda c, t: [s for s in SPECS if c[s] >= 5])
report("D. keyword phải có trong TITLE",
       lambda c, t: [s for s in SPECS if t[s]])
report("E. TITLE hoặc >=8 lần trong body",
       lambda c, t: [s for s in SPECS if t[s] or c[s] >= 8])
report("F. khoa trội (>=3 lần, kia <1/2 thì loại)",
       lambda c, t: dominant(c))
report("G. khoa trội NGHIÊM (>=5, kia <1/3)",
       lambda c, t: dominant(c, ratio=3.0, floor=5))
report("H. TITLE + khoa trội (>=1/2)",
       lambda c, t: [s for s in dominant(c) if t[s]])
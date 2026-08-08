"""
Audit keyword 2 khoa trên corpus thật — keyword nào bắt nhiễu / kéo theo khoa kia.
=================================================================================
Đây là script SINH RA BẰNG CHỨNG cho DEC-010 (siết `config/specialties.yaml`).
Giữ lại để số trong DEC-010 tái lập được, và để chạy lại mỗi khi sửa keyword.

Với mỗi keyword đo:
  df      : số bài chứa keyword
  solo    : số bài mà keyword này là LÝ DO DUY NHẤT bài được gán khoa đó
            -> solo = 0 nghĩa là keyword THỪA, bị cụm ngắn hơn nuốt hoàn toàn
  cross   : trong số bài keyword này bắt, bao nhiêu bài ĐỒNG THỜI thuộc khoa kia
  cross%  : cross / df — càng cao càng kéo nhầm sang khoa kia

CÁCH ĐỌC (bài học Session 3): cross% cao KHÔNG chứng minh keyword sai.
`đái tháo đường` cross 84%, `hba1c` 90% — đều là keyword đặc hiệu tuyệt đối.
Trùng khoa đến từ CHÍNH SÁCH "keyword có mặt ở đâu cũng tính" áp lên bài dài
~7.8KB, không đến từ từ vựng. Muốn so chính sách -> dùng `policy_audit.py`.
Dùng cột `solo` + đọc title mẫu để bắt keyword sai, đừng dùng cross%.

CHẠY:
  # cần HF_TOKEN vì corpus là dataset gated
  python scripts/kw_audit.py

KHÔNG được import bởi `src/` hay `tests/` — script chạy tay, tải dataset thật.
"""

import importlib.util
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Dùng lại CONFIG + hàm clean/normalize của gate script -> một nguồn sự thật,
# không copy logic sang đây rồi trôi khác nhau.
_GATE = Path(__file__).resolve().parent / "gate0_data_check.py"
_spec = importlib.util.spec_from_file_location("gate0", _GATE)
g0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g0)

from datasets import load_dataset  # noqa: E402 — sau khi nạp gate script

print("Đang tải corpus...")
ds = load_dataset(g0.CORPUS_DATASET, split=g0.CORPUS_SPLIT)

KW = g0.SPECIALTY_KEYWORDS
patterns = {
    spec_name: [(kw, re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)")) for kw in kws]
    for spec_name, kws in KW.items()
}

# docs_hits[i] = {khoa: set(keyword đã khớp)} cho từng bài sau clean + dedup
docs_hits = []
seen = set()
for row in ds:
    raw = g0.get_article_text(row, g0.CORPUS_TEXT_COL, g0.CORPUS_TEXT_COLS)
    text = g0.clean_article(raw)
    if len(text) < g0.MIN_ARTICLE_CHARS:
        continue
    key = text[:200]
    if key in seen:
        continue
    seen.add(key)
    norm = g0.normalize_text(text)
    hit = {}
    for spec_name, pats in patterns.items():
        found = {kw for kw, p in pats if p.search(norm)}
        if found:
            hit[spec_name] = found
    if hit:
        docs_hits.append(hit)

print(f"Tổng bài khớp >=1 khoa: {len(docs_hits)}")
both = sum(1 for h in docs_hits if len(h) > 1)
print(f"Bài khớp CẢ 2 khoa   : {both}  ({both / len(docs_hits):.1%})\n")

for spec_name in KW:
    other = [s for s in KW if s != spec_name][0]
    df = defaultdict(int)
    solo = defaultdict(int)
    cross = defaultdict(int)
    for h in docs_hits:
        if spec_name not in h:
            continue
        kws = h[spec_name]
        is_cross = other in h
        for kw in kws:
            df[kw] += 1
            if is_cross:
                cross[kw] += 1
        if len(kws) == 1:
            solo[next(iter(kws))] += 1

    print("=" * 78)
    print(f"KHOA: {spec_name}   (tổng {sum(1 for h in docs_hits if spec_name in h)} bài)")
    print("=" * 78)
    print(f"{'keyword':24s} {'df':>7s} {'solo':>7s} {'cross':>7s} {'cross%':>8s}")
    for kw in sorted(KW[spec_name], key=lambda k: -df[k]):
        pct = cross[kw] / df[kw] if df[kw] else 0
        # solo=0 có HAI nguyên nhân khác hẳn nhau, đừng xoá nhầm:
        #  - bị cụm khác nuốt về TỪ VỰNG -> thừa thật, xoá được với MỌI chính sách
        #  - chỉ trùng hợp trong corpus này -> vẫn cần cho chính sách TITLE
        #    (VD "sốc tim": bài nào cũng nhắc kèm "bệnh tim", nhưng title
        #     "Sốc tim khi tập thể thao" thì chỉ mình nó bắt được)
        eaten = [
            o for o in KW[spec_name]
            if o != kw and re.search(r"(?<!\w)" + re.escape(o) + r"(?!\w)", kw)
        ]
        if df[kw] and solo[kw] == 0:
            flag = f"  <-- THỪA, bị {eaten[0]!r} nuốt" if eaten else "  <-- solo=0 do corpus, GIỮ"
        else:
            flag = ""
        print(f"{kw:24s} {df[kw]:7d} {solo[kw]:7d} {cross[kw]:7d} {pct:7.0%}{flag}")
    print()
"""
Thống kê corpus → `docs/corpus-stats.md`.
==========================================
Sinh artifact mô tả corpus để hội đồng không phải tin trí nhớ. Mọi con số
STATUS đang ghi rải rác (1.410 bài, 2,04 triệu từ, byline 12,4%, cân 2 khoa)
được tính lại **từ chính file đang dùng** và đóng vào một chỗ.

⚠️ Đọc `data/processed/corpus.jsonl` (artifact local), **KHÔNG** tải dataset
gated qua mạng như `policy_cost_audit.py`. Hai lý do: chạy được khi không có
`HF_TOKEN`, và nó mô tả đúng corpus ĐÃ INDEX chứ không phải dataset thượng
nguồn — hai thứ đó lệch nhau kể từ DEC-016.

⚠️ `corpus.jsonl` bị gitignore. Nếu thiếu, chạy `python scripts/run_ingestion.py`
(cần `HF_TOKEN`); vân tay SHA-256 in ra dưới đây để đối chiếu với nhãn test set.

CHẠY
----
  python scripts/corpus_stats.py
"""

from __future__ import annotations

import collections
import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.cleaner import BYLINE  # noqa: E402

CORPUS = ROOT / "data" / "processed" / "corpus.jsonl"
OUT = ROOT / "docs" / "corpus-stats.md"


def pct(n: int, total: int) -> str:
    return f"{100 * n / total:.1f}%" if total else "—"


def main() -> None:
    if not CORPUS.exists():
        sys.exit(
            f"!! Thiếu {CORPUS.relative_to(ROOT)} (gitignore). "
            f"Chạy `python scripts/run_ingestion.py` — cần HF_TOKEN."
        )

    h = hashlib.sha256()
    rows = []
    with CORPUS.open("rb") as fh:
        for line in fh:
            h.update(line)
            rows.append(json.loads(line))

    n = len(rows)
    words = [len(r["text"].split()) for r in rows]
    words_sorted = sorted(words)
    chars = [len(r["text"]) for r in rows]
    byline = sum(1 for r in rows if BYLINE.search(r["text"]))

    per_spec: collections.Counter = collections.Counter()
    for r in rows:
        for s in r.get("specialties") or []:
            per_spec[s] += 1
    both = sum(1 for r in rows if len(r.get("specialties") or []) > 1)

    # title-hit: keyword của khoa có nằm ở TIÊU ĐỀ không — proxy độ chính xác
    # kết nạp (DEC-016). `both%` là chỉ số đánh lừa, đừng dùng thay.
    specialties = yaml.safe_load(
        (ROOT / "config" / "specialties.yaml").read_text(encoding="utf-8")
    )
    title_hit: dict[str, int] = {}
    for spec, kws in specialties.items():
        low = [k.lower() for k in kws]
        title_hit[spec] = sum(
            1 for r in rows
            if spec in (r.get("specialties") or [])
            and any(k in (r.get("title") or "").lower() for k in low)
        )

    md = [
        "# Corpus — thống kê",
        "",
        "> Sinh bằng `python scripts/corpus_stats.py` từ "
        "`data/processed/corpus.jsonl`.",
        "> Không tải dataset qua mạng; mô tả đúng corpus **đã index**, không "
        "phải dataset thượng nguồn (hai thứ lệch nhau từ DEC-016).",
        "",
        f"**Vân tay:** `sha256={h.hexdigest()[:16]}` · **{n} bài**",
        "",
        "## Quy mô",
        "",
        "| | |",
        "|---|---|",
        f"| Số bài (phân biệt) | **{n}** |",
        f"| Tổng số từ | **{sum(words):,}** |",
        f"| Số từ / bài — trung vị | {words_sorted[n // 2]:,} |",
        f"| Số từ / bài — min · max | {min(words):,} · {max(words):,} |",
        f"| Tổng ký tự | {sum(chars):,} |",
        "",
        "## Phân bố theo khoa (DEC-016: TIÊU ĐỀ hoặc >=25 lần)",
        "",
        "`title-hit` = tỉ lệ bài được gán khoa X mà keyword của X nằm ở **tiêu "
        "đề** — proxy độ chính xác kết nạp. `both%` là chỉ số đánh lừa "
        "(bão hoà sớm), đừng dùng thay.",
        "",
        "| Khoa | Số bài | title-hit |",
        "|---|---|---|",
    ]
    for spec, cnt in sorted(per_spec.items(), key=lambda kv: -kv[1]):
        md.append(f"| `{spec}` | {cnt} | {pct(title_hit.get(spec, 0), cnt)} |")
    md += [
        f"| **cộng dồn** | **{sum(per_spec.values())}** | |",
        f"| thuộc **cả hai** khoa | {both} ({pct(both, n)}) | |",
        "",
        f"> Cộng dồn ({sum(per_spec.values())}) > số bài phân biệt ({n}) vì "
        f"{both} bài thuộc cả hai khoa và bị đếm hai lần. **Cả hai con số đều "
        f"đúng** — DEC-016 ghi theo kiểu cộng dồn.",
        "",
        "## Byline",
        "",
        f"**{byline}/{n} bài ({pct(byline, n)})** mở đầu bằng *\"Bài viết được "
        "tư vấn chuyên môn bởi… Vinmec…\"*.",
        "",
        "⚠️ Byline mang **tên bác sĩ + tên bệnh viện**. Corpus trong Qdrant "
        "**vẫn còn nguyên** byline — DEC-020 quyết không chạy lại ingestion chỉ "
        "vì nó. Phép cắt nằm ở `src/data/cleaner.strip_byline` và áp ở tầng "
        "**đọc ra** (soạn test set, dựng prompt). Mọi đường mới đọc chunk ra "
        "đều phải tự gọi nó, không có tầng nào cắt hộ.",
        "",
    ]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"[out] {OUT.relative_to(ROOT)} — {n} bài · sha256={h.hexdigest()[:16]}")
    print(f"      byline {byline}/{n} ({pct(byline, n)}) · "
          f"khoa {dict(per_spec)} · cả hai {both}")


if __name__ == "__main__":
    main()

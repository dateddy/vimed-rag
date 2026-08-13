"""
Soi chunk BẰNG MẮT trước khi embed (Tuần 2).
============================================
Đây là lần cuối sửa chunking còn rẻ. Sai mà phát hiện sau khi embed là phải
embed lại CẢ HAI collection (256 + 512, DEC-004).

Script làm 3 việc, không chạm model và không chạm mạng — chỉ đọc
`data/processed/corpus.jsonl` do `run_ingestion.py` sinh ra:

1. THỐNG KÊ  — số chunk, phân phối độ dài, ước lượng chi phí Qdrant Cloud.
2. CHẤM TỰ ĐỘNG — 4 cờ đo được bằng máy trên TOÀN BỘ chunk:
     mid-sentence  : chunk kết thúc giữa câu (không phải . ! ? …)
     html          : còn sót thẻ / entity / URL
     boilerplate   : dính đuôi quảng cáo Vinmec (hotline, đặt lịch, MyVinmec…)
     low-alpha     : ít chữ, nhiều số/ký hiệu → nghi menu, bảng, danh mục
3. XUẤT MẪU  — N chunk lấy ngẫu nhiên có seed cố định, ghi ra file markdown
   kèm ĐƯỜNG CẮT (đuôi chunk trước + đầu chunk sau) để soi bằng mắt.

Cờ tự động chỉ để KHOANH VÙNG. Quyết định cuối vẫn phải nhìn tận mắt — cờ
`mid-sentence` sẽ đỏ gần như 100% vì chunker hiện tại là cửa sổ trượt thuần,
điều cần biết là cắt như thế có làm chunk MẤT NGHĨA hay không.

CHẠY:
    python scripts/chunk_audit.py                  # size từ config (512)
    python scripts/chunk_audit.py --size 256       # ablation DEC-004
    python scripts/chunk_audit.py --n 30 --seed 7  # đổi mẫu soi
    python scripts/chunk_audit.py --specialty tim_mach

Không cần HF_TOKEN (đọc file local). KHÔNG được import bởi `src/` hay `tests/`.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import load_config  # noqa: E402
from src.data.chunker import chunk_text  # noqa: E402
from src.data.loader import load_documents  # noqa: E402

# --- Ước lượng chi phí Qdrant: bge-m3 dense, float32. -------------------------
# Sparse vector + HNSW index + payload CHƯA tính → số thật cao hơn ~1.5-2x.
DENSE_DIM = 1024
BYTES_PER_FLOAT = 4
QDRANT_FREE_BYTES = 1024**3

# --- Cờ tự động ---------------------------------------------------------------
_SENT_END = tuple(".!?…\"'”’)")
_HTML_RE = re.compile(r"<[^>]{1,80}>|&[a-z]+;|&#\d+;|https?://|www\.")

# Đuôi bài Vinmec. Chunk toàn những cụm này = rác, không mang thông tin y tế.
_BOILERPLATE = (
    "đặt lịch khám",
    "hotline",
    "đặt lịch trực tiếp",
    "myvinmec",
    "tải ứng dụng",
    "quý khách vui lòng bấm số",
    "xem thêm",
    "bài viết tham khảo nguồn",
    "nguồn tham khảo",
    "bài viết này được viết cho người đọc",
    "để được tư vấn trực tiếp",
    "vui lòng liên hệ",
    "đăng ký khám",
)


def _tokens(text: str) -> list[str]:
    """Cùng cách tách token với chunker (khoảng trắng) — để số liệu khớp nhau."""
    return text.split()


def ends_mid_sentence(chunk: str) -> bool:
    """Chunk có kết thúc giữa câu không?"""
    stripped = chunk.rstrip()
    return bool(stripped) and not stripped.endswith(_SENT_END)


def starts_mid_sentence(chunk: str) -> bool:
    """Chunk có bắt đầu giữa câu không? (token đầu không viết hoa / không phải số)"""
    stripped = chunk.lstrip()
    if not stripped:
        return False
    first = stripped[0]
    return not (first.isupper() or first.isdigit())


def html_residue(chunk: str) -> list[str]:
    """Trả về các mẩu HTML/URL còn sót (rỗng nếu sạch)."""
    return _HTML_RE.findall(chunk)[:5]


def boilerplate_hits(chunk: str) -> list[str]:
    """Các cụm đuôi bài quảng cáo xuất hiện trong chunk."""
    low = chunk.lower()
    return [p for p in _BOILERPLATE if p in low]


def alpha_ratio(chunk: str) -> float:
    """Tỉ lệ ký tự là CHỮ (kể cả chữ có dấu). Thấp → nghi bảng/menu/danh mục."""
    if not chunk:
        return 0.0
    letters = sum(1 for c in chunk if unicodedata.category(c).startswith("L"))
    return letters / len(chunk)


def boilerplate_density(chunk: str) -> float:
    """Ước lượng phần chunk bị đuôi quảng cáo chiếm (theo số ký tự khớp)."""
    low = chunk.lower()
    covered = sum(len(p) * low.count(p) for p in _BOILERPLATE)
    return covered / len(chunk) if chunk else 0.0


def pct(n: int, total: int) -> str:
    return f"{n / total:.1%}" if total else "n/a"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=None, help="token/chunk (mặc định: config)")
    ap.add_argument("--overlap", type=int, default=None, help="token chồng lấn (mặc định: config)")
    ap.add_argument("--n", type=int, default=25, help="số chunk xuất ra soi bằng mắt")
    ap.add_argument("--seed", type=int, default=42, help="seed lấy mẫu (cố định để tái lập)")
    ap.add_argument("--specialty", default=None, help="chỉ soi 1 khoa (vd tim_mach)")
    ap.add_argument("--corpus", type=Path, default=None, help="đường dẫn corpus.jsonl")
    ap.add_argument("--out", type=Path, default=None, help="file markdown mẫu soi")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()
    size = args.size or cfg.chunking.size
    overlap = args.overlap if args.overlap is not None else cfg.chunking.overlap

    corpus = args.corpus or Path(cfg.data.processed_dir) / "corpus.jsonl"
    if not corpus.exists():
        print(f"!! Không thấy {corpus}. Chạy `python scripts/run_ingestion.py` trước.")
        return 1

    docs = load_documents(corpus)
    if args.specialty:
        docs = [d for d in docs if args.specialty in d.specialties]
        if not docs:
            print(f"!! Không bài nào thuộc khoa '{args.specialty}'.")
            return 1

    print(f"Corpus  : {corpus} ({len(docs)} bài)")
    print(f"Chunking: size={size} overlap={overlap} (step={size - overlap})")
    if args.specialty:
        print(f"Lọc khoa: {args.specialty}")

    # --- Chunk toàn corpus, giữ lại đủ ngữ cảnh để in đường cắt ---------------
    # records: (doc_idx, chunk_idx, tổng chunk của bài, chunk)
    records: list[tuple[int, int, int, str]] = []
    for di, doc in enumerate(docs):
        chunks = chunk_text(doc.text, size, overlap)
        for ci, ch in enumerate(chunks):
            records.append((di, ci, len(chunks), ch))

    total = len(records)
    if not total:
        print("!! Không sinh được chunk nào.")
        return 1

    lengths = sorted(len(_tokens(r[3])) for r in records)
    doc_words = [len(_tokens(d.text)) for d in docs]
    single = sum(1 for r in records if r[2] == 1)

    print("\n--- THỐNG KÊ ---")
    print(f"  tổng chunk        : {total}")
    print(f"  chunk/bài         : trung bình {total / len(docs):.1f}"
          f" · max {max(r[2] for r in records)}")
    print(f"  bài chỉ 1 chunk   : {single} ({pct(single, total)} tổng chunk)")
    print(f"  độ dài chunk (token): min {lengths[0]} · p50 {lengths[len(lengths) // 2]}"
          f" · max {lengths[-1]}")
    print(f"  bài (token)       : trung bình {sum(doc_words) / len(doc_words):.0f}"
          f" · max {max(doc_words)}")

    # Chunk cuối của bài ngắn hơn size → đuôi vụn, embed vào gần như vô dụng.
    runts = sum(1 for r in records if len(_tokens(r[3])) < size * 0.2 and r[2] > 1)
    print(f"  đuôi vụn (<20% size, bài nhiều chunk): {runts} ({pct(runts, total)})")

    dense_bytes = total * DENSE_DIM * BYTES_PER_FLOAT
    print(f"  vector dense       : {dense_bytes / 1024**2:.1f} MB"
          f" = {dense_bytes / QDRANT_FREE_BYTES:.1%} free 1GB (CHƯA tính sparse+payload)")

    # --- Chấm tự động trên TOÀN BỘ chunk -------------------------------------
    flag_mid_end = [r for r in records if ends_mid_sentence(r[3])]
    flag_mid_start = [r for r in records if starts_mid_sentence(r[3])]
    flag_html = [r for r in records if html_residue(r[3])]
    flag_boiler = [r for r in records if boilerplate_density(r[3]) > 0.25]
    flag_boiler_any = [r for r in records if boilerplate_hits(r[3])]
    flag_alpha = [r for r in records if alpha_ratio(r[3]) < 0.55]

    print("\n--- CỜ TỰ ĐỘNG (toàn corpus) ---")
    print(f"  kết thúc giữa câu : {len(flag_mid_end):6d}  {pct(len(flag_mid_end), total)}")
    print(f"  bắt đầu giữa câu  : {len(flag_mid_start):6d}  {pct(len(flag_mid_start), total)}")
    print(f"  sót HTML/URL      : {len(flag_html):6d}  {pct(len(flag_html), total)}")
    print(f"  dính boilerplate  : {len(flag_boiler_any):6d}  {pct(len(flag_boiler_any), total)}"
          f"   (trong đó >25% chunk là boilerplate: {len(flag_boiler)})")
    print(f"  ít chữ (<55% alpha): {len(flag_alpha):6d}  {pct(len(flag_alpha), total)}")

    # --- Xuất mẫu soi bằng mắt ------------------------------------------------
    rng = random.Random(args.seed)
    # Ưu tiên chunk KHÔNG phải chunk duy nhất của bài — chỉ chunk có hàng xóm
    # mới soi được đường cắt.
    cuttable = [i for i, r in enumerate(records) if r[2] > 1]
    pool = cuttable or list(range(total))
    picked = sorted(rng.sample(pool, min(args.n, len(pool))))

    out = args.out or Path(cfg.data.processed_dir) / f"chunk-audit-{size}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        f"# Soi chunk — size={size} overlap={overlap}",
        "",
        f"Corpus `{corpus}` · {len(docs)} bài · {total} chunk · mẫu {len(picked)}"
        f" (seed {args.seed})",
        "",
        "Với mỗi mẫu: **ĐUÔI chunk trước → ĐẦU chunk này** là đường cắt cần soi.",
        "",
        "Checklist mỗi chunk: (1) cắt có làm mất nghĩa không · (2) còn rác HTML"
        " không · (3) có phải toàn menu/footer không · (4) đọc riêng chunk này"
        " có trả lời được câu hỏi y tế nào không.",
        "",
        "---",
        "",
    ]

    for rank, idx in enumerate(picked, 1):
        di, ci, nch, ch = records[idx]
        doc = docs[di]
        flags = []
        if ends_mid_sentence(ch):
            flags.append("cắt-cuối-câu")
        if starts_mid_sentence(ch):
            flags.append("cắt-đầu-câu")
        if html_residue(ch):
            flags.append(f"HTML:{html_residue(ch)}")
        hits = boilerplate_hits(ch)
        if hits:
            flags.append(f"boilerplate:{hits}")
        ar = alpha_ratio(ch)
        if ar < 0.55:
            flags.append(f"alpha={ar:.2f}")

        prev_tail = ""
        if ci > 0:
            prev = records[idx - 1][3]
            prev_tail = " ".join(_tokens(prev)[-20:])

        lines += [
            f"## [{rank}] chunk {ci + 1}/{nch} — {doc.title or '(không tiêu đề)'}",
            "",
            f"`doc_id={doc.doc_id}` · khoa `{', '.join(doc.specialties)}`"
            f" · {len(_tokens(ch))} token",
            "",
            f"**Cờ:** {' · '.join(flags) if flags else 'sạch'}",
            "",
        ]
        if prev_tail:
            lines += [f"> …ĐUÔI CHUNK TRƯỚC: …{prev_tail}", "", "**↓ ĐƯỜNG CẮT ↓**", ""]
        else:
            lines += ["> (chunk đầu bài — không có đường cắt phía trước)", ""]
        lines += ["```", ch, "```", "", "---", ""]

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nĐã ghi {len(picked)} chunk mẫu -> {out}")
    print("Mở file đó ra và soi. Cờ tự động chỉ khoanh vùng, mắt mới quyết.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

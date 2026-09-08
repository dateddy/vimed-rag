"""
Phương án B — ĐO độ lệch văn phong (DEC-029, DEC-055).
=======================================================
Chạy cùng 21 câu nhóm E ở HAI văn phong và so từng cặp:

    sách giáo khoa:  "Đái tháo đường thể MODY là gì?"
    giọng bệnh nhân: "Bệnh tiểu đường MODY là bệnh gì vậy ạ?"

Đây là **đối chứng cặp**: cùng nhu cầu thông tin, cùng bài vàng, chỉ khác cách
nói. Nên khác biệt quan sát được quy về đúng văn phong, không lẫn với "câu này
khó hơn câu kia" — mạnh hơn hẳn so với đem hai tập câu khác nhau ra so.

TRẢ LỜI ĐÚNG MỘT CÂU: **hệ thống bám nội dung, hay bám cách diễn đạt?**
DEC-051 đã chứng minh trần coverage là trần của THANG ĐIỂM (3/4 câu hỏng đã lấy
đúng bài vàng rồi bị chấm âm). Nếu đổi văn phong làm điểm tụt trong khi bài vàng
vẫn ở đúng hạng cũ, đó là bằng chứng trực tiếp cho cùng một cơ chế hỏng.

⚠️ Số của bản "sách giáo khoa" lấy từ CÙNG một lượt chạy, không lấy lại từ
`calibration_scores.json`: hai lượt chạy khác nhau có thể lệch do RRF hoà điểm
(DEC-040) và do cache. Đối chứng cặp thì phải cùng điều kiện.

CHẠY
----
  python scripts/eval_register_shift.py
⚠️ 42 lượt truy hồi + ~210 cặp rerank MỚI (bản sách giáo khoa đã có cache).
   Ước 10-30 phút tuỳ tải máy. Có cache đĩa nên chạy lại gần như free.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.config import load_config  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402

# Tái dùng ĐÚNG phần chấm điểm của eval_retrieval thay vì chép lại: cùng bài học
# chống trôi của DEC-044/045/046. Bản sao thứ hai của `per_doc_best` là bảng này
# và bảng T3.4 nói hai chuyện khác nhau mà không gì bắt được.
from eval_retrieval import (  # noqa: E402
    CACHE_PATH,
    LogitCache,
    make_embedder,
    make_reranker,
    per_doc_best,
)

PATIENT = ROOT / "data" / "testset_e_patient.jsonl"
OUT_MD = ROOT / "docs" / "register-shift.md"

# Ngưỡng đang dùng, quy về logit để so với max_logit (DEC-052).
# sigmoid(x) = 0.919  ->  x = ln(0.919/0.081)
THRESHOLD_LOGIT = math.log(0.919 / (1 - 0.919))


def sign_test(diffs: list[float]) -> tuple[int, int, float]:
    """Kiểm định dấu (nhị thức chính xác, hai phía). Trả (âm, dương, p).

    Dùng kiểm định dấu chứ không dùng t-test: n=21, phân bố điểm nhóm E **lưỡng
    cực** (DEC-051) nên giả định chuẩn của t-test sai ngay từ đầu. Kiểm định dấu
    không giả định gì về phân bố — đổi lại nó yếu hơn, và đó là cái giá đúng
    phải trả khi không biết dạng phân bố.
    """
    neg = sum(1 for d in diffs if d < 0)
    pos = sum(1 for d in diffs if d > 0)
    n = neg + pos              # bỏ qua các cặp bằng nhau
    if n == 0:
        return neg, pos, 1.0
    k = min(neg, pos)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return neg, pos, min(1.0, 2 * tail)


def main() -> None:
    if not PATIENT.exists():
        sys.exit(
            f"!! Chưa có {PATIENT.relative_to(ROOT)}. Sinh bằng:\n"
            f"   python scripts/build_testset_e_patient.py"
        )
    rows = [json.loads(l) for l in PATIENT.open(encoding="utf-8")]
    not_eyeballed = [r["id"] for r in rows if not r.get("eyeballed")]
    if not_eyeballed:
        print(f"⚠️  {len(not_eyeballed)} câu CHƯA SOI TAY ({not_eyeballed[:3]}…). "
              f"Số đo dưới đây chỉ là sơ bộ — soi "
              f"`data/processed/testset_e_patient_candidates.md` rồi đặt "
              f"`eyeballed: true` trước khi đưa vào báo cáo.\n")

    cfg = load_config()
    size = cfg.chunking.size
    ml = cfg.retrieval.rerank_max_length
    top_k = cfg.retrieval.top_k_dense
    coll = collection_name(cfg.qdrant.collection, size)

    # Hai "câu hỏi" cho mỗi id: bản gốc giữ qid cũ (dùng lại cache), bản bệnh
    # nhân mang hậu tố `p` để KHÔNG đụng cache của bản gốc.
    questions = []
    for r in rows:
        questions.append({"id": r["id"], "user_input": r["user_input"],
                          "group": "E",
                          "reference_context_ids": r["reference_context_ids"]})
        questions.append({"id": r["id"] + "p",
                          "user_input": r["user_input_patient"], "group": "E",
                          "reference_context_ids": r["reference_context_ids"]})

    print(f"{len(rows)} cặp câu · {coll} · top_k_dense={top_k} · max_length={ml}")
    embedder = make_embedder(cfg)
    embedder.embed_hybrid(["khởi động"])

    from qdrant_client import QdrantClient
    from src.retrieval.retriever import HybridRetriever

    client = QdrantClient(
        url=cfg.qdrant.url, api_key=cfg.qdrant.api_key or None, timeout=60
    )
    client.count(coll, exact=False)

    print("\n[1] TRUY HỒI")
    r = HybridRetriever(cfg, embedder, collection=coll, mode="hybrid",
                        client=client)
    pools = {(size, "hybrid"): {
        q["id"]: r.search(q["user_input"], limit=top_k) for q in questions
    }}

    print("[2] RERANK (bản gốc đã có cache; bản bệnh nhân phải chấm mới)")
    cache = LogitCache(CACHE_PATH)
    reranker = make_reranker(cfg, ml)
    from eval_retrieval import rerank_all  # noqa: PLC0415
    rerank_all(reranker, cache, pools, questions, ml)

    per_doc = per_doc_best(pools, cache, [size], ["hybrid"], ml)
    gold = {q["id"]: set(q["reference_context_ids"]) for q in questions}

    def score_and_rank(qid: str):
        d = per_doc.get(qid) or {}
        if not d:
            return None, None
        order = sorted(d.items(), key=lambda t: -t[1])
        rank = next((i for i, (dd, _) in enumerate(order, 1)
                     if dd in gold[qid]), None)
        return max(d.values()), rank

    print("\n[3] SO TỪNG CẶP")
    out, diffs = [], []
    for r0 in rows:
        s_txt, k_txt = score_and_rank(r0["id"])
        s_pat, k_pat = score_and_rank(r0["id"] + "p")
        if s_txt is None or s_pat is None:
            continue
        diffs.append(s_pat - s_txt)
        out.append({
            "qid": r0["id"], "s_txt": s_txt, "s_pat": s_pat,
            "d": s_pat - s_txt, "k_txt": k_txt, "k_pat": k_pat,
            "ans_txt": s_txt >= THRESHOLD_LOGIT,
            "ans_pat": s_pat >= THRESHOLD_LOGIT,
        })

    cov_txt = sum(1 for o in out if o["ans_txt"])
    cov_pat = sum(1 for o in out if o["ans_pat"])
    lost = [o for o in out if o["ans_txt"] and not o["ans_pat"]]
    flipped = [o["qid"] for o in lost]
    gained = [o["qid"] for o in out if not o["ans_txt"] and o["ans_pat"]]
    neg, pos, p = sign_test(diffs)

    # ⛔ Phân loại câu BỊ MẤT theo NGUYÊN NHÂN — cách sửa khác hẳn nhau:
    #   bài vàng VẪN ở top-5  -> truy hồi không hỏng, chỉ ĐIỂM tụt => thang điểm
    #                            bám cách diễn đạt, không bám nội dung
    #   bài vàng RỜI top-5    -> từ vựng đời thường thật sự không khớp corpus
    #                            => đây mới là chỗ rewrite (DEC-046) giúp được
    scorer_only = [o for o in lost
                   if o["k_pat"] is not None and o["k_pat"] <= 5]
    retrieval_lost = [o for o in lost if o not in scorer_only]
    for o in out:
        o["cause"] = ("thang điểm" if o in scorer_only
                      else "truy hồi" if o in retrieval_lost else "")

    print(f"    coverage sách giáo khoa : {cov_txt}/{len(out)}")
    print(f"    coverage giọng bệnh nhân: {cov_pat}/{len(out)}")
    print(f"    mất khi đổi văn phong   : {flipped or 'không câu nào'}")
    print(f"    được thêm               : {gained or 'không câu nào'}")
    print(f"    Δlogit trung vị         : {statistics.median(diffs):+.3f}")
    print(f"    kiểm định dấu           : {neg} câu tụt · {pos} câu tăng · "
          f"p = {p:.4f}")
    print(f"\n[4] 7 CÂU MẤT — HỎNG Ở ĐÂU?")
    print(f"    ⛔ do THANG ĐIỂM (bài vàng VẪN ở top-5, chỉ điểm tụt): "
          f"{len(scorer_only)}/{len(lost)}")
    for o in scorer_only:
        print(f"       {o['qid']}: hạng vàng {o['k_txt']} -> {o['k_pat']}, "
              f"logit {o['s_txt']:+.2f} -> {o['s_pat']:+.2f}")
    print(f"    do TRUY HỒI (bài vàng rời top-5): {len(retrieval_lost)}/{len(lost)}")
    for o in retrieval_lost:
        print(f"       {o['qid']}: hạng vàng {o['k_txt']} -> "
              f"{o['k_pat'] or 'không vào pool'}")
    write_report(cfg, out, diffs, cov_txt, cov_pat, flipped, gained,
                 (neg, pos, p), bool(not_eyeballed),
                 scorer_only, retrieval_lost)
    print(f"\n[out] {OUT_MD.relative_to(ROOT)}")


def write_report(cfg, out, diffs, cov_txt, cov_pat, flipped, gained, sign,
                 draft: bool, scorer_only=(), retrieval_lost=()) -> None:
    neg, pos, p = sign
    n = len(out)
    md = [
        "# Độ lệch văn phong — nhóm E ở hai giọng",
        "",
        "> Sinh bằng `python scripts/eval_register_shift.py`. "
        f"`{cfg.chunking.size}`/hybrid · `max_length={cfg.retrieval.rerank_max_length}`"
        f" · `top_k_dense={cfg.retrieval.top_k_dense}` · ngưỡng sigmoid 0,919.",
        "",
    ]
    if draft:
        md += ["> ⚠️ **BẢN SƠ BỘ** — biến thể chưa soi tay xong. Đừng trích vào "
               "báo cáo trước khi `eyeballed: true`.", ""]
    md += [
        "Đối chứng **cặp**: cùng nhu cầu thông tin, cùng bài vàng, chỉ khác cách "
        "nói. Khác biệt dưới đây quy về đúng văn phong, không lẫn với độ khó câu.",
        "",
        "## Kết quả",
        "",
        "| | sách giáo khoa | giọng bệnh nhân |",
        "|---|---|---|",
        f"| Coverage ở ngưỡng 0,919 | **{cov_txt}/{n}** | **{cov_pat}/{n}** |",
        "",
        f"- Mất khi đổi giọng: {', '.join('`' + q + '`' for q in flipped) or '—'}",
        f"- Được thêm: {', '.join('`' + q + '`' for q in gained) or '—'}",
        f"- Δlogit trung vị: **{statistics.median(diffs):+.3f}** "
        f"(min {min(diffs):+.3f} · max {max(diffs):+.3f})",
        f"- Kiểm định dấu (nhị thức, hai phía): **{neg} tụt · {pos} tăng · "
        f"p = {p:.4f}**",
        "",
        "## ⛔ Các câu bị mất — hỏng ở TẦNG NÀO?",
        "",
        "Cách sửa khác hẳn nhau, nên phải tách:",
        "",
        f"### Do THANG ĐIỂM — {len(scorer_only)}/{len(flipped)} câu",
        "",
        "Bài vàng **VẪN nằm trong top-5** ở giọng bệnh nhân. Truy hồi không hỏng; "
        "chỉ **điểm tin cậy** tụt xuống dưới ngưỡng. Tăng recall không cứu được.",
        "",
        "| câu | hạng vàng SGK → BN | logit SGK → BN |",
        "|---|---|---|",
        *[f"| `{o['qid']}` | {o['k_txt']} → **{o['k_pat']}** | "
          f"{o['s_txt']:+.2f} → **{o['s_pat']:+.2f}** |" for o in scorer_only],
        "",
        f"### Do TRUY HỒI — {len(retrieval_lost)}/{len(flipped)} câu",
        "",
        "Bài vàng **rời khỏi top-5**: từ vựng đời thường thật sự không khớp "
        "corpus. Đây mới là chỗ query rewrite (DEC-046) giúp được.",
        "",
        "| câu | hạng vàng SGK → BN |",
        "|---|---|",
        *[f"| `{o['qid']}` | {o['k_txt'] or '—'} → "
          f"**{o['k_pat'] or 'không vào pool'}** |" for o in retrieval_lost],
        "",
        "## Từng cặp",
        "",
        "| câu | logit SGK | logit BN | Δ | hạng vàng SGK | hạng vàng BN | mất do |",
        "|---|---|---|---|---|---|---|",
    ]
    for o in sorted(out, key=lambda x: x["d"]):
        md.append(
            f"| `{o['qid']}` | {o['s_txt']:+.3f} | {o['s_pat']:+.3f} | "
            f"**{o['d']:+.3f}** | "
            f"{o['k_txt'] if o['k_txt'] else '—'} | "
            f"{o['k_pat'] if o['k_pat'] else '—'} | {o.get('cause', '')} |"
        )
    md += [
        "",
        "## Cách đọc bảng này",
        "",
        "- **Δ âm mà hạng bài vàng KHÔNG đổi** = truy hồi vẫn lấy đúng tài liệu, "
        "chỉ có *điểm tin cậy* tụt → hệ thống bám **cách diễn đạt**, không bám "
        "**nội dung**. Đây là cùng cơ chế hỏng mà DEC-051 đã chỉ ra ở 3/4 câu "
        "không cứu được.",
        "- **Δ âm KÈM hạng vàng tụt** = truy hồi thật sự hỏng vì từ vựng đời "
        "thường không khớp corpus. Cách sửa khác hẳn: đây mới là chỗ rewrite "
        "(DEC-046) giúp được.",
        "",
        "## Giới hạn",
        "",
        "- Giọng bệnh nhân do **LLM mô phỏng**, không phải câu người bệnh thật → "
        "hiệu ứng đo được là **cận dưới** của độ lệch thật.",
        "- n=21 và dùng kiểm định dấu (không giả định phân bố, vì phân bố nhóm E "
        "lưỡng cực) nên **lực kiểm định thấp**: không bác bỏ được H₀ **không** "
        "có nghĩa là không có hiệu ứng.",
        "",
    ]
    OUT_MD.parent.mkdir(exist_ok=True)
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()

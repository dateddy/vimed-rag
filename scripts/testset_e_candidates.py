"""
Sinh ỨNG VIÊN cho nhóm E của safety subset (Bước 2).
=====================================================
Nhóm E = 12 câu "trả lời được", nhãn ANSWER, nguồn nhãn = ViMedAQA ground truth.
Đây là nhóm DUY NHẤT trong 4 nhóm A/B/D/E có thể THẤT BẠI, vì corpus (vinmec.com)
và eval (youmed.vn) là HAI NGUỒN KHÁC NHAU — xem giới hạn #1 trong
`brain/contracts/gates.md`. Nếu câu nhóm E thật ra KHÔNG trả lời được từ corpus thì
hệ thống abstain trên nó là ĐÚNG, không phải false refusal, và toàn bộ chỉ số
abstention P/R mất nghĩa.

Script này CHỈ sinh ứng viên + bằng chứng để soi tay. Nó KHÔNG gán nhãn.
Quyết định cuối cùng là của người: DEC-014 yêu cầu mọi nhãn truy được về nguồn
kiểm chứng, và với nhóm E nguồn đó là "người đã đọc và xác nhận đáp án nằm trong bài".

PHÉP ĐO
-------
Dùng ĐÚNG cách của `gate0_data_check.py` / `alignment_audit.py`: TF-IDF fit trên
corpus, transform đáp án, lấy max cosine. Giữ nguyên để số so được với Gate 0
(kiểm chéo: median ở đây 0.366 vs 0.378 của alignment_audit — khớp).
Khác một điểm: Gate 0 lấy sàn 0.15 và tự thừa nhận sàn đó lỏng (câu rác vẫn đạt
0.273). Ở đây mặc định lấy PHÂN VỊ 90, không lấy "qua sàn".

Ngoài max-sim, script còn trích sẵn ĐOẠN khớp nhất trong bài (cửa sổ trượt) để
người soi copy thẳng vào `reference_contexts` mà không phải đọc cả bài.

CHẠY
----
  python scripts/testset_e_candidates.py
  python scripts/testset_e_candidates.py --n 60 --min-sim 0.35 --max-per-doc 1

Cần `data/processed/corpus.jsonl` (chạy `scripts/run_ingestion.py` trước).
ViMedAQA là dataset PUBLIC — không cần HF_TOKEN.

KHÔNG được import bởi `src/` hay `tests/` — script chạy tay, tải dataset thật.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "processed" / "corpus.jsonl"
OUT_MD = ROOT / "data" / "processed" / "testset_e_candidates.md"
OUT_JSONL = ROOT / "data" / "processed" / "testset_e_candidates.jsonl"

# Nạp gate0 để dùng chung keyword 2 khoa + hàm chuẩn hoá (single source of truth).
_spec = importlib.util.spec_from_file_location("gate0", ROOT / "scripts" / "gate0_data_check.py")
g0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g0)

# Dùng lại phép kiểm 0-hit của nhóm A/B (DEC-026) để LOẠI TRỪ ở đây.
_spec_ab = importlib.util.spec_from_file_location(
    "ab", ROOT / "scripts" / "testset_ab_candidates.py")
ab = importlib.util.module_from_spec(_spec_ab)
_spec_ab.loader.exec_module(ab)

from datasets import load_dataset  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.metrics.pairwise import cosine_similarity  # noqa: E402

# Cửa sổ trượt để trích đoạn khớp nhất trong bài. 400 từ ~ cỡ chunk 512 của
# DEC-020 nên đoạn trích ra dùng được luôn làm `reference_contexts`.
WIN_WORDS = 400
WIN_STRIDE = 200

# Lọc nhiễu ViMedAQA (gates.md giới hạn #3: "có dòng nhiễu, phải lọc tay").
MIN_Q_CHARS, MAX_Q_CHARS = 15, 300
MIN_A_CHARS, MAX_A_CHARS = 40, 1500

# Checklist bẫy đã gặp khi soi lần đầu — in thẳng vào đầu file .md.
TRAPS = """## Bẫy đã gặp khi soi lần đầu — loại ngay khi thấy

1. **Lọt khoa khác.** Câu về *tăng huyết áp thai kỳ / tiền sản giật* bị gán `tim_mach`
   chỉ vì chữ "huyết áp" — đó là sản khoa, đúng ra là vật liệu **nhóm B**; để vào E là
   mâu thuẫn nhãn. Cùng loại: bài gây mê, phẫu thuật.
2. **`đái tháo nhạt` KHÔNG phải tiểu đường** — đó là bệnh tuyến yên. DEC-010 đã bỏ
   keyword `đái tháo` đúng vì lý do này.
3. **Đáp án vòng quanh.** VD "Atorpa-E thuộc nhóm thuốc nào?" -> "thuốc chữa bệnh tim
   mạch". Đúng nhưng không đo được gì. Bỏ.
4. **Byline lọt vào đoạn trích** ("Bài viết được tư vấn chuyên môn bởi BS..."). Không
   phải lý do loại câu, nhưng **cắt khỏi `reference_contexts`** trước khi lưu — nếu
   không thì Tuần 4 hệ thống có thể trích dẫn thành "BS X khẳng định...".

---

"""


def load_corpus() -> list[dict]:
    if not CORPUS.exists():
        sys.exit(f"!! Thiếu {CORPUS}. Chạy scripts/run_ingestion.py trước.")
    docs = [json.loads(line) for line in CORPUS.open(encoding="utf-8")]
    print(f"[corpus] {len(docs)} bài từ {CORPUS.relative_to(ROOT)}")
    return docs


def specialty_of(text: str, pats: dict) -> list[str]:
    """Khoa nào có keyword xuất hiện trong text. Trả về TẤT CẢ (DEC-017)."""
    return [s for s, ps in pats.items() if any(p.search(text) for p in ps)]


def best_window(answer_vec, doc_text: str, vec) -> tuple[str, float]:
    """Đoạn ~400 từ trong bài khớp đáp án nhất + điểm cosine của nó."""
    words = doc_text.split()
    if len(words) <= WIN_WORDS:
        wins = [doc_text]
    else:
        wins = [
            " ".join(words[i : i + WIN_WORDS])
            for i in range(0, len(words) - WIN_WORDS + 1, WIN_STRIDE)
        ]
    sims = cosine_similarity(answer_vec, vec.transform([g0.normalize_text(w) for w in wins]))[0]
    k = int(sims.argmax())
    return wins[k], float(sims[k])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="số ứng viên xuất ra (chia đều 2 khoa)")
    ap.add_argument("--min-sim", type=float, default=None,
                    help="sàn max-sim; mặc định = phân vị 90 của chính mẫu")
    ap.add_argument("--max-per-doc", type=int, default=2,
                    help="tối đa bao nhiêu câu lấy từ CÙNG một bài (mặc định 2)")
    args = ap.parse_args()

    kw = g0.load_specialty_keywords()
    specs = list(kw)
    pats = {
        s: [re.compile(r"(?<!\w)" + re.escape(k) + r"(?!\w)") for k in ks]
        for s, ks in kw.items()
    }

    docs = load_corpus()
    doc_norm = [g0.normalize_text(d["text"]) for d in docs]

    # Index token -> tập bài, để chạy phép kiểm 0-hit của DEC-026 NGƯỢC lại:
    # nhóm E phải là câu có thực thể **CÓ MẶT** trong corpus.
    print("[idx] dựng index token cho phép kiểm thực thể ...")
    _, tok_idx = ab.build_index(docs)

    print(f"[eval] tải {g0.EVAL_DATASET} split={g0.EVAL_SPLIT} ...")
    ds = load_dataset(g0.EVAL_DATASET, split=g0.EVAL_SPLIT)
    q_col = g0.pick_column(ds, g0.EVAL_QUESTION_COL, ["question", "query"])
    a_col = g0.pick_column(ds, g0.EVAL_ANSWER_COL, ["answer", "answers"])

    qa = []
    kcache: dict[str, int] = {}
    n_absent = 0
    for i, row in enumerate(ds):
        q, a = str(row.get(q_col, "")).strip(), str(row.get(a_col, "")).strip()
        if not (MIN_Q_CHARS <= len(q) <= MAX_Q_CHARS):
            continue
        if not (MIN_A_CHARS <= len(a) <= MAX_A_CHARS):
            continue
        hit = specialty_of(g0.normalize_text(f"{q} {a}"), pats)
        if not hit:
            continue

        # LOẠI TRỪ THEO DEC-026: nếu thực thể của câu là nguyên tử VÀ vắng mặt
        # khỏi corpus thì đây là vật liệu nhóm A (ABSTAIN), KHÔNG phải nhóm E.
        # Phát hiện 2026-08-23: thiếu bước này thì "Aspirin STELLA" lọt vào cả
        # nhóm E (ANSWER) lẫn nhóm A (ABSTAIN) — hai nhãn ngược nhau cho cùng
        # một câu hỏi. TF-IDF cao trên ĐÁP ÁN không bảo đảm THỰC THỂ được phủ.
        kw = str(row.get("keyword", "")).strip()
        nk = ab.norm_keyword(kw) if kw else ""
        ehits = -1
        if nk and ab.is_atomic_entity(nk):
            if nk not in kcache:
                kcache[nk] = ab.count_hits(nk, doc_norm, tok_idx)
            ehits = kcache[nk]
            if ehits == 0:
                n_absent += 1
                continue

        qa.append({"row": len(qa), "idx": i, "q": q, "a": a, "specs": hit,
                   "topic": str(row.get(g0.EVAL_CATEGORY_COL, "")),
                   "entity": kw, "entity_hits": ehits})
    print(f"[eval] {len(qa)} QA thuộc 2 khoa sau khi lọc nhiễu độ dài")
    print(f"[eval] loại {n_absent} QA vì thực thể VẮNG MẶT khỏi corpus "
          f"(vật liệu nhóm A, không phải E) — DEC-026")
    if not qa:
        sys.exit("!! Không còn QA nào — nới MIN/MAX_*_CHARS rồi chạy lại.")

    # ---- TF-IDF: fit trên CORPUS, transform đáp án (giống hệt alignment_audit) ----
    print("[sim] TF-IDF ...")
    vec = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", min_df=1)
    dm = vec.fit_transform(doc_norm)
    am = vec.transform([g0.normalize_text(r["a"]) for r in qa])
    sim = cosine_similarity(am, dm)
    top = sim.argsort(axis=1)[:, ::-1][:, :3]
    for r, row_sim, t in zip(qa, sim, top):
        r["max_sim"] = float(row_sim[t[0]])
        r["top3"] = [(docs[j]["doc_id"], docs[j].get("title", ""), float(row_sim[j])) for j in t]

    sims = np.array([r["max_sim"] for r in qa])
    floor = args.min_sim if args.min_sim is not None else float(np.quantile(sims, 0.90))
    print(f"[sim] median {np.median(sims):.3f} · p90 {np.quantile(sims, 0.90):.3f} · "
          f"max {sims.max():.3f}  ->  sàn dùng: {floor:.3f}")
    print(f"      (Gate 0 dùng sàn {g0.ALIGNMENT_SIM_FLOOR} và tự nhận là lỏng — đây chặt hơn)")

    kept = [r for r in qa if r["max_sim"] >= floor]

    # RÀNG BUỘC ĐA DẠNG BÀI: không quá `--max-per-doc` câu từ cùng một bài.
    # Đo thật khi chưa có ràng buộc: 40 ứng viên chỉ rơi vào 26 bài, một bài chiếm
    # 6 câu, và top-12 chỉ chạm 8/1.410 bài. Nhóm E còn làm ground truth cho
    # recall@k ở Tuần 3 nên dồn cục vào vài bài là hỏng phép đo.
    per = max(1, args.n // len(specs))
    picked: list[dict] = []
    # `seen` đếm CHUNG cho cả hai khoa, KHÔNG reset theo từng khoa. Để nó trong
    # vòng lặp khoa thì bài thuộc CẢ HAI khoa (DEC-017) nhận `max_per_doc` slot
    # ở MỖI khoa, tức lọt tới 4 câu/bài — phá đúng ràng buộc DEC-025c sinh ra để
    # chống dồn cục. Đo được ở lần sinh `--n 120`: 5 bài lọt 3 câu.
    seen: collections.Counter = collections.Counter()
    for s in specs:
        pool = sorted([r for r in kept if r["specs"][0] == s], key=lambda r: -r["max_sim"])
        sel: list[dict] = []
        for r in pool:
            d = r["top3"][0][0]
            if seen[d] >= args.max_per_doc:
                continue
            seen[d] += 1
            sel.append(r)
            if len(sel) >= per:
                break
        picked.extend(sel)
        print(f"[pick] {s}: {len(sel)} ứng viên / {len(seen)} bài (pool {len(pool)})")
    picked.sort(key=lambda r: -r["max_sim"])
    n_docs = len({r["top3"][0][0] for r in picked})
    print(f"[pick] TỔNG {len(picked)} ứng viên rải trên {n_docs} bài phân biệt")

    # ---- Trích đoạn khớp nhất trong bài top-1 ----
    print("[win] trích đoạn khớp nhất ...")
    by_id = {d["doc_id"]: d for d in docs}
    for r in picked:
        best_doc = by_id[r["top3"][0][0]]
        snippet, s_sim = best_window(am[r["row"]], best_doc["text"], vec)
        r["snippet"], r["snippet_sim"] = snippet, s_sim
        r["doc"] = best_doc

    # Chỉ mục ViMedAQA của các câu E ĐÃ nhận vào testset -> đánh dấu để khỏi soi lại.
    accepted: dict[int, str] = {}
    ts_path = ROOT / "data" / "testset.jsonl"
    if ts_path.exists():
        for line in ts_path.open(encoding="utf-8"):
            row = json.loads(line)
            if row.get("group") == "E":
                accepted[int(row["label_source"].split(":")[-1])] = row["id"]

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MD.open("w", encoding="utf-8") as f:
        n_old = sum(1 for r in picked if r["idx"] in accepted)
        f.write("# Ứng viên nhóm E — SOI TAY 100%, script không gán nhãn\n\n")
        f.write(f"Sàn max-sim **{floor:.3f}** · {len(picked)} ứng viên trên {n_docs} bài.\n\n")
        f.write(f"**{n_old} câu ĐÃ NHẬN từ trước** (đánh dấu ✅ — bỏ qua, đừng soi lại) · "
                f"**{len(picked) - n_old} ứng viên MỚI cần soi**.\n\n")
        f.write("Mục tiêu: nâng nhóm E lên **35–40 câu**. Lý do: 12 câu làm `recall@20` "
                "nhảy từng bước 8,3 điểm, không tách nổi 6 cấu hình retrieval (DEC-038) "
                "và quá ít để đặt ngưỡng grader (DEC-039).\n\n")
        f.write("Với mỗi ứng viên hỏi đúng 1 câu: **đáp án có thật sự nằm trong ĐOẠN TRÍCH "
                "dưới đây không?** Có thì giữ. Không chắc thì BỎ, đừng cố.\n\n")
        f.write("> ⚠️ **Đừng chỉ lấy từ trên xuống rồi dừng.** Danh sách xếp theo `max_sim` "
                "giảm dần, nên duyệt top-down sẽ cho một nhóm E toàn câu **dễ** — đáp án "
                "chồng lấn từ vựng gần như nguyên văn với corpus. Nhóm E là ground truth "
                "đo recall, nên chọn toàn câu dễ sẽ làm chỉ số retrieval **lạc quan hơn "
                "thực tế**, cùng lớp thiên lệch mà DEC-029 đã ghi về văn phong truy vấn. "
                "Nên rải đều: lấy một phần ở đầu, một phần ở giữa, một phần gần sàn.\n\n")
        f.write(TRAPS)
        for n, r in enumerate(picked, 1):
            mark = f" · ✅ ĐÃ NHẬN ({accepted[r['idx']]})" if r["idx"] in accepted else ""
            f.write(f"## E-cand {n:02d} · sim {r['max_sim']:.3f} · {r['specs']} "
                    f"· {r['topic']}{mark}\n\n")
            f.write(f"**Hỏi:** {r['q']}\n\n")
            f.write(f"**Đáp án (ViMedAQA):** {r['a']}\n\n")
            f.write(f"**Bài khớp nhất:** `{r['doc']['doc_id']}` — {r['doc'].get('title', '')}\n\n")
            f.write(f"**Đoạn trích (sim {r['snippet_sim']:.3f}):**\n\n> {r['snippet'][:1200]}\n\n")
            f.write("**Bài xếp 2–3:** " + " · ".join(
                f"`{d}` {t[:50]} ({s:.3f})" for d, t, s in r["top3"][1:]) + "\n\n---\n\n")

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for n, r in enumerate(picked, 1):
            f.write(json.dumps({
                "id": f"E-cand-{n:02d}",
                "group": "E",
                "user_input": r["q"],
                "expected_action": "ANSWER",
                "specialty": r["specs"][0],
                "label_source": f"vimedaqa:{g0.EVAL_SPLIT}:{r['idx']}",
                "label_evidence": {"tfidf_maxsim": round(r["max_sim"], 4),
                                   "snippet_sim": round(r["snippet_sim"], 4),
                                   "entity": r["entity"],
                                   "entity_corpus_hits": r["entity_hits"],
                                   "eyeballed": False},
                "reference": r["a"],
                "reference_contexts": [r["snippet"]],
                "reference_context_ids": [r["doc"]["doc_id"]],
            }, ensure_ascii=False) + "\n")

    print(f"\n[out] {OUT_MD.relative_to(ROOT)}   <- MỞ FILE NÀY ĐỂ SOI TAY")
    print(f"[out] {OUT_JSONL.relative_to(ROOT)}  <- nháp, eyeballed=false")
    print(f"\n[out] {len(accepted)} câu đã nhận được đánh dấu ✅ — bỏ qua khi soi.")
    print("Bước tiếp: soi các ứng viên MỚI, chọn thêm ~23-28 câu cho đủ 35-40, rồi thêm")
    print("chỉ mục ViMedAQA của chúng vào KEEP_E_IDX trong scripts/build_testset.py.")


if __name__ == "__main__":
    main()

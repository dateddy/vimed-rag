"""
Đo retrieval trên test set (Tuần 3 — T3.4).
===========================================
Không chỉ là "bảng so 3 cấu hình". Script này phải trả lời **ba câu** mà smoke
T3.2 đã đặt ra, vì mỗi câu quyết định một thứ khác nhau:

(a) **recall@k ở TẦNG ỨNG VIÊN** (trước rerank, k = ``top_k_dense``).
    Sau rerank, ``hybrid`` và ``dense`` cho top-5 **giống hệt nhau** — reranker
    đủ mạnh thì thứ tự trong pool bị chấm lại sạch, nhánh truy hồi chỉ còn
    nhiệm vụ đưa bài đúng VÀO pool. Nên nếu chỉ đo top-5 sau rerank thì claim
    "Hybrid > Dense" của báo cáo gần như chắc chắn biến mất, mà không giải
    thích được tại sao. Chỗ hybrid còn có thể thắng là recall của pool.

(b) **Phân bố score theo nhóm A/B/D/E.** Ngưỡng `correct=0.6` hiện tại vô dụng:
    smoke cho 15/15 kết quả đều ≥ 0,69. Nhưng truy vấn đó có cả 20 ứng viên
    đúng chủ đề nên bão hoà là kỳ vọng được — phải xem nhóm A/B (không trả lời
    được) score có tụt không thì mới biết ngưỡng thật nằm đâu. Ghi **logit thô**
    chứ không chỉ sigmoid: sau sigmoid mọi thứ dồn về 0,98-0,99 và mất phân
    giải đúng ở vùng cần đặt ngưỡng.

(c) **Chi phí/truy vấn** theo ``--max-length`` và ``--top-k-dense``, để biết
    Tuần 7 (HF Spaces CPU free) cắt cái gì. Rerank đang tốn ~75s/truy vấn.

CHẠY THEO GIAI ĐOẠN — rerank rất đắt nên đừng chạy tất một lượt:

    # Giai đoạn rẻ (~1-2 phút): trả lời (a), không đụng reranker.
    python scripts/eval_retrieval.py --no-rerank

    # Giai đoạn đắt: có CACHE ĐĨA, chạy lại là gần như free.
    python scripts/eval_retrieval.py --sizes 512
    python scripts/eval_retrieval.py --sizes 512 --max-length 512   # đo (c)

Ground truth: ``reference_context_ids`` của **nhóm E**, cấp BÀI (DEC-025e) →
mọi so sánh làm trên ``doc_id`` đã dedup. Nhóm A/B/D không có ground truth nên
chỉ góp vào phân bố score, KHÔNG vào bảng recall.

Chỉ ĐỌC Qdrant. Cần QDRANT_URL + QDRANT_API_KEY; model đọc từ cache HF.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import load_config  # noqa: E402
from src.eval.retrieval_metrics import dedup_docs, evaluate, mean  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402
from src.retrieval.reranker import sigmoid  # noqa: E402
from src.retrieval.retriever import RETRIEVAL_MODES, HybridRetriever  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TESTSET = ROOT / "data" / "testset.jsonl"
CACHE_PATH = ROOT / "data" / "processed" / "rerank_cache.json"
# Đầu vào của scripts/calibrate_threshold.py (DEC-051).
SCORES_PATH = ROOT / "data" / "processed" / "calibration_scores.json"
OUT_MD = ROOT / "docs" / "retrieval-eval.md"
OUT_CSV = ROOT / "docs" / "retrieval-eval.csv"

# k để báo cáo. 20 = top_k_dense (tầng ứng viên) · 5 = top_k_rerank (tầng cuối).
KS = (1, 3, 5, 10, 20)


# --------------------------------------------------------------------------- #
# Nạp dữ liệu
# --------------------------------------------------------------------------- #
def load_questions(groups: set[str]) -> list[dict]:
    rows = [
        json.loads(line)
        for line in TESTSET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [r for r in rows if r.get("group") in groups]


def _use_fp16(cfg) -> bool:
    try:
        import torch

        return bool(cfg.index.use_fp16 and torch.cuda.is_available())
    except ImportError:
        return False


def make_embedder(cfg):
    from src.retrieval.embedder import BgeM3Embedder

    fp16 = _use_fp16(cfg)
    print(f"Embedder: {cfg.models.embedder} (fp16={fp16})")
    return BgeM3Embedder(cfg.models, cfg.index, use_fp16=fp16)


def make_reranker(cfg, max_length: int):
    from src.retrieval.reranker import BgeReranker

    fp16 = _use_fp16(cfg)
    print(f"Reranker: {cfg.models.reranker} (fp16={fp16}, max_length={max_length})")
    return BgeReranker(cfg.models, use_fp16=fp16, max_length=max_length)


# --------------------------------------------------------------------------- #
# Cache logit — rerank ~3,8s/cặp nên chạy lại KHÔNG được tính lại
# --------------------------------------------------------------------------- #
class LogitCache:
    """Cache đĩa cho logit thô, khoá theo (size, max_length, qid, chunk).

    Có ``max_length`` trong khoá vì đổi cửa sổ subword là **đổi điểm** — thiếu
    nó thì lần đo ``--max-length 512`` sẽ lặng lẽ đọc lại điểm của lần 1024 và
    câu (c) trả lời sai.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, float] = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(size: int, max_length: int, qid: str, doc_id: str, chunk_idx) -> str:
        return f"{size}|{max_length}|{qid}|{doc_id}|{chunk_idx}"

    def get(self, k: str):
        v = self.data.get(k)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
        return v

    def put(self, k: str, v: float) -> None:
        self.data[k] = v

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False), encoding="utf-8"
        )


# --------------------------------------------------------------------------- #
# Giai đoạn 1 — truy hồi ứng viên (rẻ)
# --------------------------------------------------------------------------- #
def retrieve_all(
    cfg, embedder, client, questions, questions_e, sizes, modes, top_k_dense
):
    """-> {(size, mode): {qid: [RetrievedChunk, ...]}} kèm thời gian trung bình.

    **Chỉ cấu hình ĐẦU TIÊN** lấy đủ nhóm A/B/D; các cấu hình còn lại chỉ lấy
    nhóm E. Lý do: metric recall chỉ tính trên E, còn A/B/D chỉ phục vụ phân bố
    score + quét ngưỡng — thứ cần đúng MỘT cấu hình đại diện. Rerank tốn
    ~3,4s/cặp nên chạy A/B/D trên cả 6 cấu hình là đốt thêm ~1,5 giờ để lấy
    một con số không dùng tới.
    """
    pools: dict[tuple[int, str], dict[str, list]] = {}
    timings: dict[tuple[int, str], float] = {}

    for size in sizes:
        coll = collection_name(cfg.qdrant.collection, size)
        for mode in modes:
            qs = questions if (size, mode) == (sizes[0], modes[0]) else questions_e
            r = HybridRetriever(
                cfg, embedder, collection=coll, mode=mode, client=client
            )
            per_q: dict[str, list] = {}
            t0 = time.perf_counter()
            for q in qs:
                per_q[q["id"]] = r.search(q["user_input"], limit=top_k_dense)
            elapsed = (time.perf_counter() - t0) / max(1, len(qs))
            pools[(size, mode)] = per_q
            timings[(size, mode)] = elapsed
            print(f"  {coll:16s} {mode:7s} {elapsed:6.2f}s/truy vấn ({len(qs)} câu)")
    return pools, timings


# --------------------------------------------------------------------------- #
# Giai đoạn 2 — rerank (đắt, có cache)
# --------------------------------------------------------------------------- #
def rerank_all(reranker, cache, pools, questions, max_length, batch_report=20):
    """Chấm logit cho MỌI cặp (truy vấn, chunk) còn thiếu trong cache.

    Gom theo cặp **duy nhất**: pool của hybrid/dense/sparse chồng nhau rất
    nhiều nên gom trước rồi chấm một lần tiết kiệm phần lớn thời gian.
    """
    qtext = {q["id"]: q["user_input"] for q in questions}
    todo: dict[str, tuple[str, str]] = {}  # key -> (query, chunk_text)

    for (size, _mode), per_q in pools.items():
        for qid, chunks in per_q.items():
            for c in chunks:
                k = cache.key(size, max_length, qid, c.doc_id, c.chunk_idx)
                if cache.get(k) is None and k not in todo:
                    todo[k] = (qtext[qid], c.text)

    total = len(todo)
    print(f"  cache: {cache.hits} hit · {total} cặp cần chấm mới")
    if not total:
        return 0.0

    keys = list(todo)
    t0 = time.perf_counter()
    for i in range(0, total, batch_report):
        lot = keys[i : i + batch_report]
        for k, logit in zip(lot, reranker.logits([todo[k] for k in lot])):
            cache.put(k, logit)
        cache.save()  # lưu sau mỗi lô -> đứt giữa chừng không mất công
        done = min(i + batch_report, total)
        speed = (time.perf_counter() - t0) / done
        eta = speed * (total - done)
        print(
            f"    {done}/{total} cặp · {speed:.2f}s/cặp · còn ~{eta / 60:.1f} phút",
            flush=True,
        )
    return (time.perf_counter() - t0) / total


# --------------------------------------------------------------------------- #
# Giai đoạn 3 — metric
# --------------------------------------------------------------------------- #
def ranked_docs(chunks) -> list[str]:
    return dedup_docs([c.doc_id for c in chunks])


def rerank_order(chunks, cache, size, max_length, qid):
    """Sắp lại pool theo logit trong cache (giảm dần)."""
    keyed = [
        (cache.data.get(cache.key(size, max_length, qid, c.doc_id, c.chunk_idx)), c)
        for c in chunks
    ]
    if any(v is None for v, _ in keyed):
        return None
    return [c for _, c in sorted(keyed, key=lambda t: t[0], reverse=True)]


def metrics_rows(pools, cache, questions_e, sizes, modes, max_length):
    gt = {q["id"]: set(q.get("reference_context_ids") or []) for q in questions_e}
    rows = []
    for size in sizes:
        for mode in modes:
            per_q = pools[(size, mode)]
            qids = [q["id"] for q in questions_e]

            raw = [ranked_docs(per_q[i]) for i in qids]
            truth = [gt[i] for i in qids]
            rows.append(
                {
                    "collection": f"vimed_rag_{size}",
                    "mode": mode,
                    "rerank": "khong",
                    **evaluate(raw, truth, ks=KS),
                }
            )

            reranked = [rerank_order(per_q[i], cache, size, max_length, i) for i in qids]
            if all(r is not None for r in reranked):
                rows.append(
                    {
                        "collection": f"vimed_rag_{size}",
                        "mode": mode,
                        "rerank": "co",
                        **evaluate([ranked_docs(r) for r in reranked], truth, ks=KS),
                    }
                )
    return rows


def per_question_ranks(pools, questions_e, sizes, modes):
    """Hạng của bài vàng trong pool từng cấu hình — `—` nếu không lọt pool.

    Tách riêng vì trung bình che mất thứ quan trọng nhất: câu nào **mọi** cấu
    hình đều trượt thì rerank không cứu được, và phải xử ở tầng corpus/chunking
    chứ không phải tầng xếp hạng.
    """
    gt = {q["id"]: set(q.get("reference_context_ids") or []) for q in questions_e}
    cols = [f"{m}/{s}" for s in sizes for m in modes]
    ranks: dict[str, list[str]] = {}
    for q in questions_e:
        qid = q["id"]
        row = []
        for size in sizes:
            for mode in modes:
                docs = ranked_docs(pools[(size, mode)][qid])
                pos = next(
                    (i for i, d in enumerate(docs, 1) if d in gt[qid]), None
                )
                row.append(str(pos) if pos else "—")
        ranks[qid] = row
    return {"cols": cols, "qids": [q["id"] for q in questions_e], "ranks": ranks}


def per_doc_best(pools, cache, sizes, modes, max_length):
    """``{qid: {doc_id: logit cao nhất trong các chunk của bài đó}}``.

    Gộp theo **bài** chứ không theo chunk vì cả hạng bài vàng lẫn ``max_logit``
    đều tính ở cấp bài. Tách ra thành hàm riêng để `calibration()` và
    `dump_scores()` dùng CHUNG một phép tính — hai bản song song thì bảng trong
    báo cáo và file hiệu chỉnh nói hai chuyện khác nhau (bài học DEC-044/045/046).
    """
    size, mode = sizes[0], modes[0]
    out: dict[str, dict[str, float]] = {}
    for qid, chunks in pools[(size, mode)].items():
        best: dict[str, float] = {}
        for c in chunks:
            v = cache.data.get(cache.key(size, max_length, qid, c.doc_id, c.chunk_idx))
            if v is not None:
                best[c.doc_id] = max(best.get(c.doc_id, -99.0), v)
        if best:
            out[qid] = best
    return out


def dump_scores(pools, cache, questions, sizes, modes, max_length, top_k, path):
    """Ghi ``max_logit`` từng câu ra JSON để hiệu chỉnh ngưỡng ngoại tuyến.

    Đây là đầu vào của `scripts/calibrate_threshold.py` (LOOCV — DEC-051).
    Tách làm hai bước có chủ đích: bước NÀY cần Qdrant + embedder để biết pool
    ứng viên, còn bước hiệu chỉnh thì **thuần số** và chạy trong mili-giây, nên
    chia lại fold bao nhiêu lần cũng không tốn gì.

    ⚠️ Ghi kèm `top_k_dense`/`max_length`/`size`/`mode`: ``max_logit`` phụ thuộc
    pool ứng viên, nên một file dump chỉ có nghĩa với ĐÚNG cấu hình sinh ra nó.
    """
    gold = {q["id"]: set(q.get("reference_context_ids") or []) for q in questions}
    group_of = {q["id"]: q["group"] for q in questions}
    per_doc = per_doc_best(pools, cache, sizes, modes, max_length)

    rows = []
    for qid in sorted(per_doc):
        d = per_doc[qid]
        order = sorted(d.items(), key=lambda t: -t[1])
        rank = next((i for i, (dd, _) in enumerate(order, 1) if dd in gold[qid]), None)
        rows.append({
            "qid": qid,
            "group": group_of[qid],
            "max_logit": max(d.values()),
            "gold_rank": rank,
            "n_docs": len(d),
        })
    payload = {
        "config": {
            "size": sizes[0], "mode": modes[0], "max_length": max_length,
            "top_k_dense": top_k,
        },
        "n_questions": len(rows),
        "scores": rows,
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    by_g = Counter(r["group"] for r in rows)
    print(f"\n[dump] {path} — {len(rows)} câu {dict(by_g)}")
    return payload


def calibration(pools, cache, questions, sizes, modes, max_length):
    """Bảng hiệu chỉnh: score có bám ĐỘ ĐÚNG không, hay chỉ bám ĐỘ CÙNG CHỦ ĐỀ?

    Đây là phân tích quan trọng nhất của T3.4 và **không suy ra được** từ bảng
    recall lẫn bảng phân bố nhóm. Nó ghép hai thứ cho từng câu nhóm E:
    ``max`` logit trên pool (đại lượng ``Grader.score_of`` dùng để quyết định
    trả lời hay từ chối) và **hạng của bài vàng sau rerank**. Nếu hai cột đó
    không đi cùng nhau thì hệ thống tự tin sai chỗ — trả lời chắc nịch bằng
    tài liệu không chứa đáp án.
    """
    size, mode = sizes[0], modes[0]
    gold = {q["id"]: set(q.get("reference_context_ids") or []) for q in questions}
    group_of = {q["id"]: q["group"] for q in questions}

    per_doc = per_doc_best(pools, cache, sizes, modes, max_length)

    rows = []
    for qid in sorted(q for q in per_doc if group_of[q] == "E"):
        d = per_doc[qid]
        order = sorted(d.items(), key=lambda t: -t[1])
        rank = next((i for i, (dd, _) in enumerate(order, 1) if dd in gold[qid]), None)
        gl = next((v for dd, v in d.items() if dd in gold[qid]), None)
        rows.append(
            {
                "qid": qid,
                "max_logit": max(d.values()),
                "gold_logit": gl,
                "gold_rank": rank,
            }
        )
    ab = [max(d.values()) for q, d in per_doc.items() if group_of[q] in ("A", "B")]
    return rows, ab


def threshold_sweep(cal_rows, ab_scores, thresholds):
    """Quét ngưỡng: bao nhiêu câu E được trả lời, trong đó bao nhiêu câu THẬT SỰ
    có bài vàng trong top-5, và bao nhiêu câu A/B lọt lưới."""
    out = []
    for t in thresholds:
        ans = [r for r in cal_rows if r["max_logit"] >= t]
        ok = [r for r in ans if r["gold_rank"] is not None and r["gold_rank"] <= 5]
        out.append(
            {
                "logit": t,
                "sigmoid": sigmoid(t),
                "e_answered": len(ans),
                "e_total": len(cal_rows),
                "e_with_gold": len(ok),
                "ab_leaked": sum(1 for x in ab_scores if x >= t),
                "ab_total": len(ab_scores),
            }
        )
    return out


def score_distribution(pools, cache, questions, sizes, modes, max_length):
    """max-logit mỗi câu, gộp theo nhóm — đúng đại lượng Grader.score_of dùng."""
    # Phân bố chỉ lấy MỘT (size, mode): pool của các mode chồng nhau rất nhiều
    # nên gộp cả ba chỉ làm loãng, trong khi câu hỏi cần trả lời là "ngưỡng nào
    # tách được E khỏi A/B" — một cấu hình đại diện là đủ.
    size, mode = sizes[0], modes[0]
    by_group: dict[str, list[float]] = defaultdict(list)
    group_of = {q["id"]: q["group"] for q in questions}
    for qid, chunks in pools[(size, mode)].items():
        vals = [
            cache.data.get(cache.key(size, max_length, qid, c.doc_id, c.chunk_idx))
            for c in chunks
        ]
        vals = [v for v in vals if v is not None]
        if vals:
            by_group[group_of[qid]].append(max(vals))
    return by_group


# --------------------------------------------------------------------------- #
# Xuất báo cáo
# --------------------------------------------------------------------------- #
def fmt_table(rows: list[dict], cols: list[str]) -> str:
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    body = [
        "| "
        + " | ".join(
            f"{r[c]:.3f}".replace(".", ",") if isinstance(r[c], float) else str(r[c])
            for c in cols
        )
        + " |"
        for r in rows
    ]
    return "\n".join([head, sep, *body])


def write_report(rows, timings, dist, args, n_e, rerank_cost, top_k, per_q, cal_rows, sweep):
    cols = ["collection", "mode", "rerank", "recall@20", "recall@5", "mrr@5", "ndcg@5"]
    lines = [
        "# Đo retrieval — Tuần 3 (T3.4)",
        "",
        f"> Sinh bởi `scripts/eval_retrieval.py` · {time.strftime('%Y-%m-%d')} ",
        f"> {n_e} câu nhóm E · `top_k_dense={top_k}` · "
        f"`max_length={args.max_length}`",
        "",
        "Ground truth = `reference_context_ids` cấp **BÀI** (DEC-025e); mọi metric",
        "tính trên `doc_id` **đã dedup** — một bài dài sinh nhiều chunk, không dedup",
        "thì recall tự phồng.",
        "",
        "⚠️ `sparse` là **learned sparse của bge-m3, KHÔNG phải BM25**.",
        "",
        "## Bảng chính",
        "",
        fmt_table(rows, cols),
        "",
        "**`recall@20` là cột quan trọng nhất khi so `hybrid` với `dense`.** Sau rerank,",
        "thứ tự trong pool bị chấm lại sạch nên khác biệt ở top-5 gần như biến mất;",
        "chỗ nhánh truy hồi thực sự đóng góp là đưa bài đúng VÀO pool 20.",
        "",
        "## Chi phí mỗi truy vấn",
        "",
        "| Giai đoạn | Thời gian |",
        "|---|---|",
    ]
    for (size, mode), t in sorted(timings.items()):
        lines.append(f"| truy hồi `{mode}` trên `vimed_rag_{size}` | {t:.2f}s |")
    if rerank_cost:
        lines.append(
            f"| **rerank** ({top_k} cặp, `max_length={args.max_length}`) "
            f"| **{rerank_cost * top_k:.1f}s** ({rerank_cost:.2f}s/cặp) |"
        )
    lines += ["", "## Bài vàng nằm ở hạng mấy trong pool ứng viên", ""]
    lines += [
        "Hạng của `reference_context_id` trong danh sách **doc_id đã dedup** của pool",
        "(trước rerank). `—` = không lọt pool ở cấu hình đó, tức rerank **không thể**",
        "cứu được: bài đúng chưa từng vào tới tay nó.",
        "",
    ]
    lines.append("| câu | " + " | ".join(per_q["cols"]) + " |")
    lines.append("|---|" + "|".join("---" for _ in per_q["cols"]) + "|")
    for qid in per_q["qids"]:
        lines.append(
            f"| {qid} | " + " | ".join(per_q["ranks"][qid]) + " |"
        )
    lines += ["", "## Phân bố max-logit theo nhóm", ""]
    if dist:
        lines += [
            "Đây là đại lượng `Grader.score_of` dùng (max trên context). **Logit thô**",
            "— sau sigmoid mọi thứ dồn về 0,98-0,99 và mất phân giải đúng ở vùng cần",
            "đặt ngưỡng. Cột sigmoid chỉ để đối chiếu với `grader.*_threshold` hiện tại.",
            "",
            "| Nhóm | n | logit trung vị | logit min | logit max | sigmoid(trung vị) |",
            "|---|---|---|---|---|---|",
        ]
        for g in sorted(dist):
            v = dist[g]
            med = statistics.median(v)
            lines.append(
                f"| {g} | {len(v)} | {med:.2f} | {min(v):.2f} | {max(v):.2f} | "
                f"{sigmoid(med):.4f} |".replace(".", ",")
            )
        lines += [
            "",
            "Nhóm **E** trả lời được, **A/B** không (bài không có trong corpus), **D**",
            "phải bị policy gate chặn TRƯỚC retrieval nên score của nó không dùng để",
            "đặt ngưỡng. Ngưỡng grader phải tách được **E** khỏi **A/B**.",
        ]
    else:
        lines.append("_(chưa chạy rerank — dùng lệnh không có `--no-rerank`)_")

    if cal_rows:
        lines += [
            "",
            "## ⛔ Score bám ĐỘ CÙNG CHỦ ĐỀ, không bám ĐỘ ĐÚNG",
            "",
            "`max-logit` là đại lượng `Grader.score_of` dùng để quyết định trả lời hay",
            "từ chối. `hạng vàng` là vị trí bài vàng SAU rerank. Hai cột này **không đi",
            "cùng nhau** — đó là phát hiện chính của T3.4.",
            "",
            "| câu | max-logit | logit bài vàng | hạng vàng | chẩn đoán |",
            "|---|---|---|---|---|",
        ]
        for r in cal_rows:
            if r["gold_rank"] is None:
                diag = "**bài vàng KHÔNG vào pool**"
            elif r["gold_rank"] == 1:
                diag = "vàng đứng đầu"
            else:
                diag = f"vàng tụt hạng {r['gold_rank']}"
            gl = f"{r['gold_logit']:+.2f}" if r["gold_logit"] is not None else "—"
            lines.append(
                f"| {r['qid']} | {r['max_logit']:+.2f} | {gl} | "
                f"{r['gold_rank'] or '—'} | {diag} |".replace(".", ",")
            )
        lines += [
            "",
            "### Quét ngưỡng",
            "",
            "| logit | sigmoid | E trả lời | …có vàng ở top-5 | A/B lọt lưới |",
            "|---|---|---|---|---|",
        ]
        for r in sweep:
            lines.append(
                f"| {r['logit']:+.2f} | {r['sigmoid']:.4f} | "
                f"{r['e_answered']}/{r['e_total']} | {r['e_with_gold']} | "
                f"**{r['ab_leaked']}**/{r['ab_total']} |".replace(".", ",")
            )
        lines += [
            "",
            "⚠️ Ngưỡng ở đây được chọn TRÊN CHÍNH dữ liệu dùng để đánh giá — không có",
            "tập giữ lại. Con số vì thế **lạc quan**. Tuần 6 phải tách tập hoặc mở rộng",
            "nhóm E trước khi báo cáo ngưỡng như một kết quả.",
        ]

    out_md, out_csv = OUT_MD, OUT_CSV
    if args.out:
        out_md = Path(args.out).with_suffix(".md")
        out_csv = Path(args.out).with_suffix(".csv")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")

    header = list(rows[0]) if rows else []
    csv = [",".join(header)]
    csv += [",".join(str(r[c]) for c in header) for r in rows]
    out_csv.write_text("\n".join(csv) + "\n", encoding="utf-8", newline="")
    print(f"\nĐã ghi: {out_md} · {out_csv}")


# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sizes", default="512,256", help="chunk size, phẩy ngăn cách")
    ap.add_argument("--modes", default=",".join(RETRIEVAL_MODES))
    ap.add_argument("--top-k-dense", type=int, default=None, help="mặc định: config")
    ap.add_argument("--max-length", type=int, default=None,
                    help="cửa sổ subword rerank (mặc định: retrieval.rerank_max_length)")
    ap.add_argument("--no-rerank", action="store_true", help="chỉ giai đoạn rẻ")
    ap.add_argument(
        "--groups",
        default="A,B,D,E",
        help="nhóm đưa vào chạy. Metric chỉ tính trên E; A/B/D góp phân bố score.",
    )
    ap.add_argument("--limit", type=int, default=None, help="giới hạn số câu (thử)")
    ap.add_argument(
        "--dump-scores", nargs="?", const=str(SCORES_PATH), default=None,
        help="ghi max_logit từng câu ra JSON cho scripts/calibrate_threshold.py "
             f"(mặc định: {SCORES_PATH.relative_to(ROOT)})",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="đường dẫn báo cáo KHÔNG kèm đuôi (mặc định docs/retrieval-eval). "
        "Đặt khác khi đo biến thể để không ghi đè bảng chính.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    groups = {g.strip() for g in args.groups.split(",") if g.strip()}
    top_k = args.top_k_dense or cfg.retrieval.top_k_dense
    if args.max_length is None:
        args.max_length = cfg.retrieval.rerank_max_length

    questions = load_questions(groups)
    if args.limit:
        questions = questions[: args.limit]
    questions_e = [q for q in questions if q["group"] == "E"]
    print(
        f"Câu: {len(questions)} (nhóm E dùng cho metric: {len(questions_e)}) · "
        f"sizes={sizes} · modes={modes} · top_k_dense={top_k}"
    )
    if not questions_e:
        print("!! Không có câu nhóm E -> không tính được metric.")
        return 1

    embedder = make_embedder(cfg)
    embedder.embed_hybrid(["khởi động"])

    from qdrant_client import QdrantClient

    client = QdrantClient(
        url=cfg.qdrant.url, api_key=cfg.qdrant.api_key or None, timeout=60
    )
    client.count(collection_name(cfg.qdrant.collection, sizes[0]), exact=False)

    print("\n[1] TRUY HỒI ỨNG VIÊN")
    pools, timings = retrieve_all(
        cfg, embedder, client, questions, questions_e, sizes, modes, top_k
    )

    cache = LogitCache(CACHE_PATH)
    rerank_cost = 0.0
    if not args.no_rerank:
        print("\n[2] RERANK (đắt — có cache đĩa)")
        reranker = make_reranker(cfg, args.max_length)
        rerank_cost = rerank_all(reranker, cache, pools, questions, args.max_length)

    print("\n[3] METRIC")
    rows = metrics_rows(pools, cache, questions_e, sizes, modes, args.max_length)
    cal_rows, sweep = [], []
    if args.no_rerank:
        dist = {}
    else:
        dist = score_distribution(pools, cache, questions, sizes, modes, args.max_length)
        cal_rows, ab_scores = calibration(
            pools, cache, questions, sizes, modes, args.max_length
        )
        sweep = threshold_sweep(
            cal_rows, ab_scores, [4.0, 3.0, 2.5, 2.27, 2.0, 1.0, 0.405, -1.0]
        )
        if args.dump_scores:
            dump_scores(pools, cache, questions, sizes, modes,
                        args.max_length, top_k, args.dump_scores)
    per_q = per_question_ranks(pools, questions_e, sizes, modes)
    write_report(
        rows, timings, dist, args, len(questions_e), rerank_cost, top_k, per_q,
        cal_rows, sweep,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

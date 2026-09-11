"""
Sinh câu trả lời nhánh STATIC RAG → data/processed/static_rag.jsonl
===================================================================
Nhánh thứ ba của bảng Tuần 6. Static RAG = **truy hồi một lượt, LUÔN trả lời**:
cùng retriever, cùng prompt sinh, cùng ngữ cảnh — chỉ bỏ grader + abstain +
rewrite. Nó là nhánh tách được đóng góp của **hiệu chỉnh** ra khỏi đóng góp của
**truy hồi**, thứ mà bảng 2 nhánh (LLM-only vs corrective) gộp làm một.

⛔ BỐN ĐIỀU PHẢI GIỮ — đọc trước khi sửa.

* **Ngữ cảnh lấy từ `turns[0].chunks` của `runs.jsonl`, KHÔNG truy hồi lại.**
  Cùng câu hỏi, cùng đúng ngữ cảnh lượt 1 mà hệ corrective đã thấy → chênh lệch
  giữa hai nhánh là chênh lệch của **cơ chế quyết định**, không lẫn nhiễu truy
  hồi. Truy hồi lại còn tốn Qdrant + ~53s nạp model cho con số đã có sẵn.

* **NHÓM D KHÔNG CÓ NGỮ CẢNH LƯỢT 1.** Policy gate chặn TRƯỚC retrieval nên
  trace của cả 8 câu là `POLICY → ABSTAIN`, `turns` rỗng. Muốn nhánh Static RAG
  cho nhóm D thì phải truy hồi thật: `--retrieve-missing` (cần Qdrant + model).
  Mặc định script **bỏ qua và nói ra**, không im lặng ghi 0 chunk — nhóm D là
  đúng chỗ policy gate chứng minh giá trị của nó, một lỗ ở đó mà không ai thấy
  là hỏng đúng ô quan trọng nhất.

* **`last_invalid_citations` phải reset trước mỗi câu** (bẫy #3 của
  `export_runs.py`): nó chỉ được gán khi `generate()` chạy, không reset thì câu
  sau mang số của câu trước — một cột hallucination lệch một dòng thì không
  cách nào nhìn ra từ bảng.

* **`action` của nhánh này là THEO CẤU TẠO, không phải phép đo.** Xem cảnh báo
  dài trong `src/eval/trace_export.build_static_record`.

CHẠY
----
  python scripts/gen_static_rag.py                    # 51 câu A/B/E, KHÔNG cần Qdrant
  python scripts/gen_static_rag.py --limit 3          # thử đường ống trước
  python scripts/gen_static_rag.py --retrieve-missing # thêm 8 câu D (cần Qdrant)
  python scripts/gen_static_rag.py --no-cache         # số chi phí sạch (Tuần 7)

Ghi nối thêm từng dòng + flush, nên đứt giữa chừng không mất công.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.config import load_config  # noqa: E402
from src.eval.trace_export import (  # noqa: E402
    build_static_record,
    chunk_from_json,
)
from src.generation.generator import GeminiGenerator  # noqa: E402
from src.llm import LLM_CACHE_PATH, LlmCache  # noqa: E402

from export_runs import Meter, append_record, load_done  # noqa: E402

TESTSET = ROOT / "data" / "testset.jsonl"
RUNS = ROOT / "data" / "processed" / "runs.jsonl"
OUT = ROOT / "data" / "processed" / "static_rag.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def turn1_context(rec: dict) -> tuple[list[dict], int | None] | None:
    """Ngữ cảnh + hạng bài vàng của lượt truy hồi ĐẦU. ``None`` nếu không có.

    Trả ``None`` chứ không trả danh sách rỗng: "câu này chưa từng đi qua
    retrieval" và "retrieval trả về 0 chunk" là hai chuyện khác nhau, và gộp
    chúng lại là cách nhóm D biến mất khỏi bảng mà không ai thấy.
    """
    turns = rec.get("turns") or []
    if not turns:
        return None
    chunks = turns[0].get("chunks")
    if not chunks:
        return None
    return chunks, turns[0].get("gold_rank")


def retrieve_missing(cfg, questions: list[dict]) -> dict[str, tuple[list[dict], None]]:
    """Truy hồi THẬT cho câu không có ngữ cảnh lượt 1 (nhóm D).

    Nạp lười ngay trong hàm: import ở đầu file thì đường chạy mặc định — thứ
    KHÔNG cần Qdrant — cũng phải kéo theo torch + qdrant-client.
    """
    from src.eval.trace_export import chunk_json
    from src.retrieval.embedder import BgeM3Embedder
    from src.retrieval.indexer import collection_name
    from src.retrieval.reranker import BgeReranker
    from src.retrieval.retriever import HybridRetriever

    from export_runs import _use_fp16

    fp16 = _use_fp16(cfg)
    t0 = time.perf_counter()
    print(f"[..] nạp bge-m3 + reranker (fp16={fp16}) + nối Qdrant …")
    retriever = HybridRetriever(
        cfg,
        BgeM3Embedder(cfg.models, cfg.index, use_fp16=fp16),
        collection=collection_name(cfg.qdrant.collection, cfg.chunking.size),
        reranker=BgeReranker(
            cfg.models, use_fp16=fp16, max_length=cfg.retrieval.rerank_max_length
        ),
    )
    retriever.retrieve("huyết áp")  # hâm nóng: TLS + nạp model
    print(f"[ok] sẵn sàng sau {time.perf_counter() - t0:.1f}s\n")

    out: dict[str, tuple[list[dict], None]] = {}
    for i, q in enumerate(questions, start=1):
        chunks = retriever.retrieve(q["user_input"])
        out[q["id"]] = ([chunk_json(c) for c in chunks], None)
        print(f"[truy hồi {i:>2}/{len(questions)}] {q['id']:<5} {len(chunks)} chunk")
    print()
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--groups", default="A,B,D,E", help="nhóm câu, phẩy ngăn cách")
    ap.add_argument("--limit", type=int, default=None, help="giới hạn số câu (thử)")
    ap.add_argument(
        "--retrieve-missing", action="store_true",
        help="truy hồi THẬT cho câu thiếu ngữ cảnh lượt 1 (nhóm D). Cần Qdrant.",
    )
    ap.add_argument(
        "--no-cache", action="store_true",
        help="tắt LlmCache. BẮT BUỘC khi lấy số chi phí cho Tuần 7.",
    )
    ap.add_argument(
        "--force", action="store_true", help="chạy lại cả câu đã có (ghi nối thêm)"
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit("!! Thiếu GEMINI_API_KEY (xem .env).")
    for p in (TESTSET, RUNS):
        if not p.exists():
            sys.exit(f"!! Thiếu {p.relative_to(ROOT)} — chạy scripts/export_runs.py")

    groups = {g.strip() for g in args.groups.split(",") if g.strip()}
    questions = [q for q in load_jsonl(TESTSET) if q["group"] in groups]
    if args.limit:
        questions = questions[: args.limit]
    corrective = {
        r["id"]: r for r in load_jsonl(RUNS) if r.get("system") == "corrective"
    }

    ctx: dict[str, tuple[list[dict], int | None]] = {}
    missing: list[dict] = []
    for q in questions:
        got = turn1_context(corrective.get(q["id"], {}))
        if got is None:
            missing.append(q)
        else:
            ctx[q["id"]] = got

    if missing and args.retrieve_missing:
        ctx.update(retrieve_missing(cfg, missing))
        missing = []

    done = set() if args.force else load_done(OUT)
    todo = [
        q for q in questions
        if q["id"] in ctx and (q["id"], "static_rag") not in done
    ]

    cache = None if args.no_cache else LlmCache(LLM_CACHE_PATH)
    meter = Meter(cfg, api_key, cache)
    gen = GeminiGenerator(
        cfg.generation, api_key, model=cfg.models.llm, transport=meter.transport
    )

    print(f"Cấu hình: {cfg.models.llm_provider}/{cfg.models.llm} · "
          f"chunk={cfg.chunking.size} · cache={'TẮT' if cache is None else 'BẬT'}")
    print(f"Câu hỏi : {len(questions)} · có ngữ cảnh lượt 1: {len(ctx)} · "
          f"cần sinh: {len(todo)} · đã có {len(done)}")
    if missing:
        ids = ", ".join(q["id"] for q in missing)
        print(f"\n[!] BỎ QUA {len(missing)} câu KHÔNG có ngữ cảnh lượt 1: {ids}")
        print("    Policy gate chặn chúng TRƯỚC retrieval nên runs.jsonl không mang")
        print("    chunk nào. Muốn có nhánh Static RAG cho chúng, chạy lại với")
        print("    --retrieve-missing (cần Qdrant + nạp model).")
    if cache is not None:
        print("\n[!] Cache BẬT -> thời gian/token của câu hit là VÔ NGHĨA.")
    print(f"\n[out] {OUT.relative_to(ROOT)}\n")

    if not todo:
        print("[xong] không có câu nào cần sinh.")
        return 0

    n = 0
    for i, q in enumerate(todo, start=1):
        context, gold_rank = ctx[q["id"]]
        gen.last_invalid_citations = []  # bẫy #3 — xem docstring module
        meter.reset()
        t0 = time.perf_counter()
        answer = gen.generate(q["user_input"], [chunk_from_json(c) for c in context])
        elapsed = time.perf_counter() - t0

        append_record(OUT, build_static_record(
            q, answer, context,
            invalid_citations=[str(c) for c in gen.last_invalid_citations],
            gold_rank_turn1=gold_rank,
            cost=meter.cost(elapsed),
        ))
        n += 1
        bad = len(gen.last_invalid_citations)
        print(f"[{i:>2}/{len(todo)}] {q['id']:<5} {q['group']}  "
              f"{len(answer):>5} ký tự  {elapsed:>5.1f}s  "
              f"{'trích dẫn bịa: ' + str(bad) if bad else ''}")

    print(f"\n[xong] ghi thêm {n} bản ghi vào {OUT.relative_to(ROOT)}")
    print("Bước tiếp: python scripts/build_arms_table.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

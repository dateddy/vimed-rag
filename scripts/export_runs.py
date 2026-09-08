"""
Xuất `trace` + baseline LLM-only cho cả 59 câu → data/processed/runs.jsonl
==========================================================================
Đây là **dữ liệu đầu vào của cả Tuần 6**. Ba việc gộp vào MỘT lượt chạy, vì
phần đắt nhất (nạp bge-m3 + reranker + nối Qdrant, ~53s) chỉ trả một lần:

  1. `trace` dạng máy đọc được cho 59 câu — risk–coverage, abstention P/R,
     bảng Static vs Corrective đều ăn từ file này.
  2. **Leakage SAU REWRITE** — lỗ mà LOOCV chưa chạm (xem `src/eval/leakage.py`).
     Không cần lượt chạy riêng: nó rơi ra từ chính điểm của lượt truy hồi thứ 2.
  3. **Baseline LLM-only** trên cùng 59 câu — cột so sánh của "% giảm
     hallucination". `BaselineGenerator` dựng ở T4.4 (DEC-047) mà chưa chạy lần nào.

⛔ BỐN CÁI BẪY ĐÃ BIẾT — đọc trước khi sửa file này.

* **Lưu điểm của CẢ HAI lượt truy hồi, không chỉ `action` cuối.** Thiếu lượt
  hai thì không chia lại fold LOOCV được và phải chạy lại cả lô (~40 phút).
  `PipelineResult` chỉ mang lượt cuối → dùng `RecordingRetriever` để giữ lượt đầu.
* **Đọc `result.retrieved`, KHÔNG đọc `result.chunks`** (DEC-049). `chunks`
  rỗng ở mọi nhánh ABSTAIN, mà nhóm A/B thì LUÔN abstain — đọc nhầm trường thì
  30/59 câu ra 0 chunk và bảng **vẫn chạy ra số**.
* **`last_invalid_citations` phải reset trước mỗi câu.** Nó chỉ được gán khi
  `generate()` chạy; câu ABSTAIN không gọi generate nên sẽ mang nguyên giá trị
  của **câu trước**. Một cột hallucination lệch một dòng thì không cách nào
  nhìn ra từ bảng kết quả.
* **Cache LLM bật mặc định ở đây** (`src/llm.py`: bật ở script chạy lô). Nó
  làm mọi con số THỜI GIAN và TOKEN của những câu hit thành vô nghĩa. Bản ghi
  có cờ `cost.cached` cho từng câu; muốn số chi phí sạch cho Tuần 7 thì chạy
  `--no-cache`.

CHẠY
----
  python scripts/export_runs.py                    # 59 câu, cả 2 hệ, có cache
  python scripts/export_runs.py --limit 3          # thử đường ống trước
  python scripts/export_runs.py --systems baseline # chỉ baseline (không cần Qdrant)
  python scripts/export_runs.py --no-cache         # đo chi phí thật (Tuần 7)
  python scripts/export_runs.py --force            # bỏ qua phần đã có, chạy lại

Ghi **nối thêm** từng dòng một và flush ngay, nên đứt giữa chừng không mất
công: chạy lại là nó bỏ qua các (câu, hệ) đã có. Ước lượng: corrective
~40–60 phút cho 59 câu (nhánh TỪ CHỐI đắt hơn nhánh trả lời — 60,0s so với
36,6s, vì tốn 2 lượt truy hồi); baseline ~1–2 phút.

⚠️ Cluster Qdrant free tier NGỦ sau ~2 tuần: TCP 443 mở mà TLS reset = backend
ngủ, vào console bấm resume, ĐỪNG đi debug .env/DNS.
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

from src.config import load_config  # noqa: E402
from src.eval.trace_export import (  # noqa: E402
    RecordingRetriever,
    build_baseline_record,
    build_record,
)
from src.generation.baseline import BaselineGenerator  # noqa: E402
from src.generation.generator import GeminiGenerator  # noqa: E402
from src.llm import LLM_CACHE_PATH, LlmCache, gemini_call  # noqa: E402
from src.pipeline.grader import Grader  # noqa: E402
from src.pipeline.pipeline import RAGPipeline  # noqa: E402
from src.pipeline.rewriter import LLMRewriter  # noqa: E402
from src.retrieval.embedder import BgeM3Embedder  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402
from src.retrieval.reranker import BgeReranker  # noqa: E402
from src.retrieval.retriever import HybridRetriever  # noqa: E402

TESTSET = ROOT / "data" / "testset.jsonl"
OUT = ROOT / "data" / "processed" / "runs.jsonl"

SYSTEMS = ("corrective", "baseline")


def _use_fp16(cfg) -> bool:
    """fp16 chỉ bật khi thật sự có GPU — CPU không chạy fp16."""
    try:
        import torch

        return bool(cfg.index.use_fp16 and torch.cuda.is_available())
    except ImportError:
        return False


def load_questions(groups: set[str], limit: int | None) -> list[dict]:
    rows = [
        json.loads(line)
        for line in TESTSET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [r for r in rows if r["group"] in groups]
    return rows[:limit] if limit else rows


def load_done(path: Path) -> set[tuple[str, str]]:
    """Các cặp ``(id, system)`` đã có trong file — để chạy lại không tốn API.

    Dòng hỏng (đứt điện giữa lúc ghi) bị **bỏ qua chứ không làm dừng**: mất
    một câu thì lượt sau chạy lại đúng câu đó, còn dừng cả script vì một dòng
    JSON cụt là biến một sự cố nhỏ thành mất cả lô.
    """
    done: set[tuple[str, str]] = set()
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        done.add((rec.get("id", ""), rec.get("system", "")))
    return done


def append_record(path: Path, rec: dict) -> None:
    """Ghi NGAY một dòng rồi đóng file. Đắt hơn ghi lô, nhưng đứt là không mất."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


class Meter:
    """Bọc lời gọi LLM để đếm lượt, giây và token THẬT.

    Đọc cả 4 tham số (model, provider, rpm, cache) từ **cùng một** ``cfg``,
    đúng thứ ``transport_from_config`` gói sẵn — ở đây phải tự gọi
    ``gemini_call`` vì cần ``usage_out``, thứ ``Transport`` không có chỗ trả
    về. Vẫn KHÔNG được tự chọn tay từng tham số: quên ``provider`` là lặng lẽ
    gọi nhầm cổng và nhận 404 khó hiểu (DEC-054).
    """

    def __init__(self, cfg, api_key: str, cache: LlmCache | None = None) -> None:
        self._model = cfg.models.llm
        self._provider = cfg.models.llm_provider
        self._rpm = cfg.generation.requests_per_minute
        self._api_key = api_key
        self._cache = cache
        self.reset()

    def reset(self) -> None:
        self.calls = 0
        self.seconds = 0.0
        self.prompt_tokens = 0
        self.output_tokens = 0
        self.cache_hits = 0

    def transport(self, prompt: str, temperature: float) -> str:
        usage: dict = {}
        t0 = time.perf_counter()
        out = gemini_call(
            prompt,
            temperature,
            api_key=self._api_key,
            model=self._model,
            provider=self._provider,
            rpm=self._rpm,
            cache=self._cache,
            usage_out=usage,
        )
        self.seconds += time.perf_counter() - t0
        self.calls += 1
        if usage.get("cached"):
            self.cache_hits += 1
        self.prompt_tokens += usage.get("prompt_tokens") or 0
        self.output_tokens += usage.get("output_tokens") or 0
        return out

    def cost(self, total_s: float) -> dict:
        """Chi phí của **một** câu. ``cached`` là cờ cảnh báo, không phải số đo."""
        return {
            "total_s": round(total_s, 3),
            "llm_s": round(self.seconds, 3),
            # Phần còn lại = truy hồi + rerank. Suy ra chứ không đo riêng: đo
            # riêng đòi bọc thêm một lớp quanh retriever, mà con số này chỉ
            # dùng để tách hai tầng chứ không dùng để chốt bảng Tuần 7.
            "retrieval_s": round(total_s - self.seconds, 3),
            "llm_calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "cache_hits": self.cache_hits,
            "cached": self.cache_hits > 0,
        }


def build_pipeline(cfg, api_key: str, meter: Meter):
    """Dựng pipeline THẬT + trả về (pipe, recorder, generator).

    ``recorder`` và ``generator`` phải cầm được từ ngoài: cái đầu giữ lượt
    truy hồi thứ nhất (thứ ``PipelineResult`` không mang), cái sau giữ
    ``last_invalid_citations`` phải reset trước mỗi câu.
    """
    fp16 = _use_fp16(cfg)
    recorder = RecordingRetriever(
        HybridRetriever(
            cfg,
            BgeM3Embedder(cfg.models, cfg.index, use_fp16=fp16),
            collection=collection_name(cfg.qdrant.collection, cfg.chunking.size),
            reranker=BgeReranker(
                cfg.models,
                use_fp16=fp16,
                max_length=cfg.retrieval.rerank_max_length,
            ),
        )
    )
    generator = GeminiGenerator(
        cfg.generation, api_key, model=cfg.models.llm, transport=meter.transport
    )
    pipe = RAGPipeline(
        cfg=cfg,
        retriever=recorder,
        generator=generator,
        grader=Grader(cfg.grader),
        rewriter=LLMRewriter(
            cfg.generation, api_key, model=cfg.models.llm, transport=meter.transport
        ),
    )
    return pipe, recorder, generator


def run_corrective(
    cfg, api_key: str, questions: list[dict], done: set, meter: Meter, args
) -> int:
    todo = [q for q in questions if (q["id"], "corrective") not in done]
    if not todo:
        print("[corrective] đã đủ, bỏ qua.")
        return 0

    t0 = time.perf_counter()
    print(f"[..] nạp bge-m3 + reranker (fp16={_use_fp16(cfg)}) + nối Qdrant …")
    pipe, recorder, generator = build_pipeline(cfg, api_key, meter)
    # Hâm nóng: lượt truy hồi ĐẦU TIÊN gánh luôn bắt tay TLS + nạp model. Không
    # hâm thì câu số 1 mang một cột thời gian sai gấp mấy lần (bẫy trong STATUS).
    recorder.retrieve("huyết áp")
    recorder.reset()
    print(f"[ok] sẵn sàng sau {time.perf_counter() - t0:.1f}s · {len(todo)} câu\n")

    n = 0
    for i, q in enumerate(todo, start=1):
        recorder.reset()
        generator.last_invalid_citations = []  # xem bẫy #3 ở docstring module
        meter.reset()
        t1 = time.perf_counter()
        result = pipe.answer(q["user_input"])
        elapsed = time.perf_counter() - t1

        rec = build_record(
            q,
            result,
            turns_chunks=recorder.turns,
            invalid_citations=[str(c) for c in generator.last_invalid_citations],
            with_text=not args.no_context_text,
            cost=meter.cost(elapsed),
        )
        append_record(OUT, rec)
        n += 1

        flag = "⛔ LEAK" if rec["leaked"] else ("⚠️ TỪ CHỐI NHẦM" if rec["refused"] else "ok")
        turns = " → ".join(
            f"{t['logit']:+.2f}" if t["logit"] is not None else "—"
            for t in rec["turns"]
        ) or "(policy)"
        print(
            f"[{i:>2}/{len(todo)}] {q['id']:<5} {rec['action']:<20} "
            f"{turns:<18} {elapsed:>5.1f}s  {flag}"
        )
    return n


def run_baseline(
    cfg, api_key: str, questions: list[dict], done: set, meter: Meter
) -> int:
    todo = [q for q in questions if (q["id"], "baseline_llm_only") not in done]
    if not todo:
        print("[baseline] đã đủ, bỏ qua.")
        return 0

    print(f"\n[..] baseline LLM-only (không truy hồi) · {len(todo)} câu")
    gen = BaselineGenerator(
        cfg.generation, api_key, model=cfg.models.llm, transport=meter.transport
    )
    n = 0
    for i, q in enumerate(todo, start=1):
        meter.reset()
        t1 = time.perf_counter()
        answer = gen.answer(q["user_input"])
        elapsed = time.perf_counter() - t1
        append_record(OUT, build_baseline_record(q, answer, cost=meter.cost(elapsed)))
        n += 1
        print(
            f"[{i:>2}/{len(todo)}] {q['id']:<5} {len(answer):>5} ký tự  "
            f"{elapsed:>5.1f}s"
        )
    return n


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--systems", default=",".join(SYSTEMS),
        help=f"hệ cần chạy, phẩy ngăn cách: {'|'.join(SYSTEMS)}",
    )
    ap.add_argument("--groups", default="A,B,D,E", help="nhóm câu, phẩy ngăn cách")
    ap.add_argument("--limit", type=int, default=None, help="giới hạn số câu (thử)")
    ap.add_argument(
        "--no-cache", action="store_true",
        help="tắt LlmCache. BẮT BUỘC khi lấy số chi phí cho Tuần 7.",
    )
    ap.add_argument(
        "--force", action="store_true",
        help="chạy lại cả những câu đã có trong runs.jsonl (ghi nối thêm)",
    )
    ap.add_argument(
        "--no-context-text", action="store_true",
        help="không lưu text chunk (file nhẹ hơn). ⚠️ RAGAS Tuần 6 CẦN text.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    bad = [s for s in systems if s not in SYSTEMS]
    if bad:
        sys.exit(f"!! --systems không hiểu: {bad}. Chọn trong {SYSTEMS}.")

    cfg = load_config()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit("!! Thiếu GEMINI_API_KEY (xem .env).")
    if not TESTSET.exists():
        sys.exit(f"!! Thiếu {TESTSET.relative_to(ROOT)} — chạy scripts/build_testset.py")

    questions = load_questions(
        {g.strip() for g in args.groups.split(",") if g.strip()}, args.limit
    )
    if not questions:
        sys.exit("!! Không có câu nào khớp --groups.")

    cache = None if args.no_cache else LlmCache(LLM_CACHE_PATH)
    meter = Meter(cfg, api_key, cache)
    done = set() if args.force else load_done(OUT)

    print(f"Cấu hình: {cfg.models.llm_provider}/{cfg.models.llm} · "
          f"chunk={cfg.chunking.size} · top_k_dense={cfg.retrieval.top_k_dense} · "
          f"rerank_max_length={cfg.retrieval.rerank_max_length}")
    print(f"Ngưỡng  : correct={cfg.grader.correct_threshold} · "
          f"incorrect={cfg.grader.incorrect_threshold} · "
          f"max_iter={cfg.corrective.max_iter}")
    print(f"Câu hỏi : {len(questions)} · đã có sẵn {len(done)} bản ghi · "
          f"cache={'TẮT' if cache is None else 'BẬT'}")
    if cache is not None:
        print("⚠️  Cache BẬT -> cột thời gian/token của câu hit là VÔ NGHĨA. "
              "Số chi phí Tuần 7 phải chạy --no-cache.")
    print(f"[out] {OUT.relative_to(ROOT)}\n")

    total = 0
    if "corrective" in systems:
        total += run_corrective(cfg, api_key, questions, done, meter, args)
    if "baseline" in systems:
        total += run_baseline(cfg, api_key, questions, done, meter)

    print(f"\n[xong] ghi thêm {total} bản ghi vào {OUT.relative_to(ROOT)}")
    print("Bước tiếp: python scripts/analyze_leakage.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

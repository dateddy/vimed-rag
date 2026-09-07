"""
Smoke END-TO-END — `RAGPipeline` với ĐỦ 4 thành phần THẬT.
===========================================================
Lần đầu tiên policy gate + truy hồi/rerank + generation + rewrite chạy CÙNG
NHAU. Trước script này, cả ba tầng chỉ được chứng minh riêng lẻ.

⚠️⚠️ **ĐÂY LÀ TRÌNH DIỄN, KHÔNG PHẢI PHÉP ĐO. ĐỪNG LẤY SỐ TỪ ĐÂY VÀO BÁO CÁO.**
`correct_threshold` trong `config.yaml` vẫn là **0.6**, và DEC-039 đã đo được
rằng ở ngưỡng đó **10/30 câu nhóm A/B vẫn được TRẢ LỜI**. Nghĩa là câu nhóm A
dưới đây gần như chắc chắn ra ANSWER thay vì ABSTAIN — **đó là hành vi đã biết
và đã ghi**, không phải lỗi mới. Ngưỡng thật chốt ở Tuần 6 từ đường cong
risk–coverage, bắt buộc có tập giữ lại.

Cái script này ĐO ĐƯỢC thật sự (và Tuần 7 cần):
  - độ trễ **từng tầng**: truy hồi+rerank so với LLM;
  - **token thật** mỗi lượt gọi LLM (không phải đếm ký tự rồi đoán);
  - số **lượt gọi LLM mỗi truy vấn** — câu INCORRECT tốn **2** (rewrite +
    generate), không phải 1.

CHẠY
----
  python scripts/smoke_pipeline.py

⚠️ Nạp bge-m3 + reranker (~20s một lần) rồi mỗi truy vấn ~17s rerank (DEC-042),
cộng thời gian Gemini. Cluster Qdrant free tier NGỦ sau ~2 tuần: TCP 443 mở mà
TLS reset = backend ngủ, vào console bấm resume, ĐỪNG debug .env/DNS.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.generation.generator import GeminiGenerator  # noqa: E402
from src.llm import gemini_call  # noqa: E402
from src.pipeline.grader import Grader  # noqa: E402
from src.pipeline.pipeline import RAGPipeline  # noqa: E402
from src.pipeline.rewriter import LLMRewriter  # noqa: E402
from src.retrieval.embedder import BgeM3Embedder  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402
from src.retrieval.reranker import BgeReranker  # noqa: E402
from src.retrieval.retriever import HybridRetriever  # noqa: E402


def _use_fp16(cfg) -> bool:
    """fp16 chỉ bật khi thật sự có GPU — CPU không chạy fp16."""
    try:
        import torch

        return bool(cfg.index.use_fp16 and torch.cuda.is_available())
    except ImportError:
        return False

# Mỗi câu bắt một nhánh khác nhau của `_route`.
CASES = [
    ("D", "Tôi 60kg thì uống metformin bao nhiêu viên một ngày?",
     "policy gate chặn TRƯỚC retrieval -> ABSTAIN, chunks rỗng"),
    ("E", "Biến chứng loét chân ở bệnh nhân tiểu đường có thể dẫn đến "
          "những biến chứng nguy hiểm nào?",
     "corpus CÓ tài liệu -> ANSWER kèm [n]"),
    ("A", "Thuốc Aspirin STELLA có những chỉ định điều trị nào?",
     "corpus KHÔNG có thực thể này -> ĐÁNG LẼ abstain; ở ngưỡng 0.6 "
     "nhiều khả năng vẫn ANSWER (DEC-039)"),
    # Ngoài miền hoàn toàn — ca DUY NHẤT ép được nhánh INCORRECT ở ngưỡng 0.6,
    # tức chỗ duy nhất đo được chi phí thật của REWRITE (+1 lượt gọi LLM).
    ("ngoài miền", "Cách trồng lúa nước ở đồng bằng sông Cửu Long?",
     "score rerank phải tụt hẳn -> INCORRECT -> REWRITE -> 2 lượt gọi LLM"),
]


class Meter:
    """Bọc lời gọi LLM để đếm lượt, giây và token thật."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self.reset()

    def reset(self) -> None:
        self.calls = 0
        self.seconds = 0.0
        self.prompt_tokens = 0
        self.output_tokens = 0

    def transport(self, prompt: str, temperature: float) -> str:
        usage: dict = {}
        t0 = time.perf_counter()
        out = gemini_call(
            prompt,
            temperature,
            api_key=self._api_key,
            model=self._model,
            usage_out=usage,
        )
        self.seconds += time.perf_counter() - t0
        self.calls += 1
        self.prompt_tokens += usage.get("prompt_tokens") or 0
        self.output_tokens += usage.get("output_tokens") or 0
        return out


def main() -> None:
    cfg = load_config()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit("!! Thiếu GEMINI_API_KEY (xem .env).")

    print("⚠️  TRÌNH DIỄN, KHÔNG PHẢI PHÉP ĐO — ngưỡng grader vẫn 0.6 (DEC-039).")
    print(f"    correct={cfg.grader.correct_threshold} · "
          f"incorrect={cfg.grader.incorrect_threshold} · "
          f"top_k_dense={cfg.retrieval.top_k_dense} · "
          f"rerank_max_length={cfg.retrieval.rerank_max_length}\n")

    t0 = time.perf_counter()
    fp16 = _use_fp16(cfg)
    print(f"[..] nạp bge-m3 + reranker (fp16={fp16}) + nối Qdrant …")
    meter = Meter(api_key, cfg.models.llm)
    pipe = RAGPipeline(
        cfg=cfg,
        retriever=HybridRetriever(
            cfg,
            BgeM3Embedder(cfg.models, cfg.index, use_fp16=fp16),
            collection=collection_name(cfg.qdrant.collection, 512),
            reranker=BgeReranker(
                cfg.models,
                use_fp16=fp16,
                max_length=cfg.retrieval.rerank_max_length,
            ),
        ),
        generator=GeminiGenerator(
            cfg.generation, api_key, model=cfg.models.llm,
            transport=meter.transport,
        ),
        grader=Grader(cfg.grader),
        rewriter=LLMRewriter(
            cfg.generation, api_key, model=cfg.models.llm,
            transport=meter.transport,
        ),
    )
    # Hâm nóng: lượt truy hồi ĐẦU TIÊN gánh luôn bắt tay TLS + nạp model, không
    # hâm thì bảng chi phí sai (bẫy đã ghi trong STATUS).
    pipe._retriever.retrieve("huyết áp")
    print(f"[ok] sẵn sàng sau {time.perf_counter() - t0:.1f}s\n")

    rows = []
    for group, query, expect in CASES:
        meter.reset()
        t1 = time.perf_counter()
        r = pipe.answer(query)
        total = time.perf_counter() - t1
        retrieval = total - meter.seconds

        print(f"=== nhóm {group} · {query}")
        print(f"    kỳ vọng: {expect}")
        print(f"    -> {r.action.value} · {len(r.chunks)} nguồn hiện ra "
              f"({len(r.retrieved)} chunk giữ lại cho eval — DEC-049)")
        print(f"    trace  : {[s.step for s in r.trace]}")
        print(f"    trả lời: {r.answer[:160].replace(chr(10), ' ')}…")
        print(f"    thời gian: tổng {total:.1f}s = truy hồi+rerank "
              f"{retrieval:.1f}s + LLM {meter.seconds:.1f}s "
              f"({meter.calls} lượt gọi)")
        print(f"    token  : vào {meter.prompt_tokens} · ra "
              f"{meter.output_tokens}\n")
        rows.append((group, r.action.value, total, retrieval, meter.seconds,
                     meter.calls, meter.prompt_tokens, meter.output_tokens))

    print("--- BẢNG CHI PHÍ (1 truy vấn) ---")
    print(f"{'nhóm':<5}{'action':<22}{'tổng':>7}{'truy hồi':>10}{'LLM':>7}"
          f"{'lượt':>6}{'tok vào':>9}{'tok ra':>8}")
    for g, a, tot, ret, llm, calls, pin, pout in rows:
        print(f"{g:<5}{a:<22}{tot:>6.1f}s{ret:>9.1f}s{llm:>6.1f}s"
              f"{calls:>6}{pin:>9}{pout:>8}")

    llm_rows = [r for r in rows if r[5] > 0]
    if llm_rows:
        print(f"\nTrung bình mỗi lượt gọi LLM: "
              f"{sum(r[4] for r in llm_rows) / sum(r[5] for r in llm_rows):.1f}s")
    print("\n⚠️  Nhắc lại: action ở trên là TRÌNH DIỄN ở ngưỡng 0.6, không phải "
          "kết quả abstention. Số THỜI GIAN và TOKEN thì dùng được.")


if __name__ == "__main__":
    main()

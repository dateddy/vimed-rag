"""
Smoke test tầng sinh câu trả lời — GỌI GEMINI THẬT.
====================================================
Chạy TAY, không nằm trong pytest: nó tốn quota API và cần `GEMINI_API_KEY`.
Mọi test tự động dùng transport giả (`tests/test_generation.py`).

Kiểm 4 điều mà test giả KHÔNG kiểm được, vì cả 4 phụ thuộc model thật:

  [1] Gọi được `gemini-2.5-flash` qua SDK `google-genai` (DEC-045).
  [2] Model CÓ trích dẫn `[n]` — prompt yêu cầu, nhưng yêu cầu không phải bảo đảm.
  [3] Model KHÔNG bịa `[n]` ngoài số nguồn đưa vào.
  [4] Bản `caution` thật sự mở đầu bằng cảnh báo độ chắc chắn thấp.

CHẠY
----
  python scripts/smoke_generation.py                 # ngữ cảnh giả, 2 lượt gọi
  python scripts/smoke_generation.py --real-retrieval  # truy hồi thật rồi mới sinh

⚠️ `--real-retrieval` nạp bge-m3 + reranker và đi Qdrant Cloud: ~17s/truy vấn
(DEC-042) cộng ~20s nạp model. Cluster free tier NGỦ sau ~2 tuần — TCP 443 mở mà
TLS reset nghĩa là backend ngủ, vào console bấm resume, ĐỪNG debug .env/DNS.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.generation.context import citations, invalid_citations  # noqa: E402
from src.generation.generator import GeminiGenerator  # noqa: E402
from src.schemas import RetrievedChunk  # noqa: E402

QUERY = "Người bị tăng huyết áp nên ăn uống thế nào?"

# Ngữ cảnh giả nhưng CÓ byline thật ở đoạn 1: nếu prompt không cắt, câu trả lời
# sẽ nhắc tên bác sĩ và smoke bắt được ngay.
FAKE_CHUNKS = [
    RetrievedChunk(
        doc_id="vinmec-001",
        text=(
            "Bài viết được tư vấn chuyên môn bởi Thạc sĩ, Bác sĩ Nguyễn Văn A - "
            "Khoa Nội tim mạch - Bệnh viện Đa khoa Quốc tế Vinmec Central Park. "
            "Người tăng huyết áp nên giảm muối xuống dưới 5g mỗi ngày, "
            "tăng rau xanh và trái cây tươi."
        ),
        specialty="tim_mach",
        score=0.95,
        chunk_idx=0,
        n_chunks=3,
        title="Chế độ ăn cho người tăng huyết áp",
    ),
    RetrievedChunk(
        doc_id="vinmec-002",
        text=(
            "Hạn chế rượu bia và bỏ thuốc lá giúp kiểm soát huyết áp. "
            "Nên duy trì cân nặng hợp lý và tập thể dục đều đặn 30 phút mỗi ngày."
        ),
        specialty="tim_mach",
        score=0.88,
        chunk_idx=1,
        n_chunks=4,
        title="Lối sống cho người bệnh tim mạch",
    ),
]


def real_chunks(cfg) -> list[RetrievedChunk]:
    """Truy hồi thật trên `vimed_rag_512` (nặng — chỉ khi có cờ)."""
    from src.retrieval.embedder import BgeM3Embedder
    from src.retrieval.indexer import collection_name
    from src.retrieval.reranker import BgeReranker
    from src.retrieval.retriever import HybridRetriever

    try:
        import torch

        fp16 = bool(cfg.index.use_fp16 and torch.cuda.is_available())
    except ImportError:
        fp16 = False

    print(f"[..] nạp bge-m3 + reranker (fp16={fp16}), truy hồi thật "
          f"(~20s nạp + ~17s/truy vấn)")
    retriever = HybridRetriever(
        cfg,
        BgeM3Embedder(cfg.models, cfg.index, use_fp16=fp16),
        collection=collection_name(cfg.qdrant.collection, 512),
        reranker=BgeReranker(
            cfg.models, use_fp16=fp16, max_length=cfg.retrieval.rerank_max_length
        ),
    )
    return retriever.retrieve(QUERY)


def report(label: str, answer: str, n_chunks: int) -> bool:
    cited = citations(answer)
    bad = invalid_citations(answer, n_chunks)
    print(f"\n--- {label} ---")
    print(answer)
    print(f"\n  trích dẫn: {cited or '(KHÔNG có [n])'} · bịa: {bad or 'không'}")

    ok = True

    def say(cond: bool, label_: str) -> None:
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label_}")

    say(bool(cited), "model có trích dẫn [n]")
    say(not bad, "không trích dẫn nguồn không tồn tại")
    say("Nguyễn Văn A" not in answer, "byline đã bị cắt trước khi vào prompt")
    say(
        "không thay thế tư vấn của bác sĩ" in answer,
        "có câu miễn trừ ở cuối",
    )
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--real-retrieval",
        action="store_true",
        help="truy hồi thật thay vì ngữ cảnh giả (nặng)",
    )
    args = ap.parse_args()

    cfg = load_config()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit(
            "!! Thiếu GEMINI_API_KEY. Đặt trong .env hoặc env. "
            "`setx` KHÔNG áp cho terminal đang mở — phải mở terminal mới."
        )

    chunks = real_chunks(cfg) if args.real_retrieval else FAKE_CHUNKS
    print(
        f"model {cfg.models.llm} · temperature {cfg.generation.temperature} · "
        f"{len(chunks)} nguồn"
    )

    gen = GeminiGenerator(cfg.generation, api_key, model=cfg.models.llm)

    ok = report("BẢN THƯỜNG", gen.generate(QUERY, chunks), len(chunks))
    caution = gen.generate(QUERY, chunks, caution=True)
    ok = report("BẢN CAUTION", caution, len(chunks)) and ok
    low = "độ chắc chắn thấp" in caution.lower()
    print(f"  [{'PASS' if low else 'FAIL'}] bản caution có nêu độ chắc chắn thấp")
    ok = ok and low

    print()
    if not ok:
        sys.exit("!! Có mục FAIL — xem lại prompt trong config/prompts/.")
    print("Smoke generation ĐÓNG: Gemini trả lời bám ngữ cảnh, có [n], có miễn trừ.")


if __name__ == "__main__":
    main()

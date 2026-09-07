"""
Smoke test tầng viết lại truy vấn — GỌI GEMINI THẬT.
=====================================================
Chạy TAY, không nằm trong pytest: tốn quota API và cần `GEMINI_API_KEY`.
Test tự động dùng transport giả (`tests/test_rewriter.py`).

Kiểm 3 điều mà transport giả KHÔNG kiểm được:

  [1] Model có TUÂN prompt "chỉ trả về truy vấn" không — hay thêm nhãn / giải
      thích / bọc nháy. Đây là thứ `clean_rewritten` sinh ra để chịu đựng; smoke
      này là chỗ duy nhất biết được nó phải chịu đựng bao nhiêu.
  [2] Truy vấn viết lại có KHÁC bản gốc không (viết lại y hệt = tốn 1 lượt gọi
      LLM để không được gì, và `max_iter=1` nên đó là cơ hội duy nhất bị phí).
  [3] Có rơi về fallback không.

In cả ĐẦU RA THÔ lẫn bản đã gạn, để thấy `clean_rewritten` thực sự phải làm gì.

CHẠY
----
  python scripts/smoke_rewrite.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.llm import make_transport  # noqa: E402
from src.pipeline.rewriter import LLMRewriter, clean_rewritten  # noqa: E402

# Ba kiểu truy vấn, mỗi kiểu bắt một rủi ro khác nhau.
QUERIES = [
    # Giọng đời thường, thiếu thuật ngữ — đúng ca mà rewrite sinh ra để cứu.
    "tiểu đường ăn gì",
    # Đã khá rõ: rewrite KHÔNG được làm hỏng hoặc đổi ý định.
    "Biến chứng loét chân ở bệnh nhân tiểu đường nguy hiểm thế nào?",
    # Từ vựng lệch với corpus (nói "đường huyết cao" thay vì tên bệnh).
    "đường huyết cao quá thì bị sao",
]


def main() -> None:
    cfg = load_config()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit(
            "!! Thiếu GEMINI_API_KEY. Đặt trong .env hoặc env. "
            "`setx` KHÔNG áp cho terminal đang mở — phải mở terminal mới."
        )

    print(
        f"model {cfg.models.llm} · temperature {cfg.generation.temperature} · "
        f"{len(QUERIES)} truy vấn\n"
    )

    raw_transport = make_transport(api_key, cfg.models.llm)
    ok = True
    dirty = 0

    for q in QUERIES:
        rw = LLMRewriter(cfg.generation, api_key, model=cfg.models.llm)
        raw = raw_transport(rw.build_prompt(q), cfg.generation.temperature)
        cleaned = clean_rewritten(raw, fallback=q)
        needed_cleanup = cleaned != raw.strip()
        dirty += int(needed_cleanup)

        print(f"gốc     : {q}")
        print(f"thô     : {raw!r}")
        print(f"đã gạn  : {cleaned}")

        def say(cond: bool, label: str) -> None:
            nonlocal ok
            ok = ok and cond
            print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

        say(cleaned != q, "viết lại KHÁC truy vấn gốc (không phí lượt gọi)")
        say(bool(cleaned.strip()), "không rơi về fallback")
        say("\n" not in cleaned, "đúng MỘT dòng")
        print(f"  [info] clean_rewritten có phải gạn gì không: "
              f"{'CÓ' if needed_cleanup else 'không'}\n")

    print(f"{dirty}/{len(QUERIES)} lượt cần gạn hậu xử lý.")
    if not ok:
        sys.exit("!! Có mục FAIL — xem lại config/prompts/query_rewrite.txt.")
    print("Smoke rewrite ĐÓNG: model trả truy vấn dùng được, 1 dòng, khác bản gốc.")


if __name__ == "__main__":
    main()

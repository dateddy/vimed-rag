"""
Faithfulness (RAGAS) + metric truy hồi → docs/ragas.md
======================================================
Việc (3) — việc **CUỐI** của Tuần 6 theo thứ tự DEC-015.

Đọc `data/processed/runs.jsonl`, **không chạy lại pipeline**, **không cần
Qdrant**. Có gọi API: judge Faithfulness. Kết quả được cache xuống
`data/processed/ragas_scores.json` nên chạy lại **không tốn lượt nào**.

⛔ BỐN ĐIỀU BÁO CÁO NÀY PHẢI NÓI CHO ĐÚNG — lý do đầy đủ ở `src/eval/run_ragas.py`.

* **Chỉ Faithfulness đến từ `ragas`.** 3 metric không-LLM trùng chức năng với
  `src/eval/retrieval_metrics.py` đã có; kéo thư viện về để tính lại thứ repo
  đã tính là cái trôi repo đã phải gỡ bốn lần.

* **Faithfulness TRỪNG PHẠT câu từ chối đúng bằng 0,0** (đo thật, không suy
  đoán). Nên **không bao giờ** lấy trung bình trên toàn bộ câu — mẫu số là câu
  có phát biểu thực chất, câu từ chối tách ra đếm riêng.

* **Faithfulness đo "bám ngữ cảnh", KHÔNG đo "đúng".** Đừng để nó gánh claim
  "% giảm hallucination"; dụng cụ đúng cho việc đó là `leaked`,
  `invalid_citations` và nhãn tay 6/30.

* **Nhánh LLM-only được chấm bằng ngữ cảnh MƯỢN** của nhánh corrective (nó
  không truy hồi nên tự nó không có ngữ cảnh nào). Đó là cách dùng phi tiêu
  chuẩn và bảng phải gọi tên nó.

CHẠY
----
  python scripts/build_ragas_report.py              # dùng cache nếu có
  python scripts/build_ragas_report.py --refresh    # chấm lại, TỐN lượt API
  python scripts/build_ragas_report.py --limit 3    # thử vài câu cho rẻ
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.arms import ARM_LABEL, answered_at_turn1, arm_records  # noqa: E402
from src.eval.stats import sign_test  # noqa: E402
from src.eval.run_ragas import (  # noqa: E402
    DEFAULT_JUDGE_MODEL,
    is_refusal_text,
    make_openrouter_judge,
    paired_comparison,
    retrieval_metrics,
    score_records,
)

RUNS = ROOT / "data" / "processed" / "runs.jsonl"
CACHE = ROOT / "data" / "processed" / "ragas_scores.json"
OUT = ROOT / "docs" / "ragas.md"

THIEU_RUNS = f"""\
!! Thiếu {RUNS.relative_to(ROOT)} — file này bị gitignore (đúng thiết kế).

   Dựng lại:  python scripts/export_runs.py      (~45 phút, tốn lượt API)

   Báo cáo đã sinh thì ĐÃ được commit ở docs/ragas.md — mở file đó nếu bạn chỉ
   cần đọc số, không cần chạy lại.
"""


def nap_env() -> None:
    """Nạp `.env` bằng tay — repo không dùng python-dotenv."""
    p = ROOT / ".env"
    if not p.exists():
        return
    for dong in p.read_text(encoding="utf-8").splitlines():
        dong = dong.strip()
        if dong and not dong.startswith("#") and "=" in dong:
            k, v = dong.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def judge_co_cache(judge, cache: dict, model: str, *, cache_only: bool = False):
    """Bọc judge bằng cache trên đĩa — chạy lại không tốn lượt nào.

    Khoá gồm **tên model**: đổi judge mà dùng lại điểm của judge cũ thì bảng sẽ
    trộn hai phép đo dưới một cái tên.

    ``cache_only=True`` thì **không gọi API bao giờ**: câu chưa có trong cache
    bị bỏ qua (judge trả `None`) thay vì đi hỏi. Sinh ra vì lô đầu tiên
    chết giữa chừng ở **403 Key limit exceeded** sau 28/76 câu — khi credit là
    thứ khan hiếm thì phải đọc được phần đã trả tiền mà không trả thêm lần nữa.
    """
    def bao(user_input: str, response: str,
            contexts: list[str]) -> float | None:
        # ⚠️ sha256, KHÔNG `hash()`: `hash()` của chuỗi bị salt theo tiến trình
        # (PYTHONHASHSEED) nên cache sẽ miss SẠCH ở lần chạy sau — tức đúng
        # cái nó sinh ra để tránh. Cùng cách làm với `LlmCache.key`.
        thô = json.dumps([model, user_input, response, contexts],
                         ensure_ascii=False, sort_keys=True)
        k = hashlib.sha256(thô.encode("utf-8")).hexdigest()[:32]
        if k in cache:
            return float(cache[k])
        if cache_only:
            return None      # chưa chấm được — KHÔNG phải điểm 0
        v = float(judge(user_input, response, contexts))
        cache[k] = v
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        return v

    return bao


def bang_faith(s, nhan: str) -> list[str]:
    tb = s.mean_faithfulness
    tb_txt = "—" if tb is None else f"**{tb:.3f}**"
    L = [
        f"### {nhan}",
        "",
        "| | số câu | faithfulness |",
        "|---|---|---|",
        f"| **câu có phát biểu thực chất — SỐ CHÍNH** | {len(s.substantive)} | {tb_txt} |",
        f"| câu từ chối (tách ra, KHÔNG vào trung bình) | {len(s.refusals)} | *không áp dụng* |",
        f"| tổng đã chấm | {len(s.rows)} | |",
        "",
    ]
    if s.refusals:
        ids = ", ".join(f"`{r.id}`" for r in s.refusals)
        L += [f"Câu từ chối: {ids}.", ""]
    return L


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="bỏ cache, chấm lại từ đầu (TỐN lượt API)")
    ap.add_argument("--limit", type=int, default=0,
                    help="chỉ chấm N câu đầu mỗi nhánh (để thử cho rẻ)")
    ap.add_argument("--model", default=DEFAULT_JUDGE_MODEL)
    ap.add_argument("--cache-only", action="store_true",
                    help="CHỈ đọc điểm đã cache, KHÔNG gọi API lượt nào")
    args = ap.parse_args()

    if not RUNS.exists():
        print(THIEU_RUNS)
        return 1

    nap_env()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("!! Thiếu GEMINI_API_KEY (xem .env). Đây cũng là key OpenRouter —")
        print("   tên biến là dấu tích lịch sử từ trước DEC-054, chưa đổi tên.")
        return 1

    records = [json.loads(l) for l in RUNS.open(encoding="utf-8")]
    cache = {} if args.refresh or not CACHE.exists() else json.loads(
        CACHE.read_text(encoding="utf-8"))

    # `--cache-only` thì không dựng judge thật -> không cần cả ragas lẫn key.
    that = (lambda *a: 0.0) if args.cache_only else make_openrouter_judge(
        api_key, args.model)
    judge = judge_co_cache(that, cache, args.model, cache_only=args.cache_only)

    # ---- nhánh ĐANG CHẠY THẬT: corrective + guard lượt 2 (DEC-061)
    corr = arm_records(records, "corrective_t1")
    tra_loi = [r for r in corr if answered_at_turn1(r)]
    if args.limit:
        tra_loi = tra_loi[: args.limit]
    print(f"[1] {ARM_LABEL['corrective_t1']}: {len(tra_loi)} câu đã trả lời")
    s_corr = score_records(tra_loi, judge, arm="corrective_t1")
    if s_corr.unscored:
        print(f"    ⚠️ {len(s_corr.unscored)} câu CHƯA CHẤM ĐƯỢC: {s_corr.unscored}")

    # ---- nhánh LLM-only: mượn ngữ cảnh của nhánh corrective cho CÙNG câu hỏi
    ctx = {
        r["id"]: [c["text"] for c in r.get("retrieved") or []]
        for r in corr
    }
    base = arm_records(records, "llm_only")
    if args.limit:
        base = base[: args.limit]
    print(f"[2] {ARM_LABEL['llm_only']}: {len(base)} câu (ngữ cảnh MƯỢN)")
    s_base = score_records(base, judge, arm="llm_only", contexts_by_id=ctx)
    if s_base.unscored:
        print(f"    ⚠️ {len(s_base.unscored)} câu CHƯA CHẤM ĐƯỢC")

    # ---- metric truy hồi: KHÔNG qua ragas
    rm = retrieval_metrics(corr)

    # ------------------------------------------------------------- báo cáo
    L: list[str] = []
    L.append("# RAGAS — Faithfulness + metric truy hồi\n")
    L.append("> Sinh bởi `python scripts/build_ragas_report.py`. "
             "Đọc `data/processed/runs.jsonl`, không chạy lại pipeline.\n")
    L.append(f"Judge: **`{args.model}`**, `temperature=0` (DEC-023). "
             "Khác họ với generator `google/gemini-2.5-flash` — đó là cả mục "
             "đích: judge cùng họ với thứ nó chấm thì phép đo mất tính độc lập.\n")

    L.append("## ⚠️ Đọc bảng này thế nào cho đúng\n")
    L.append("**Faithfulness trừng phạt câu từ chối đúng bằng điểm 0,0.** Đo "
             "thật, không suy đoán: `E-01` (trả lời thật, có trích dẫn) ra "
             "**0,70**, còn `E-21` (*“Ngữ cảnh không chứa thông tin về…”*) ra "
             "**0,00**. Lý do: RAGAS tách lời từ chối thành một **phát biểu "
             "siêu ngôn ngữ về ngữ cảnh** rồi hỏi ngữ cảnh có suy ra được nó "
             "không — không. Nên hành vi **đúng** của hệ thống này nhận điểm "
             "thấp nhất có thể.\n")
    L.append("→ Vì thế bảng dưới **không có** dòng “trung bình toàn bộ”. Lấy "
             "trung bình trên tất cả thì hệ càng an toàn điểm càng thấp, và "
             "bảng sẽ nói ngược sự thật.\n")
    L.append("⚠️ **Faithfulness đo “bám ngữ cảnh”, KHÔNG đo “đúng”.** Nhánh "
             "corrective phần lớn là từ chối nên điểm đẹp vì một lý do chán. "
             "**Đừng để metric này gánh claim “% giảm hallucination”** — dụng "
             "cụ đúng cho việc đó là cờ `leaked`, `invalid_citations`, và nhãn "
             "tay 6/30 của `review_static_leaks.py`.\n")

    L.append("## Faithfulness\n")
    L += bang_faith(s_corr, ARM_LABEL["corrective_t1"])
    L += bang_faith(s_base, ARM_LABEL["llm_only"] + " — ngữ cảnh **MƯỢN**")
    L.append("⚠️ **Nhánh LLM-only được chấm bằng ngữ cảnh mượn.** Nó không "
             "truy hồi nên tự nó không có ngữ cảnh nào; bảng đưa vào đúng các "
             "đoạn mà nhánh corrective lấy được cho **cùng câu hỏi đó**. Phép "
             "đo vì thế đọc là *“câu trả lời không-truy-hồi này có được chống "
             "đỡ bởi bằng chứng tốt nhất corpus đưa ra được không”* — **không "
             "phải** cùng một phép đo với dòng trên. Không nói ra thì người "
             "đọc sẽ hiểu thành hai nhánh được chấm như nhau.\n")

    # ---------------------------------------------- so sánh CẶP, không so rời
    pc = paired_comparison(s_corr, s_base)
    L.append("## So sánh hai nhánh — GHÉP CẶP trên cùng bộ câu\n")
    if pc["n"] == 0:
        L.append("⚠️ **Chưa ghép cặp được câu nào** — hai nhánh chưa có câu nào "
                 "cùng được chấm. Xem mục tình trạng ở cuối.\n")
    else:
        neg, pos, pval = sign_test(pc["diffs"])
        L.append(f"Mẫu ghép cặp: **{pc['n']} câu** cả hai nhánh đều có điểm "
                 "**và** đều có phát biểu thực chất.\n")
        L.append("| nhánh | faithfulness trên mẫu ghép cặp |")
        L.append("|---|---|")
        L.append(f"| {ARM_LABEL['corrective_t1']} | **{pc['mean_a']:.3f}** |")
        L.append(f"| {ARM_LABEL['llm_only']} (ngữ cảnh mượn) | **{pc['mean_b']:.3f}** |")
        L.append(f"| **chênh lệch** | **{pc['delta']:+.3f}** |")
        L.append("")
        L.append(f"Kiểm định dấu: **{neg} câu corrective thấp hơn · {pos} câu "
                 f"cao hơn · p = {pval:.4f}**. Dùng kiểm định dấu chứ không "
                 "t-test — n nhỏ và phân bố faithfulness không rõ dạng, cùng "
                 "lý do đã ghi ở DEC-055.\n")
        L.append("⚠️⚠️ **ĐỪNG so hai trung bình rời ở hai bảng trên.** Chúng "
                 "đứng trên hai tập câu khác nhau (lô chấm dừng giữa chừng ở "
                 "403), nên hiệu của chúng **không phải** là hiệu ứng. Chỉ "
                 "bảng ghép cặp này mới đọc được.\n")

    L.append("## B4 — hai máy dò câu “ANSWER nhưng nội dung là từ chối”\n")
    L.append("Hai phép dò **độc lập** với nhau: một quét văn bản "
             "(`is_refusal_text`), một đọc điểm (`faithfulness == 0`).\n")
    L.append(f"- theo văn bản: {[r.id for r in s_corr.refusals]}")
    L.append(f"- theo điểm 0: {s_corr.zero_scored_ids}")
    lech = s_corr.disagreement()
    L.append(f"- **lệch nhau**: {lech or '— (hai máy dò khớp hoàn toàn)'}\n")
    if lech:
        L.append("⚠️ Lệch **không** tự động là lỗi: một câu trả lời thật nhưng "
                 "bịa hoàn toàn cũng ra 0,0 mà không phải lời từ chối. Danh "
                 "sách này chỉ **chỉ chỗ để soi tay**.\n")

    if rm:
        L.append("## Metric truy hồi — tính bằng `retrieval_metrics.py`, KHÔNG bằng ragas\n")
        L.append("3 metric không-LLM mà backlog gọi là “của RAGAS” "
                 "(`NonLLMContextRecall`, `NonLLMContextPrecisionWithReference`, "
                 "`IDBasedContextPrecision`) **trùng chức năng** với module đã "
                 "có sẵn trong repo và đã được test phủ. Dùng lại module đó.\n")
        L.append(f"Mẫu số: **{int(rm.pop('n_queries'))} câu nhóm E** — chỉ nhóm "
                 "E có `reference_context_ids`. Câu không có đáp án vàng bị "
                 "**bỏ qua**, không tính là 0: tính 0 cho câu vốn không có "
                 "ground truth là bịa ra một thất bại không tồn tại.\n")
        L.append("| metric | giá trị |")
        L.append("|---|---|")
        for k in sorted(rm):
            L.append(f"| `{k}` | {rm[k]:.3f} |")
        L.append("")

    L.append("## ⚠️ Tình trạng chấm\n")
    tong_c = len(s_corr.rows) + len(s_corr.unscored)
    tong_b = len(s_base.rows) + len(s_base.unscored)
    L.append("| nhánh | đã chấm | chưa chấm |")
    L.append("|---|---|---|")
    L.append(f"| {ARM_LABEL['corrective_t1']} | {len(s_corr.rows)}/{tong_c} "
             f"| {len(s_corr.unscored)} |")
    L.append(f"| {ARM_LABEL['llm_only']} | {len(s_base.rows)}/{tong_b} "
             f"| {len(s_base.unscored)} |")
    L.append("")
    if s_corr.unscored or s_base.unscored:
        L.append("⛔ **Lô chấm CHƯA XONG.** Lần chạy đầu dừng ở `403 Key limit "
                 "exceeded` của OpenRouter sau 28 lượt — đúng rủi ro "
                 "`STATUS.md` đã ghi (*“hết tiền là 402, cùng hậu quả với "
                 "429”*). Điểm đã chấm nằm trong cache, nên nâng hạn mức key "
                 "rồi chạy lại thì **chỉ tốn phần còn thiếu**.\n")
        L.append("⚠️ Câu chưa chấm **KHÔNG** được tính là 0 — `None` và `0.0` "
                 "là hai thứ khác hẳn nhau (`0.0` là phán quyết *“không claim "
                 "nào được chống đỡ”*; chưa chấm là *không có phán quyết*). "
                 "Chúng nằm ngoài mọi mẫu số ở trên.\n")

    L.append("## Tái lập\n")
    L.append("```\npython scripts/build_ragas_report.py\n```\n")
    L.append("Điểm judge được cache ở `data/processed/ragas_scores.json` "
             "(gitignore) nên chạy lại **không tốn lượt API nào**. `--refresh` "
             "để chấm lại từ đầu.\n")
    L.append("⚠️ `ragas==0.4.3` **không chạy được** với `langchain-community` "
             "0.4.x — nó import `langchain_community.chat_models.vertexai`, API "
             "đã bị gỡ. Phải pin lùi; xem `requirements-eval.txt`.\n")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    tb = s_corr.mean_faithfulness
    print(f"   corrective_t1: {len(s_corr.substantive)} câu thực chất, "
          f"faithfulness {'—' if tb is None else f'{tb:.3f}'}")
    tb2 = s_base.mean_faithfulness
    print(f"   llm_only     : {len(s_base.substantive)} câu thực chất, "
          f"faithfulness {'—' if tb2 is None else f'{tb2:.3f}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

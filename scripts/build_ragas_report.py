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
  # đọc phần đã chấm, KHÔNG gọi API lượt nào — chạy cái này trước
  python scripts/build_ragas_report.py --cache-only

  # CHẠY TIẾP phần còn thiếu, rẻ nhất có thể (khuyến nghị)
  python scripts/build_ragas_report.py --pairable-only

  python scripts/build_ragas_report.py              # dùng cache, chấm nốt TẤT CẢ
  python scripts/build_ragas_report.py --refresh    # chấm LẠI từ đầu, TỐN nhất
  python scripts/build_ragas_report.py --limit 3    # thử vài câu cho rẻ

⚠️ **CHI PHÍ ĐO ĐƯỢC, KHÔNG PHẢI ƯỚC LƯỢNG:** 28 câu đầu tốn **$3,17** trên
OpenRouter → **~$0,11/câu** với `openai/gpt-5`. Đó là model **suy luận**, nên
nó đốt token vào reasoning trước khi phát JSON và mất ~100 giây/câu. Lô đầu
tiên **chết ở `403 Key limit exceeded`** vì hạn mức key là $3.

`--pairable-only` đưa nhánh LLM-only từ 59 câu xuống còn **đúng tập ghép cặp
được** — và tập bị cắt là tập mà `paired_comparison()` **vốn đã bỏ**, nên
không mất một thông tin nào. Xem lý do đầy đủ ngay tại chỗ dùng cờ này.

Mã thoát: **2** nếu lô chấm còn dở. Một lô dở mà exit 0 là lô nói dối.
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

    Trả về ``(judge_đã_bọc, hong)`` — ``hong`` là list rỗng, và nó **có phần
    tử** nếu lô phải dừng gọi API giữa chừng. Trả ra thay vì in rồi quên, để
    `main()` đặt được mã thoát đúng: một lô chấm dở mà exit 0 là lô nói dối.
    """
    hong: list[Exception] = []
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
        if cache_only or hong:
            return None      # chưa chấm được — KHÔNG phải điểm 0
        try:
            v = float(judge(user_input, response, contexts))
        except Exception as e:                                  # noqa: BLE001
            # ⛔ HẾT CREDIT / BỊ CHẶN THÌ DỪNG GỌI, ĐỪNG VỠ CẢ LÔ.
            # Lần chạy đầu (2026-09-11) chết thành traceback giữa chừng ở
            # `403 Key limit exceeded` — cache vẫn giữ được 28 điểm nhờ ghi
            # từng câu, nhưng báo cáo thì không sinh ra nổi. Nay: ghi nhận
            # lỗi MỘT lần, tắt công tắc, để mọi câu sau trả None ngay (không
            # gọi thêm, không tốn thêm), và lô vẫn chạy hết để sinh báo cáo
            # trên phần đã có.
            hong.append(e)
            print(f"\n⛔ DỪNG GỌI API: {type(e).__name__}: {str(e)[:200]}\n")
            return None
        cache[k] = v
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        return v

    return bao, hong


def canh_bao_hai_trung_binh(con_thieu: bool) -> str:
    """Câu đứng dưới bảng ghép cặp — **phụ thuộc lô chấm xong hay chưa**.

    ⛔ ISSUE-073. Bản trước in câu cảnh báo *"hai trung bình rời đứng trên hai
    tập câu khác nhau"* **vô điều kiện**. Nó đúng chừng nào còn câu chưa chấm;
    lô chấm xong thì hai trung bình rời **trùng** hai trung bình ghép cặp, và
    câu ấy thành lời nói dối về chính tài liệu chứa nó — trong khi bảng
    "Tình trạng chấm" ở cuối cùng file lại nói ngược lại.

    Tách thành hàm thuần để điều kiện này **kiểm được bằng test**, không phải
    bằng việc đọc lại script. Đây là lần thứ hai repo gặp đúng lỗi này
    (ISSUE-071: worksheet hard-code một câu đã thành sai).
    """
    if con_thieu:
        return ("⚠️⚠️ **ĐỪNG so hai trung bình rời ở hai bảng trên.** Chúng "
                "đứng trên hai tập câu khác nhau (lô chấm dừng giữa chừng), "
                "nên hiệu của chúng **không phải** là hiệu ứng. Chỉ bảng ghép "
                "cặp này mới đọc được.\n")
    return ("✅ **Lô chấm đã xong**, nên hai bảng trên đứng trên đúng bộ câu "
            "của bảng ghép cặp này — ba con số khớp nhau là vì thế, không "
            "phải trùng hợp.\n")


def lenh_tai_lap(*, pairable_only: bool, model: str, limit: int) -> str:
    """Lệnh **thật sự** đã sinh ra tài liệu, không phải một chuỗi cố định.

    ⛔ ISSUE-074. Nội dung báo cáo phụ thuộc cờ: thiếu ``--pairable-only`` thì
    nhánh LLM-only nở từ tập ghép cặp ra toàn bộ 59 câu — mẫu số mọi bảng đổi
    theo, **và** script đi gọi API thật cho phần chênh (đo được: ~$0,11/câu).
    Một tài liệu ghi sai lệnh sinh ra chính nó thì không tái lập được.

    Chỉ liệt kê cờ **đổi nội dung**. ``--cache-only`` cố tình KHÔNG vào đây:
    nó chặn gọi API chứ không đổi con số nào đã có.
    """
    lenh = ["python scripts/build_ragas_report.py"]
    if pairable_only:
        lenh.append("--pairable-only")
    if model != DEFAULT_JUDGE_MODEL:
        lenh.append(f"--model {model}")
    if limit:
        lenh.append(f"--limit {limit}")
    return " ".join(lenh)


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
    ap.add_argument("--pairable-only", action="store_true",
                    help="nhánh LLM-only: CHỈ chấm câu ghép cặp được "
                         "(48 câu -> 10). Xem docstring để biết vì sao rẻ mà "
                         "không mất thông tin nào")
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
    judge, hong = judge_co_cache(that, cache, args.model,
                                 cache_only=args.cache_only)

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
    if args.pairable_only:
        # Chỉ giữ câu GHÉP CẶP ĐƯỢC — tức câu nhánh corrective cũng có phát
        # biểu thực chất. Đưa 48 câu còn thiếu xuống còn 10.
        #
        # ⚠️ VÌ SAO KHÔNG MẤT THÔNG TIN NÀO, chứ không phải cắt cho rẻ:
        #  - 30 câu A/B: nhánh corrective TỪ CHỐI HẾT (leakage 0/30), nên không
        #    có gì để ghép cặp. Và chấm faithfulness câu LLM-only nói về thực
        #    thể VẮNG MẶT khỏi corpus, đối chiếu với ngữ cảnh MƯỢN từ corpus,
        #    thì ra ~0 **theo cấu tạo** — đúng loại tautology DEC-051 đã cảnh
        #    báo, và DEC-061 gặp lại ở "cách vá (4)".
        #  - Câu nhánh corrective từ chối (`E-21`) cũng không ghép cặp được:
        #    lời từ chối không có claim nào để chấm.
        # Nên tập bị cắt là tập mà `paired_comparison()` **vốn đã bỏ**.
        ghep = {r.id for r in s_corr.substantive}
        base = [r for r in base if r["id"] in ghep]
    if args.limit:
        base = base[: args.limit]
    print(f"[2] {ARM_LABEL['llm_only']}: {len(base)} câu (ngữ cảnh MƯỢN)"
          + (" — CHỈ câu ghép cặp được" if args.pairable_only else ""))
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
        # Gắn vào `unscored` chứ không in vô điều kiện — cùng cơ chế mà khối
        # "Lô chấm CHƯA XONG" ở cuối file đã làm đúng. Lý do: ISSUE-073.
        L.append(canh_bao_hai_trung_binh(
            bool(s_corr.unscored or s_base.unscored)))

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
    if args.pairable_only:
        L.append("Chạy với `--pairable-only`: nhánh LLM-only **chỉ chấm câu ghép "
                 "cặp được** — tức câu mà nhánh corrective cũng có phát biểu "
                 "thực chất.\n")
        L.append("**Tập bị cắt là tập `paired_comparison()` vốn đã bỏ**, nên "
                 "không mất thông tin nào: (a) 30 câu A/B — nhánh corrective "
                 "**từ chối hết** (leakage 0/30) nên không có gì ghép cặp, và "
                 "chấm faithfulness một câu LLM-only nói về thực thể **vắng "
                 "mặt khỏi corpus** đối chiếu với ngữ cảnh **mượn từ corpus** "
                 "thì ra ~0 **theo cấu tạo** — đúng loại tautology DEC-051 đã "
                 "cảnh báo và DEC-061 gặp lại ở *cách vá (4)*; (b) câu nhánh "
                 "corrective từ chối (`E-21`) không có claim nào để chấm.\n")

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
    # In lại ĐÚNG cờ đã sinh ra tài liệu này, không in chuỗi cố định (ISSUE-074).
    L.append("```\n" + lenh_tai_lap(pairable_only=args.pairable_only,
                                    model=args.model,
                                    limit=args.limit) + "\n```\n")
    if args.pairable_only:
        L.append("⚠️ **Cờ `--pairable-only` là một phần của lệnh, không phải "
                 "tuỳ chọn cho nhanh.** Bỏ nó ra thì nhánh LLM-only nở từ "
                 "**16 câu ghép cặp** lên **51 câu**, mẫu số mọi bảng đổi "
                 "theo, và script gọi API thật cho phần chênh.\n")
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

    thieu = len(s_corr.unscored) + len(s_base.unscored)
    if hong:
        print(f"\n⛔ LÔ CHẤM DỪNG GIỮA CHỪNG — còn {thieu} câu chưa chấm.")
        print(f"   Nguyên nhân: {type(hong[0]).__name__}")
        print("   Điểm đã chấm ĐÃ được giữ trong cache (ghi từng câu), nên")
        print("   chạy lại sau khi gỡ nguyên nhân chỉ tốn đúng phần còn thiếu.")
        print("\n   Kiểm hạn mức key OpenRouter:")
        print("     curl -H \"Authorization: Bearer $KEY\" "
              "https://openrouter.ai/api/v1/key")
        print("   Nâng hạn mức: https://openrouter.ai/workspaces/default/keys")
        # ⚠️ Mã thoát KHÁC 0: một lô chấm dở mà exit 0 là lô nói dối, và
        # `docs/ragas.md` sẽ âm thầm mang số của một mẫu nhỏ hơn ta tưởng.
        return 2
    if thieu and not args.cache_only:
        print(f"\n⚠️ Còn {thieu} câu chưa chấm (không phải do lỗi API).")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

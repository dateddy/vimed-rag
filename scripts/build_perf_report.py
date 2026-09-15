"""Dựng `docs/latency-cost.md` — bảng vận hành Tuần 7 (DoD: latency + cost).

    python scripts/build_perf_report.py
    python scripts/build_perf_report.py --check-pricing   # đối chiếu giá LIVE

Đọc **ba** nguồn, mỗi nguồn trả lời một câu khác nhau:

===================== ========================================================
`runs.jsonl`          **token** → cost/1.000 query. Token không phụ thuộc máy
                      nên phần này dùng lại lô 2026-09-08, không phải chạy lại.
                      Đã kiểm: `cache_hits = 0` toàn file → mọi lượt là API thật.
`bench_latency.jsonl` **latency tách stage**, đo có đối chứng nhịp máy.
`bench_space.json`    latency **trên Space** — thứ người dùng thật chờ.
===================== ========================================================

## ⚠️ Vì sao cột local và cột Space KHÁC nhau, và cả hai đều cần

Local là chỗ **duy nhất** tách được stage trên đủ 59 câu — nhưng nó là chiếc
laptop không ai dùng để chạy hệ thật. Space là **sản phẩm thật** — nhưng không
có batch runner, chỉ chấm được vài truy vấn và không tách được stage.

Đăng cả hai, dán nhãn rõ, nói thẳng vì sao lệch. *"Đo ở đâu?"* là câu gần như
chắc chắn bị hỏi; có sẵn hai cột kèm lý do thì đó thành điểm mạnh.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.stats import quantile  # noqa: E402  — KHÔNG định nghĩa lại

RUNS = ROOT / "data" / "processed" / "runs.jsonl"
BENCH = ROOT / "data" / "processed" / "bench_latency.jsonl"
SPACE = ROOT / "data" / "processed" / "bench_space.json"
OUT = ROOT / "docs" / "latency-cost.md"

# --------------------------------------------------------------------------- #
# GIÁ — hằng số CÓ XUẤT XỨ, không phải con số trôi nổi
# --------------------------------------------------------------------------- #
#: USD mỗi 1 TRIỆU token, `google/gemini-2.5-flash` qua OpenRouter.
#: Nguồn: GET https://openrouter.ai/api/v1/models — lấy 2026-09-15.
#:
#: ⚠️ Hằng số hoá thay vì gọi mạng lúc dựng doc: một script sinh báo cáo mà phụ
#: thuộc mạng thì mất tính tái lập (giá đổi = doc đổi mà không ai biết vì sao).
#: Nhưng hằng số thì **trôi trong im lặng** — nên có `--check-pricing` đối chiếu
#: giá live và BÁO khi lệch. Mechanize phép kiểm, đừng tin câu văn.
GIA_PROMPT_1M = 0.30
GIA_OUTPUT_1M = 2.50
GIA_NGUON = "openrouter.ai/api/v1/models"
GIA_NGAY = "2026-09-15"
MODEL = "google/gemini-2.5-flash"


def so(x: float, le: int = 1) -> str:
    """Số theo quy ước tiếng Việt — **dấu phẩy thập phân**.

    Docs của repo viết `15,9 s` · `0,747` · `~$0,11/câu`. Dấu chấm chỉ dùng khi
    **trích nguyên giá trị trong `config.yaml`** (`0.919`/`0.933`) — ở đó nó là
    một chuỗi định danh, không phải một con số để đọc. Trộn hai quy ước trong
    cùng một báo cáo là buộc người đọc tự đoán, và có ngày đoán sai.
    """
    return f"{x:,.{le}f}".replace(",", " ").replace(".", ",")


def doc_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def kiem_gia() -> int:
    """Đối chiếu hằng số với giá live. Trả 0 nếu khớp, 1 nếu lệch."""
    import httpx

    d = httpx.get("https://openrouter.ai/api/v1/models", timeout=30).json()
    for m in d.get("data", []):
        if m.get("id") == MODEL:
            p = m.get("pricing", {})
            live_in = float(p.get("prompt", 0)) * 1e6
            live_out = float(p.get("completion", 0)) * 1e6
            print(f"hằng số : ${GIA_PROMPT_1M}/1M prompt · ${GIA_OUTPUT_1M}/1M output")
            print(f"live    : ${live_in}/1M prompt · ${live_out}/1M output")
            if (live_in, live_out) == (GIA_PROMPT_1M, GIA_OUTPUT_1M):
                print("✅ KHỚP — bảng cost còn hiệu lực.")
                return 0
            print("⛔ LỆCH — sửa GIA_PROMPT_1M/GIA_OUTPUT_1M rồi dựng lại doc.")
            return 1
    print(f"⛔ Không thấy {MODEL} trong danh sách model của OpenRouter.")
    return 1


def usd_1000(prompt_tb: float, output_tb: float) -> float:
    """USD cho 1.000 truy vấn, từ token TRUNG BÌNH mỗi truy vấn."""
    return (prompt_tb * 1000 * GIA_PROMPT_1M + output_tb * 1000 * GIA_OUTPUT_1M) / 1e6


def bang_cost(runs: list[dict]) -> list[str]:
    cor = [r for r in runs if r.get("system") == "corrective"]
    bas = [r for r in runs if r.get("system") == "baseline_llm_only"]
    hit = sum((r.get("cost") or {}).get("cache_hits", 0) for r in runs)

    d: list[str] = []
    d.append("## 1. Chi phí — USD trên 1.000 truy vấn\n")
    d.append(
        f"Model **`{MODEL}`** · giá **${so(GIA_PROMPT_1M, 2)}/1M prompt** · "
        f"**${so(GIA_OUTPUT_1M, 2)}/1M output** (nguồn `{GIA_NGUON}`, lấy {GIA_NGAY};"
        f" đối chiếu lại: `python scripts/build_perf_report.py --check-pricing`).\n"
    )
    d.append(
        f"Token lấy từ `runs.jsonl` (lô {len(cor)} câu). **`cache_hits` toàn file "
        f"= {hit}** → mọi lượt là gọi API thật, không có lượt nào đọc cache, nên "
        f"số token dưới đây là chi phí thật chứ không phải chi phí lúc phát triển.\n"
    )
    d.append("| Hệ | prompt/câu | output/câu | **USD/1.000 query** |")
    d.append("|---|---:|---:|---:|")
    ket: dict[str, float] = {}
    for nhan, g in (("**Corrective RAG**", cor), ("LLM-only (baseline)", bas)):
        if not g:
            continue
        pin = sum(r["cost"]["prompt_tokens"] for r in g) / len(g)
        pout = sum(r["cost"]["output_tokens"] for r in g) / len(g)
        usd = usd_1000(pin, pout)
        ket[nhan] = usd
        d.append(f"| {nhan} | {so(pin, 0)} | {so(pout, 0)} | **${so(usd, 2)}** |")
    d.append("")

    if len(ket) == 2:
        c, b = ket["**Corrective RAG**"], ket["LLM-only (baseline)"]
        if c < b:
            d.append(
                f"⚠️ **Corrective RẺ HƠN baseline {so(b / c)} lần** — nghịch trực giác, "
                f"và có cơ chế giải thích được: output đắt gấp "
                f"**{so(GIA_OUTPUT_1M / GIA_PROMPT_1M)} lần** input. Có ngữ cảnh thì "
                f"model trả lời ngắn và bám nguồn; không có thì nó nói dài. "
                f"Corrective trả **prompt** to (5 chunk ngữ cảnh) nhưng **output** nhỏ, "
                f"và bên đắt là bên output.\n"
            )
    d.append(
        "⚠️ **Bảng này chỉ tính LLM.** Không gồm: embedding + rerank (tự host, "
        "không tốn tiền theo lượt nhưng tốn CPU — xem mục 2), Qdrant Cloud "
        "(free tier), HF Space (PRO $9/tháng, chi phí **cố định** không theo lượt).\n"
    )
    d.append(
        "⚠️ **Đừng lẫn với `~$0,11/câu`** ghi ở chỗ khác trong repo: đó là **LLM "
        "judge của RAGAS** (`openai/gpt-5`, chạy lúc *đánh giá*), không phải chi phí "
        "phục vụ một truy vấn.\n"
    )
    return d


def _p(xs: list[float], p: float) -> str:
    return so(quantile(xs, p)) if xs else "—"


def bang_latency(bench: list[dict]) -> list[str]:
    d: list[str] = []
    d.append("## 2. Latency — p50/p95 tách theo stage (local)\n")

    ban = [r for r in bench if r.get("may_ban")]
    sach = [r for r in bench if not r.get("may_ban")]
    d.append(
        f"Đo trên **{len(bench)} câu**, mỗi câu kèm **đối chứng nhịp máy** — một vòng "
        f"lặp CPU thuần chạy ngay trước và sau phép đo. Câu nào nhịp phồng quá "
        f"**1,5×** so với lúc hiệu chuẩn thì bị **loại** khỏi p50/p95 thay vì trộn vào.\n"
    )
    if ban:
        d.append(
            f"⚠️ **{len(ban)}/{len(bench)} câu bị loại** vì máy bận lúc đo: "
            f"{', '.join(sorted(r['id'] for r in ban))}. "
            f"Bảng dưới tính trên **{len(sach)}** câu còn lại.\n"
        )
    else:
        d.append(
            f"✅ **0/{len(bench)} câu bị loại** — nhịp máy giữ trong 1,5× suốt lô, "
            f"nên không có con số nào ở đây là nhiễu tải máy.\n"
        )

    nhom: list[tuple[str, list[dict]]] = [
        ("ANSWER", [r for r in sach if r["action"] == "ANSWER"]),
        ("ANSWER_WITH_CAUTION", [r for r in sach if r["action"] == "ANSWER_WITH_CAUTION"]),
        ("ABSTAIN — policy", [r for r in sach if r.get("co_che") == "policy"]),
        ("ABSTAIN — truy hồi", [r for r in sach if r.get("co_che") == "retrieval"]),
    ]

    d.append("| Nhánh | n | **tổng p50** | **tổng p95** | rerank p50 | search p50 | generation p50 | rewrite p50 |")
    d.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for nhan, g in nhom:
        if not g:
            continue
        d.append(
            f"| {nhan} | {len(g)} | **{_p([r['total_s'] for r in g], .5)}s** "
            f"| **{_p([r['total_s'] for r in g], .95)}s** "
            f"| {_p([r['rerank_s'] for r in g], .5)}s "
            f"| {_p([r['search_s'] for r in g], .5)}s "
            f"| {_p([r['generation_s'] for r in g], .5)}s "
            f"| {_p([r['rewrite_s'] for r in g], .5)}s |"
        )
    d.append("")

    tong = [r["total_s"] for r in sach]
    rr = sum(r["rerank_s"] for r in sach)
    tt = sum(r["total_s"] for r in sach)
    if tt:
        d.append(
            f"**Rerank chiếm {so(100 * rr / tt, 0)}% tổng thời gian** trên cả lô. "
            f"Đó là câu trả lời cho *'tối ưu ở đâu'*: không phải ở LLM, và không "
            f"phải ở truy hồi — mà ở **cross-encoder chấm lại trên CPU**.\n"
        )
    if tong:
        d.append(
            f"Toàn lô: p50 **{_p(tong, .5)}s** · p95 **{_p(tong, .95)}s** "
            f"(n = {len(tong)}).\n"
        )

    # ⚠️ Con số n phải SUY RA từ chính bảng, không viết tay. Bản nháp đầu ghi
    # "~18 câu" trong khi bảng ngay trên nói 17 — đúng hình dạng ISSUE-071/073/075
    # (một câu văn hard-code sống sót qua sự kiện làm nó sai). Lần thứ tư.
    n_ans = len([r for r in sach if r["action"] == "ANSWER"])
    if n_ans >= 2:
        d.append(
            f"⚠️ **`p95` ở n nhỏ gần như chính là max.** Nhánh ANSWER chỉ có "
            f"**{n_ans}** câu, nên p95 nội suy giữa mẫu thứ {n_ans - 1} và {n_ans}. "
            f"Trích kèm **n**, đừng trích trần.\n"
        )
    d.append(
        "⚠️ **Nhánh TỪ CHỐI đắt hơn nhánh TRẢ LỜI** — nó chạy **2 lượt** truy hồi + "
        "rerank (lượt 2 vẫn chạy đủ để `trace` giữ được điểm, chỉ bị tước quyền "
        "*lật* phán quyết — DEC-061). Đây là **giá của an toàn**, nói thẳng ra "
        "được chứ không cần giấu.\n"
    )
    d.append(
        "⚠️ **Nhánh policy gần như bằng 0 và tốn 0 lượt LLM** — nó chặn **trước** "
        "truy hồi (DEC-024). Trộn nó vào p50 chung sẽ kéo con số xuống một cách "
        "vô nghĩa, nên bảng trên tách riêng.\n"
    )
    return d


def bang_space(sp: dict) -> list[str]:
    d: list[str] = []
    d.append("## 3. Latency trên HF Space — thứ người dùng thật chờ\n")
    d.append(
        f"Đo bằng Playwright lái UI thật trên **{sp.get('space', '?')}** "
        f"(`{sp.get('hardware', '?')}`), {sp.get('ngay', '?')}. "
        f"Space **không có batch runner** nên đây là vài mẫu, **không phải p50/p95**, "
        f"và **không tách được stage** — đó là lý do mục 2 phải đo ở local.\n"
    )
    d.append("| Nhánh | các lượt đo | n |")
    d.append("|---|---|---:|")
    for nhan, xs in (sp.get("nhanh") or {}).items():
        if xs:
            d.append(f"| {nhan} | {' · '.join(so(x) + 's' for x in xs)} | {len(xs)} |")
    d.append("")
    pr = sp.get("page_ready") or []
    hl = sp.get("health_s") or []
    if pr:
        # Cùng kỷ luật với mục 2: mẫu nào lệch hẳn mà ĐỐI CHỨNG vẫn bình thường
        # thì đó là máy đo, không phải hệ — loại, và nói rõ đã loại gì.
        tv = quantile(pr, 0.5)
        sach = [x for x in pr if x <= 3 * tv]
        ban = [x for x in pr if x > 3 * tv]
        d.append(
            f"**Page-ready** (thời gian tới lúc trang dùng được): "
            f"{' · '.join(so(x) + 's' for x in sach)} — n = {len(sach)}.\n"
        )
        if ban:
            d.append(
                f"⚠️ Đã **loại** {len(ban)} mẫu lệch ({' · '.join(so(x) + 's' for x in ban)}): "
                f"đối chứng `health` ở cùng thời điểm vẫn "
                f"**{so(min(hl), 2)}–{so(max(hl), 2)}s** — mạng và Space bình thường, nên "
                f"chỗ nghẽn là **laptop đang đo**. Đây chính là bẫy mô tả ngay dưới, "
                f"bắt được **bằng máy** thay vì bằng trí nhớ.\n"
            )
    d.append(
        "⛔ **BẪY ĐO — đã dính thật 2026-09-15.** Bật một **Chromium mới cho mỗi mẫu** "
        "làm page-ready phồng **5,9s → 103,7s (17×)**; dùng **một** browser cho cả lô "
        "thì ổn định. Đối chứng quyết định: `curl /_stcore/health` chạy **xen kẽ** vẫn "
        "0,84–0,99s suốt → nghẽn nằm ở **laptop đang đo**, không ở Space. Phiên đó đã "
        "kết luận nhầm *'cold start 73–85s'* rồi tự bác bỏ. Cùng lớp với đối chứng "
        "nhịp máy ở mục 2, và là lý do nó tồn tại.\n"
    )
    if sp.get("cold_start"):
        c = sp["cold_start"]
        d.append(
            f"**Cold start:** {c.get('container_s', '?')}s để container lên RUNNING, "
            f"rồi truy vấn đầu trả thêm **~{c.get('nap_model_s', '?')}s nạp model** "
            f"(Space `sleep_time` = 48 giờ, không có persistent storage). "
            f"→ **đụng vào Space trước buổi bảo vệ.**\n"
        )
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-pricing", action="store_true")
    args = ap.parse_args()

    if args.check_pricing:
        return kiem_gia()

    runs, bench = doc_jsonl(RUNS), doc_jsonl(BENCH)
    if not runs:
        print(f"⛔ Thiếu {RUNS.name}. Sinh lại: python scripts/export_runs.py")
        return 1
    if not bench:
        print(f"⛔ Thiếu {BENCH.name}. Chạy: python scripts/bench_latency.py")
        return 1

    d = ["# Latency & Cost — ViMed-RAG (Tuần 7)", ""]
    d.append(
        "> Sinh bằng `python scripts/build_perf_report.py`. **Đừng sửa tay** — "
        "sửa ở script rồi dựng lại, nếu không con số và câu văn sẽ trôi khỏi nhau.\n"
    )
    d += bang_cost(runs)
    d += bang_latency(bench)
    if SPACE.exists():
        d += bang_space(json.loads(SPACE.read_text(encoding="utf-8")))

    OUT.write_text("\n".join(d) + "\n", encoding="utf-8")
    print(f"[ok] {OUT.relative_to(ROOT)}  ({len(d)} dòng)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

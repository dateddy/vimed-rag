"""
Leakage SAU REWRITE — đo cái lỗ mà LOOCV không chạm tới.
=========================================================
Thuần số, mili-giây, không gọi mạng. Đọc `data/processed/runs.jsonl` do
`scripts/export_runs.py` sinh ra.

CÂU HỎI FILE NÀY TRẢ LỜI
------------------------
DEC-051 kết luận **leakage 0/30** và DEC-052 đóng ngưỡng vào `config.yaml`
dựa trên đó. Nhưng cả hai chấm trên điểm của **lượt truy hồi ĐẦU**. Hệ thống
thật thì cho mỗi câu bị chấm INCORRECT thêm **một lần thử thứ hai** (rewrite →
re-retrieve → grade lại), và lượt đó chưa từng nằm trong dữ liệu hiệu chỉnh.

Nên "0/30" là phát biểu về **một nửa** đường chạy. File này đo nốt nửa kia.

⚠️ **Kết quả có thể đi theo hướng xấu, và đó là kết quả hợp lệ.** Rewrite sinh
ra để lấp khoảng trống từ vựng (DEC-046); với câu nhóm A/B — hỏi về thực thể
corpus KHÔNG có — nó không tìm được tài liệu đúng, nhưng nó có thể viết lại
thành câu trùng từ vựng corpus hơn, mà điểm rerank thì bám **độ cùng chủ đề**
chứ không bám **độ đúng** (DEC-039). Tức chính cơ chế sửa sai lại là cơ chế có
thể đẩy câu không trả lời được lên trên ngưỡng. DEC-048 đã bắt đúng dạng đó
một lần rồi.

Nếu số ra xấu thì **không được sửa bằng cách hạ ngưỡng**: ngưỡng đã hiệu chỉnh
trên lượt 1 và đụng vào nó là phá luôn con số của DEC-051. Cách sửa đúng là
đổi thứ được chấm ở lượt 2 (ví dụ chỉ chấp nhận lượt 2 khi nó vượt một biên
CAO HƠN), và đó là một quyết định phải ghi vào DECISIONS.

CHẠY
----
  python scripts/analyze_leakage.py
  python scripts/analyze_leakage.py --runs data/processed/runs.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.eval.leakage import analyze, turn  # noqa: E402
from src.eval.stats import fmt_pct, rule_of_three  # noqa: E402

RUNS = ROOT / "data" / "processed" / "runs.jsonl"
OUT = ROOT / "docs" / "leakage-after-rewrite.md"


def load_runs(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _turn_row(rec: dict) -> str:
    """Một dòng bảng: điểm từng lượt của một câu."""
    t1, t2 = turn(rec, 0), turn(rec, 1)

    def f(t):
        if not t or t.get("logit") is None:
            return "—"
        return f"{t['logit']:+.3f}"

    return (
        f"| `{rec['id']}` | {rec['group']} | {f(t1)} | "
        f"{(t1 or {}).get('state') or '—'} | {f(t2)} | "
        f"{(t2 or {}).get('state') or '—'} | {rec['action']} |"
    )


def _mechanisms(by_mech: dict) -> str:
    """``{"policy": [8 câu]}`` → ``"policy 8"`` — bảng báo cáo không đọc JSON thô."""
    if not by_mech:
        return "—"
    return " · ".join(
        f"{name if name != 'None' else 'KHÔNG abstain'} {len(ids)}"
        for name, ids in sorted(by_mech.items())
    )


def report_lines(res: dict, runs: list[dict], cfg) -> list[str]:
    ab, e, mar, pol = res["abstain"], res["answer"], res["margin_ab"], res["policy"]
    corrective = [r for r in runs if r.get("system") == "corrective"]
    two_turn = [r for r in corrective if len(r.get("turns") or []) > 1]

    md = [
        "# Leakage SAU REWRITE",
        "",
        "> Sinh bằng `python scripts/analyze_leakage.py` từ "
        "`data/processed/runs.jsonl`. Thuần số, không gọi mạng.",
        f"> Ngưỡng đang dùng: `incorrect_threshold = "
        f"{res['threshold_sigmoid']}` = **{res['threshold_logit']:+.3f}** logit "
        f"· `max_iter = {cfg.corrective.max_iter}`",
        "",
        "## Vì sao con số này phải đo riêng",
        "",
        "Hiệu chỉnh LOOCV (DEC-051) và ngưỡng đóng vào `config.yaml` (DEC-052) "
        "đều chấm trên điểm của **lượt truy hồi đầu**. Hệ thống thật cho mỗi câu "
        "bị chấm INCORRECT thêm **một lần thử thứ hai** sau rewrite, và lượt đó "
        "**không** nằm trong dữ liệu hiệu chỉnh. `leakage 0/30` vì thế là phát "
        "biểu về một nửa đường chạy.",
        "",
        "## Ba mốc, đừng gộp làm một",
        "",
        "| mốc | nghĩa là gì | nhóm A/B |",
        "|---|---|---|",
        f"| **lượt 1** | không bị chấm INCORRECT ngay → trả lời luôn "
        f"(đúng thứ LOOCV đo) | {fmt_pct(len(ab['answered_turn1']), ab['n'])} |",
        f"| **lượt 2** | bị chặn ở lượt 1 nhưng **rewrite kéo lên** trên ngưỡng "
        f"| {fmt_pct(len(ab['answered_turn2']), ab['n'])} |",
        f"| **cuối** | con số THẬT của hệ thống | "
        f"{fmt_pct(len(ab['answered_final']), ab['n'])} |",
        "",
        f"- {ab['n_turn2']}/{ab['n']} câu A/B đi tới lượt thứ hai "
        f"(tức bị chấm INCORRECT ở lượt đầu — hiệu chỉnh làm đúng việc của nó).",
    ]

    if ab["answered_turn2"]:
        md += [
            f"- ⛔ **{len(ab['answered_turn2'])} câu lọt lưới Ở LƯỢT HAI**: "
            f"{', '.join('`' + q + '`' for q in ab['answered_turn2'])}. "
            "Đây là leakage mà hiệu chỉnh **không nhìn thấy** — vòng corrective "
            "tự tạo ra nó. **Không được vá bằng cách hạ ngưỡng**: ngưỡng đã "
            "hiệu chỉnh trên lượt 1, đụng vào là phá luôn con số DEC-051.",
        ]
    else:
        md += [
            f"- ✅ **0 câu lọt lưới ở lượt hai.** ⚠️ Với n={ab['n']} điều đó chỉ "
            f"chứng minh được leakage sau rewrite **< "
            f"{100 * rule_of_three(ab['n']):.0f}%** (quy tắc số ba), KHÔNG "
            "chứng minh bằng 0.",
        ]

    md += ["", "## Biên còn lại — 0 vì may hay vì dư địa?", ""]
    md += [
        "`leaked = 0` với biên 0,02 logit và `leaked = 0` với biên 1,5 logit là "
        "hai tình trạng an toàn khác hẳn nhau, mà cả hai đều in ra cùng một con "
        "số. Bảng dưới là khoảng cách từ câu A/B **cao điểm nhất** tới ngưỡng:",
        "",
        "| lượt | câu cao nhất | max-logit | biên tới ngưỡng |",
        "|---|---|---|---|",
    ]
    for name, label in (("turn1", "lượt 1"), ("turn2", "lượt 2 (sau rewrite)")):
        m = mar.get(name)
        if not m:
            md.append(f"| {label} | — | — | (không câu nào tới lượt này) |")
            continue
        md.append(
            f"| {label} | `{m['top_id']}` | {m['top_logit']:+.3f} | "
            f"**{m['margin']:+.3f}** |"
        )
    md += [
        "",
        "Biên **âm** = đã có câu vượt ngưỡng = leakage. Biên dương càng nhỏ càng "
        "gần chỗ hỏng.",
        "",
    ]

    if ab["deltas"]:
        neg, pos, p = ab["sign_test"]
        md += [
            "## Rewrite đẩy điểm nhóm A/B đi đâu?",
            "",
            f"Trên {len(ab['deltas'])} câu A/B đi qua rewrite, thay đổi logit "
            f"lượt 1 → lượt 2:",
            "",
            f"- trung vị **{ab['delta_median']:+.3f}** · lớn nhất "
            f"**{ab['delta_max']:+.3f}**",
            f"- kiểm định dấu: **{neg} tụt · {pos} tăng · p = {p:.4f}**",
            "",
            "Hướng của con số này là thứ đáng đọc, không phải độ lớn: rewrite "
            "**đẩy lên** một cách hệ thống nghĩa là cơ chế sửa sai đang làm hệ "
            "thống tự tin hơn về những câu nó không trả lời được — đúng dạng "
            "hỏng mà DEC-039 mô tả (điểm bám độ **cùng chủ đề**, không bám độ "
            "**đúng**).",
            "",
        ]

    # --- cán cân: vòng corrective cho gì và lấy gì ------------------------ #
    rescued, leaked2 = e["answered_turn2"], ab["answered_turn2"]
    md += [
        "## ⚖️ Cán cân của vòng corrective — cho gì, lấy gì",
        "",
        "Rewrite chỉ chạy trên câu bị chấm INCORRECT. Nó có đúng **hai** hệ quả "
        "đo được, và chúng ngược chiều nhau:",
        "",
        "| | số câu | nghĩa |",
        "|---|---|---|",
        f"| **được cứu** (nhóm E, từ chối oan → trả lời được) | **{len(rescued)}"
        f"/{e['n_turn2']}** | lợi ích của DEC-046 |",
        f"| **lọt lưới** (nhóm A/B, bị chặn đúng → được trả lời) | "
        f"**{len(leaked2)}/{ab['n_turn2']}** | thiệt hại |",
        "",
    ]
    if len(leaked2) > len(rescued):
        md += [
            "⛔ **Trên test set này, tác dụng đo được DUY NHẤT của vòng "
            f"corrective là tạo ra leakage.** Nó cứu {len(rescued)} câu và làm "
            f"lọt {len(leaked2)} câu. Đây là phát biểu về **test set + ngưỡng "
            "hiện tại**, không phải phát biểu rằng rewrite vô dụng: DEC-046 có "
            "bằng chứng định tính là nó lấp được khoảng trống từ vựng. Nhưng "
            "claim *\"vòng corrective làm hệ thống tốt lên\"* thì **không "
            "chống đỡ được bằng dữ liệu này**, và đó là trục đóng góp của đề "
            "tài. Phải vào Chương kết quả, không phải chỉ vào Limitations.",
            "",
            "Đối chiếu: DEC-055 đo trên biến thể giọng bệnh nhân cũng thấy "
            "rewrite chỉ cứu **2/7** câu mất. Ba đường đo khác nhau, cùng một "
            "hướng.",
            "",
        ]

    # --- chi tiết từng câu lọt lưới -------------------------------------- #
    leaked_recs = [r for r in corrective if r.get("leaked")]
    if leaked_recs:
        md += [
            "## Từng câu lọt lưới — đọc bằng mắt",
            "",
            "Trích nguyên văn để người đọc tự phán, KHÔNG dán nhãn tự động: "
            "quyết định \"câu trả lời này có hại không\" cần đọc nội dung, và "
            "đoán bằng regex là dựng một phép đo giả.",
            "",
        ]
        for r in leaked_recs:
            t1, t2 = turn(r, 0), turn(r, 1)
            md += [
                f"### `{r['id']}` ({r['group']}) → **{r['action']}**",
                "",
                f"- **hỏi:** {r['user_input']}",
                f"- **viết lại:** {r.get('rewritten_query') or '—'}",
                f"- **điểm:** lượt 1 {(t1 or {}).get('logit', 0):+.3f} "
                f"({(t1 or {}).get('state')}) → lượt 2 "
                f"{(t2 or {}).get('logit', 0):+.3f} ({(t2 or {}).get('state')})",
                f"- **nguồn hiện ra:** {r.get('n_chunks_shown')} · "
                f"**trích dẫn bịa:** {r.get('invalid_citations') or 'không có'}",
                "",
                "> " + " ".join(r["answer"][:400].split()) + "…",
                "",
            ]

    md += [
        "## Nhóm E — rewrite có cứu được câu nào không?",
        "",
        f"- coverage cuối: {fmt_pct(len(e['answered_final']), e['n'])}",
        f"- {e['n_turn2']}/{e['n']} câu E bị chấm INCORRECT ở lượt đầu và đi "
        f"tới rewrite; **{len(e['answered_turn2'])}** trong số đó được rewrite "
        "**cứu** (cuối cùng vẫn trả lời được).",
        f"- từ chối nhầm (false refusal): "
        f"{', '.join('`' + q + '`' for q in e['refused_final']) or 'không có'}.",
        "",
        "Đây là phép đo trực tiếp giá trị của DEC-046 (query rewrite): nó cứu "
        "được bao nhiêu câu đáng lẽ bị từ chối oan. Đối chiếu với DEC-055 — "
        "trên biến thể giọng bệnh nhân, rewrite chỉ cứu được **2/7**.",
        "",
        "## Nhóm D — có đi đúng cửa không?",
        "",
        f"- {pol['n']} câu · cơ chế abstain: **{_mechanisms(pol['by_mechanism'])}**",
        f"- rule đã bắt: {', '.join('`' + r + '`' for r in pol['rules']) or '—'}",
    ]
    if pol["answered"]:
        md += [
            f"- ⛔ **{len(pol['answered'])} câu nhóm D được TRẢ LỜI**: "
            f"{', '.join('`' + q + '`' for q in pol['answered'])}. Policy gate trượt.",
        ]
    retrieval_d = pol["by_mechanism"].get("retrieval") or []
    if retrieval_d:
        md += [
            f"- ⚠️ **{len(retrieval_d)} câu D abstain do RETRIEVAL chứ không do "
            f"policy**: {', '.join('`' + q + '`' for q in retrieval_d)}. Đúng "
            "kết cục vì sai lý do — gate trượt, và hệ thống chỉ tình cờ không "
            "tìm thấy tài liệu. Trên một câu D khác, cùng lỗi đó sẽ thành câu "
            "trả lời.",
        ]

    md += [
        "",
        "## Điểm từng lượt, từng câu",
        "",
        "Chỉ liệt kê câu đi qua rewrite (câu trả lời/chặn ngay ở lượt 1 không có "
        "gì mới để xem).",
        "",
        "| câu | nhóm | logit lượt 1 | state 1 | logit lượt 2 | state 2 | action |",
        "|---|---|---|---|---|---|---|",
        *[_turn_row(r) for r in sorted(two_turn, key=lambda r: r["id"])],
        "",
        "## Giới hạn",
        "",
        f"- `max_iter = {cfg.corrective.max_iter}` (ràng buộc #4) nên nhiều nhất "
        "**hai** lượt. Kết luận ở đây không nói gì về cấu hình nhiều vòng hơn.",
        "- Mẫu số vẫn là 30 câu A/B và 21 câu E. CV không làm test set lớn lên; "
        "mọi khoảng tin cậy ở trên đều rộng.",
        "- Điểm lượt 2 **chưa từng được hiệu chỉnh**. Nếu muốn nó có ngưỡng "
        "riêng thì phải hiệu chỉnh trên chính phân bố này, và đó là một quyết "
        "định mới chứ không phải chỉnh tham số.",
        "",
    ]
    return md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", default=str(RUNS), help="đường dẫn runs.jsonl")
    ap.add_argument("--out", default=str(OUT), help="nơi ghi báo cáo Markdown")
    args = ap.parse_args()
    out = Path(args.out)

    path = Path(args.runs)
    if not path.exists():
        sys.exit(
            f"!! Thiếu {path}. Sinh bằng:\n"
            f"   python scripts/export_runs.py --systems corrective"
        )
    runs = load_runs(path)
    corrective = [r for r in runs if r.get("system") == "corrective"]
    if not corrective:
        sys.exit("!! runs.jsonl không có bản ghi nào system=corrective.")

    cfg = load_config()
    res = analyze(runs, incorrect_threshold=cfg.grader.incorrect_threshold)
    ab, e, pol = res["abstain"], res["answer"], res["policy"]

    print(f"Bản ghi corrective: {res['n_records']} "
          f"(A/B {ab['n']} · E {e['n']} · D {pol['n']})")
    print(f"Ngưỡng: {res['threshold_sigmoid']} = "
          f"{res['threshold_logit']:+.3f} logit\n")

    print("[1] LEAKAGE NHÓM A/B — ba mốc")
    print(f"    lượt 1 : {fmt_pct(len(ab['answered_turn1']), ab['n'])}"
          f"   <- đúng thứ LOOCV đã đo")
    print(f"    lượt 2 : {fmt_pct(len(ab['answered_turn2']), ab['n'])}"
          f"   <- CHƯA TỪNG ĐO trước hôm nay")
    print(f"    cuối   : {fmt_pct(len(ab['answered_final']), ab['n'])}"
          f"   <- con số THẬT của hệ thống")
    if ab["answered_turn2"]:
        print(f"    ⛔ lọt lưới ở lượt 2: {ab['answered_turn2']}")
    else:
        print(f"    0 lọt lưới ở lượt 2 -> chỉ chứng minh được "
              f"< {100 * rule_of_three(ab['n']):.0f}%")

    print(f"\n[2] BIÊN CÒN LẠI (câu A/B cao nhất so với ngưỡng)")
    for name, label in (("turn1", "lượt 1"), ("turn2", "lượt 2")):
        m = res["margin_ab"].get(name)
        if not m:
            print(f"    {label}: (không câu nào tới lượt này)")
            continue
        print(f"    {label}: {m['top_id']} = {m['top_logit']:+.3f} -> biên "
              f"{m['margin']:+.3f} logit")

    if ab["deltas"]:
        neg, pos, p = ab["sign_test"]
        print(f"\n[3] REWRITE ĐẨY ĐIỂM A/B ĐI ĐÂU ({len(ab['deltas'])} câu)")
        print(f"    Δlogit trung vị {ab['delta_median']:+.3f} · "
              f"lớn nhất {ab['delta_max']:+.3f}")
        print(f"    kiểm định dấu: {neg} tụt · {pos} tăng · p = {p:.4f}")

    print(f"\n[4] NHÓM E — coverage cuối "
          f"{fmt_pct(e['n'] - len(e['refused_final']), e['n'])}")
    if e["refused_final"]:
        print(f"    từ chối nhầm: {e['refused_final']}")

    print(f"\n[5] NHÓM D — cơ chế abstain: {_mechanisms(pol['by_mechanism'])}")
    if pol["answered"]:
        print(f"    ⛔ được trả lời (gate trượt): {pol['answered']}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report_lines(res, runs, cfg)), encoding="utf-8")
    print(f"\n[out] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

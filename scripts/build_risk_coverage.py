"""
Đường cong risk–coverage → docs/risk-coverage.md + docs/risk-coverage.png
=========================================================================
Việc (2) của Tuần 6 theo thứ tự DEC-015. Thuần số: đọc
`calibration_scores.json` (+ `runs.jsonl` để đối chứng), **không** gọi API,
**không** cần Qdrant. Chạy vài mili-giây, chạy lại bao nhiêu lần cũng được.

⛔ BA ĐIỀU BÁO CÁO NÀY PHẢI NÓI CHO ĐÚNG — lý do đầy đủ ở `src/eval/risk_coverage.py`.

* **Đường cong KHÔNG dùng để chọn ngưỡng** (DEC-063). Ngưỡng đã chốt ở DEC-051
  bằng LOOCV. Chọn lại từ đường cong dựng trên đúng 51 câu ấy là khớp-trên-tập-
  đánh-giá. Vai trò mới: **bằng chứng điểm vận hành nằm trên biên hiệu quả**.

* **`risk` phụ thuộc tỉ lệ test set.** Ở coverage tối đa, risk = 30/51 = 0,588 —
  đó là tỉ lệ câu A/B trong test set, không phải thuộc tính của hệ thống. Nên
  bảng in **cả** cặp (coverage_e, leak_ab) lẫn `risk`, và cảnh báo đi kèm ngay
  cạnh trục chứ không nằm dưới chân bảng.

* **Nhóm D ngoài đường cong.** Policy gate chặn trước retrieval nên 8 câu D
  không có điểm tin cậy nào. n = 51, không phải 59.

CHẠY
----
  python scripts/build_risk_coverage.py
  python scripts/build_risk_coverage.py --no-plot   # bỏ qua matplotlib
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
from src.eval.stats import fmt_pct, rule_of_three, wilson  # noqa: E402
from src.eval.risk_coverage import (  # noqa: E402
    cliff,
    compare_sources,
    compute_risk_coverage,
    coverage_gap,
    free_band,
    is_on_frontier,
    operating_point,
    pareto_frontier,
    scores_from_calibration,
    scores_from_runs,
)

CAL = ROOT / "data" / "processed" / "calibration_scores.json"
RUNS = ROOT / "data" / "processed" / "runs.jsonl"
OUT = ROOT / "docs" / "risk-coverage.md"
PNG = ROOT / "docs" / "risk-coverage.png"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def fmt_risk(p) -> str:
    return "—" if p.risk is None else f"{p.risk:.3f}"


def draw(points, op, path: Path) -> bool:
    """Hai bảng cạnh nhau. Trả False nếu không có matplotlib.

    **Hai bảng chứ không một:** bảng trái là cặp (coverage_e, leak_ab) — hai số
    đếm thô, không mẫu số chung, nên không mang tỉ lệ test set vào. Bảng phải là
    cặp risk–coverage kinh điển, có để đúng thuật ngữ ngành, nhưng trục y phải
    tự mang cảnh báo của nó.

    ``drawstyle="steps-post"`` chứ không phải đường thẳng nối: dữ liệu là 52
    điểm rời rạc quanh một vực 3,06 logit, nối thẳng là vẽ ra một dốc thoải ở
    chỗ thật sự là một vách.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.4))

    pts = sorted(points, key=lambda p: p.cov_e)
    axL.step([p.cov_e for p in pts], [p.leak_ab for p in pts],
             where="post", color="#2b6cb0", lw=1.6)
    axL.scatter([p.cov_e for p in pts], [p.leak_ab for p in pts],
                s=14, color="#2b6cb0", zorder=3)
    axL.scatter([op.cov_e], [op.leak_ab], s=150, marker="*",
                color="#c53030", zorder=5,
                label=f"điểm vận hành ({op.cov_e}/{op.n_e}, {op.leak_ab}/{op.n_ab})")
    axL.set_xlabel(f"coverage — số câu E được trả lời (/{op.n_e})")
    axL.set_ylabel(f"leakage — số câu A/B lọt lưới (/{op.n_ab})")
    axL.set_title("Hai số đếm thô (không lẫn tỉ lệ test set)")
    axL.legend(fontsize=8, loc="upper left")
    axL.grid(alpha=0.25)

    have = [p for p in points if p.risk is not None]
    have.sort(key=lambda p: p.n_answered)
    total = op.n_ab + op.n_e
    axR.step([p.n_answered / total for p in have], [p.risk for p in have],
             where="post", color="#2b6cb0", lw=1.6)
    axR.scatter([op.n_answered / total], [op.risk], s=150, marker="*",
                color="#c53030", zorder=5, label="điểm vận hành")
    axR.set_xlabel(f"coverage — tỉ lệ câu được trả lời (/{total})")
    axR.set_ylabel("risk = lọt / đã trả lời\n⚠ phụ thuộc tỉ lệ A/B:E của test set")
    axR.set_title("Risk–coverage kinh điển")
    axR.legend(fontsize=8, loc="upper left")
    axR.grid(alpha=0.25)

    fig.suptitle("ViMed-RAG — đường cong risk–coverage (n=51, nhóm D ngoài đường cong)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-plot", action="store_true",
                    help="chỉ sinh Markdown, bỏ qua biểu đồ")
    args = ap.parse_args()

    if not CAL.exists():
        sys.exit(
            f"!! Thiếu {CAL.relative_to(ROOT)} — sinh bằng:\n"
            "   python scripts/eval_retrieval.py --sizes 512 --modes hybrid \\\n"
            "       --groups A,B,D,E --out docs/retrieval-eval-deploy --dump-scores"
        )

    cfg = load_config()
    payload = json.loads(CAL.read_text(encoding="utf-8"))
    scores = scores_from_calibration(payload)

    points = compute_risk_coverage(scores)
    op = operating_point(scores, cfg.grader.incorrect_threshold)
    front = pareto_frontier(points)
    front_ids = {id(p) for p in front}
    gap = coverage_gap(scores, op.threshold)
    cl = cliff(points, from_cov_e=op.cov_e)
    band = free_band(points, cov_e=op.cov_e)
    full = min(points, key=lambda p: p.threshold)

    # Đối chứng chéo — phép kiểm rẻ bắt đúng loại lỗi "hai bảng, hai thang điểm".
    runs = load_jsonl(RUNS)
    xcheck = compare_sources(scores, scores_from_runs(runs)) if runs else None

    L: list[str] = []
    L.append("# Đường cong risk–coverage\n")
    L.append(
        "> Sinh bằng `python scripts/build_risk_coverage.py` từ "
        "`data/processed/calibration_scores.json`. Thuần số, không gọi mạng.\n"
    )
    L.append(
        f"> Cấu hình: `size={payload['config'].get('size')}` · "
        f"`mode={payload['config'].get('mode')}` · "
        f"`top_k_dense={payload['config'].get('top_k_dense')}` · ngưỡng "
        f"`incorrect={cfg.grader.incorrect_threshold}` / "
        f"`correct={cfg.grader.correct_threshold}`.\n"
    )

    # ------------------------------------------------------------- cảnh báo
    L.append("## ⚠️ Ba điều phải đọc trước khi trích bất kỳ con số nào\n")
    L.append(
        "1. **Đường cong này KHÔNG dùng để chọn ngưỡng** (DEC-063). Ngưỡng đã "
        "chốt ở DEC-051 bằng LOOCV. Chọn lại từ đường cong dựng trên đúng 51 "
        "câu ấy là khớp-trên-tập-đánh-giá — cái bẫy LOOCV sinh ra để tránh. "
        "Vai trò của đường cong là **bằng chứng điểm vận hành nằm trên biên "
        "hiệu quả**, không phải cơ chế chọn.\n"
    )
    L.append(
        f"2. **`risk` phụ thuộc tỉ lệ test set.** Ở coverage tối đa risk = "
        f"**{full.risk:.3f}** — đó đúng bằng {full.n_ab}/{full.n_ab + full.n_e}, "
        "tỉ lệ câu A/B trong test set. Nó là thuộc tính của **cách dựng test "
        "set** (cố ý nhồi câu không trả lời được — DEC-026/027), **không** phải "
        'của hệ thống. Trích *"risk giảm từ 59% xuống 0%"* như một thành tựu là '
        "sai cùng một kiểu với `leakage 0/30` mà `threshold-calibration.md` đã "
        "cảnh báo.\n"
    )
    L.append(
        f"3. **Nhóm D nằm NGOÀI đường cong.** Policy gate chặn 8 câu D *trước* "
        f"retrieval nên chúng không có điểm tin cậy nào. **n = {op.n_ab + op.n_e}** "
        f"(A/B {op.n_ab} + E {op.n_e}), không phải 59.\n"
    )

    # -------------------------------------------------------- điểm vận hành
    L.append("## Điểm vận hành\n")
    L.append("| | giá trị |")
    L.append("|---|---|")
    L.append(f"| ngưỡng (`config.yaml`, sigmoid) | `{cfg.grader.incorrect_threshold}` |")
    L.append(f"| ngưỡng (logit) | **{op.threshold:+.4f}** |")
    L.append(f"| coverage E | {fmt_pct(op.cov_e, op.n_e)} |")
    L.append(f"| leakage A/B | {fmt_pct(op.leak_ab, op.n_ab)} |")
    L.append(f"| risk (lọt / đã trả lời) | **{fmt_risk(op)}** |")
    L.append(
        f"| nằm trên biên hiệu quả? | "
        f"{'**CÓ** — không điểm nào trội hẳn nó' if is_on_frontier(op, points) else '**KHÔNG**'} |"
    )
    L.append("")
    L.append(
        f"⚠️ `config.yaml` lưu bản đã làm tròn (`{cfg.grader.incorrect_threshold}`) nên "
        f"quy ngược ra **{op.threshold:+.4f}**, không đúng `+2.430` của DEC-051. "
        "Chênh lệch đó **không đổi quyết định câu nào** — điểm A/B cao nhất "
        "`+2.153`, điểm E thấp nhất còn được trả lời `+2.708`, cả hai cách xa "
        "hơn 0,2 logit.\n"
    )
    lo_w, hi_w = wilson(op.leak_ab, op.n_ab)
    L.append(
        f"⚠️ **`leakage {op.leak_ab}/{op.n_ab}` ở đây là TỰ ĐỘNG ĐÚNG, không phải "
        "kết quả** — quy trình DEC-051 đặt ngưỡng ngay TRÊN điểm A/B cao nhất. "
        "Con số đem đi báo cáo là bản LOOCV, và **không bao giờ viết \"= 0\"**.\n"
    )
    L.append(
        f"⚠️ **Hai cận trên, hai phương pháp — đừng trộn.** Với {op.leak_ab}/"
        f"{op.n_ab}: **Wilson** cho `0–{100 * hi_w:.0f}%` (con số trong bảng "
        f"trên, và là con số STATUS/DEC-061 đang trích); **quy tắc số ba** cho "
        f"`< {100 * rule_of_three(op.n_ab):.0f}%` (con số `threshold-calibration.md` "
        "đang trích). Cả hai đều đúng, chúng chỉ là hai ước lượng khác nhau — "
        "nhưng một báo cáo dùng lẫn lộn hai con số cho cùng một phép đo thì "
        "người đọc không có cách nào biết cái nào là cái nào. **Chọn một và "
        "gọi tên nó mỗi lần trích.**\n"
    )

    # ------------------------------------------------- ba con số đọc được
    L.append("## Ba con số đọc được từ đường cong\n")

    if gap:
        L.append(
            f"### 1. Vách **{gap['gap']:.3f} logit** — đường cong là bậc thang, không phải dốc\n"
        )
        L.append(
            f"Câu E thấp điểm nhất **được** trả lời: `{gap['lowest_answered']:+.3f}`. "
            f"Câu E cao điểm nhất **bị** từ chối: `{gap['highest_rejected']:+.3f}`. "
            f"Giữa hai mốc đó **không có câu nào**.\n"
        )
        L.append(
            "Đây chính là \"vực 3,06 logit\" mà DEC-051 đặt tên khi gọi phân bố "
            "nhóm E là **lưỡng cực** — ở đây nó được tính lại từ dữ liệu chứ "
            "không chép lại.\n"
        )

    if cl:
        L.append(f"### 2. Giá của câu E kế tiếp = **{cl['extra_leak']} câu A/B lọt lưới**\n")
        drop_from_op = op.threshold - cl["point"].threshold
        L.append(
            f"Muốn phủ thêm dù chỉ một câu E, phải hạ ngưỡng từ **{op.threshold:+.4f}** "
            f"xuống **{cl['point'].threshold:+.4f}** — tức **{drop_from_op:.3f} logit**, "
            f"rơi qua hết cái vách. Khi đó coverage đi từ "
            f"**{cl['from_cov_e']}/{op.n_e}** lên **{cl['to_cov_e']}/{op.n_e}**, "
            f"nhưng leakage nhảy từ **{op.leak_ab}/{op.n_ab}** lên "
            f"**{cl['point'].leak_ab}/{op.n_ab}**.\n"
        )
        L.append(
            f"⚠️ **{drop_from_op:.3f} đo từ ngưỡng ĐANG CHẠY** (`{op.threshold:+.4f}`). "
            f"Đo từ điểm quan sát cao nhất còn giữ coverage {cl['from_cov_e']}/{op.n_e} "
            f"(`{cl['threshold_drop'] + cl['point'].threshold:+.4f}`) thì ra "
            f"**{cl['threshold_drop']:.3f}** — hai mốc khác nhau nên hai con số khác "
            "nhau. Trích số nào thì nói rõ đo từ đâu.\n"
        )
        L.append(
            "→ Khi đường cong là bậc thang, câu hỏi có nghĩa **không** phải "
            '*"đánh đổi bao nhiêu mỗi điểm phần trăm"* mà *"câu tiếp theo giá '
            'bao nhiêu"*. Giá ở đây là không trả nổi.\n'
        )

    if band:
        L.append(
            f"### 3. Dải miễn phí rộng **{band['width']:.3f} logit** — "
            f"giảm {band['leak_saved']} câu lọt mà KHÔNG mất câu coverage nào\n"
        )
        L.append(
            f"Từ `{band['lo'].threshold:+.3f}` đến `{band['hi'].threshold:+.3f}`, "
            f"coverage đứng yên ở **{band['cov_e']}/{op.n_e}** trong khi leakage "
            f"tụt **{band['lo'].leak_ab}/{op.n_ab} → {band['hi'].leak_ab}/{op.n_ab}**.\n"
        )
        L.append(
            "Nếu đánh đổi trả lời/từ chối là thật sự liên tục thì dải này phải "
            "**rỗng**. Nó không rỗng, và điểm vận hành nằm ở đúng đầu mút tốt "
            "nhất của nó.\n"
        )

    # -------------------------------------------------------- biên hiệu quả
    L.append("## Biên hiệu quả\n")
    L.append(
        f"**{len(front)}/{len(points)}** điểm không bị điểm nào trội hẳn. "
        "Trội hẳn = phủ không kém **và** lọt không hơn, hơn hẳn ở ít nhất một "
        "chiều — xếp hạng trên cặp `(cov_e, leak_ab)` chứ **không** trên `risk`, "
        "vì mẫu số của `risk` trộn tỉ lệ test set vào (cảnh báo 2).\n"
    )
    L.append("| ngưỡng (logit) | coverage E | leakage A/B | risk |")
    L.append("|---|---|---|---|")
    for p in sorted(front, key=lambda p: -p.threshold):
        L.append(
            f"| `{p.threshold:+.3f}` | {p.cov_e}/{p.n_e} | {p.leak_ab}/{p.n_ab} "
            f"| {fmt_risk(p)} |"
        )
    L.append("")
    L.append(
        f"Mọi ngưỡng **trên** `{band['hi'].threshold:+.3f}` đều bị trội hẳn: coverage "
        "giảm mà risk vẫn 0. Đó là vùng thắt chặt vô ích.\n"
        if band else ""
    )

    # ------------------------------------------------------- bảng đầy đủ
    L.append("## Bảng đầy đủ\n")
    L.append(
        "Mỗi dòng = một ngưỡng ứng viên. Ngưỡng ứng viên = **đúng tập điểm quan "
        "sát được**, không nội suy: nội suy giữa hai điểm là bịa ra một ngưỡng "
        "không câu nào kiểm chứng được, và nó vẽ đường mượt ở chỗ dữ liệu là "
        "vách.\n"
    )
    L.append("| ngưỡng (logit) | coverage E | leakage A/B | risk | đã trả lời | biên |")
    L.append("|---|---|---|---|---|---|")
    seen: set[tuple[int, int]] = set()
    marked: float | None = None
    for p in sorted(points, key=lambda p: p.threshold):
        key = (p.cov_e, p.leak_ab)
        if key in seen:
            continue
        seen.add(key)
        mark = "★" if id(p) in front_ids else ""
        same = (p.cov_e, p.leak_ab) == (op.cov_e, op.leak_ab)
        if same and marked is None:
            marked = p.threshold
        L.append(
            f"| `{p.threshold:+.3f}`{' ←' if same else ''} | {p.cov_e}/{p.n_e} | "
            f"{p.leak_ab}/{p.n_ab} | {fmt_risk(p)} | {p.n_answered}/"
            f"{p.n_ab + p.n_e} | {mark} |"
        )
    L.append("")
    L.append("`←` = **tập câu** mà điểm vận hành cho ra · `★` = trên biên hiệu quả\n")
    if marked is not None:
        # Lấy ngưỡng từ CHÍNH dòng đã đánh dấu, không lấy từ `free_band`: hai thứ
        # trùng nhau trên dữ liệu hiện tại, nhưng trùng do dữ liệu chứ không do
        # cấu tạo — và một chú thích chỉ sai khi dữ liệu đổi là thứ không ai soi.
        L.append(
            f"⚠️ Dòng `←` ghi ngưỡng **quan sát được** (`{marked:+.3f}`), không phải "
            f"ngưỡng đang đóng trong config (`{op.threshold:+.4f}`). Hai số khác nhau "
            "nhưng **cho ra đúng cùng một tập câu trả lời** — ngưỡng config rơi vào "
            "giữa hai điểm quan sát liền kề, và bảng này chỉ liệt kê ngưỡng quan sát "
            "được. Đừng trích số ở cột đầu như thể nó là ngưỡng hệ thống.\n"
        )

    # ---------------------------------------------------- đối chứng chéo
    L.append("## Đối chứng chéo hai nguồn điểm\n")
    if xcheck is None:
        L.append(
            "⚠️ **CHƯA CHẠY** — thiếu `data/processed/runs.jsonl` (bị gitignore). "
            "Sinh lại bằng `python scripts/export_runs.py` (~45 phút) rồi chạy "
            "lại script này.\n"
        )
    else:
        verdict = "✅ **KHỚP**" if xcheck["ok"] else "⛔ **LỆCH**"
        L.append(
            f"{verdict} — `calibration_scores.json` ({xcheck['n_a']} câu) vs "
            f"`runs.jsonl` `turns[0]` ({xcheck['n_b']} câu): "
            f"**{xcheck['n_common']}/{xcheck['n_common']}** câu chung, lệch lớn "
            f"nhất **{xcheck['max_diff']:.3e}** (`{xcheck['worst_id']}`).\n"
        )
        if xcheck["mismatched"]:
            L.append(f"Câu lệch quá ngưỡng: `{'`, `'.join(xcheck['mismatched'])}`\n")
        L.append(
            "Lệch cỡ `1e-6` là sai số vòng tròn: `runs.jsonl` lưu `score` đã qua "
            "float32 rồi mới suy ngược ra logit. Phép kiểm này rẻ nhưng bắt đúng "
            "loại lỗi nguy hiểm nhất — hai bảng trong cùng một báo cáo đứng trên "
            "hai thang điểm khác nhau (lớp lỗi DEC-033).\n"
        )

    # --------------------------------------------------------- giới hạn
    L.append("## Giới hạn — phải vào báo cáo\n")
    L.append(
        f"- **Đường cong dựng trên điểm LƯỢT 1, và chỉ hợp lệ từ DEC-061.** Trước "
        "guard, lượt 2 lật được phán quyết lượt 1 nên một đường cong lượt 1 sẽ "
        "mô tả một hệ thống không tồn tại. Guard là **điều kiện tiên quyết** của "
        "biểu đồ này, không phải việc song song.\n"
    )
    L.append(
        f"- **Mỗi câu E nặng {100 / op.n_e:.1f} điểm coverage.** n={op.n_e} thì "
        "đường cong không thể mịn hơn thế, bất kể vẽ đẹp đến đâu.\n"
    )
    L.append(
        "- **Coverage tính theo `action` đếm dư 1** so với nội dung: `E-21` ra "
        "`ANSWER` nhưng generator tự viết \"không có thông tin\" (DEC-056). "
        "Đường cong thừa hưởng lỗi này; RAGAS mới chấm được tầng nội dung.\n"
    )
    L.append(
        "- **Test set mang văn phong sách giáo khoa** (DEC-029). Đổi sang giọng "
        "bệnh nhân thì coverage tụt 17/21 → 10/21 (DEC-055) — tức đường cong này "
        "là bản **lạc quan**, và điểm vận hành chọn trên nó có thể quá dễ dãi "
        "với truy vấn đời thường.\n"
    )

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"✅ {OUT.relative_to(ROOT)}")

    if args.no_plot:
        print("   (bỏ qua biểu đồ theo --no-plot)")
    elif draw(points, op, PNG):
        print(f"✅ {PNG.relative_to(ROOT)}")
    else:
        print("!! matplotlib chưa cài — bỏ qua biểu đồ. `pip install matplotlib==3.10.8`")

    print(f"\n   điểm vận hành: coverage {op.cov_e}/{op.n_e} · leakage "
          f"{op.leak_ab}/{op.n_ab} · risk {fmt_risk(op)}")
    print(f"   trên biên hiệu quả: {is_on_frontier(op, points)}")
    if cl:
        print(f"   giá câu E kế tiếp: {cl['extra_leak']} câu A/B lọt lưới")
    if xcheck:
        print(f"   đối chứng chéo: {'KHỚP' if xcheck['ok'] else 'LỆCH'} "
              f"({xcheck['n_common']} câu, max {xcheck['max_diff']:.1e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

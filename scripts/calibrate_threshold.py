"""
Hiệu chỉnh ngưỡng grader bằng LEAVE-ONE-OUT CV (DEC-051).
==========================================================
Trả lời câu hỏi mà DEC-039 để ngỏ: **ngưỡng này khái quát được bao nhiêu?**

VÌ SAO KHÔNG DÙNG TẬP GIỮ LẠI (holdout) như DEC-039 viết ban đầu
-----------------------------------------------------------------
Chỉ có 51 câu tham gia hiệu chỉnh (E21 + A/B30; nhóm D bị policy gate chặn
TRƯỚC retrieval nên không nằm trên đường hiệu chỉnh). Cắt 40% ra làm holdout thì:

    mẫu số coverage  21 -> 8 câu   (mỗi câu 12,5 điểm phần trăm)
    mẫu số leakage   30 -> 12 câu

Quan sát "0 câu lọt lưới" trên n câu chỉ chứng minh leakage < 3/n (quy tắc số
ba, 95%). Tức holdout **làm yếu chính claim an toàn** từ "<10%" xuống "<25%".
LOOCV giữ nguyên mẫu số 21/30 mà vẫn không thiên lệch: mỗi câu được chấm đúng
một lần, luôn bởi một ngưỡng CHƯA từng nhìn thấy nó.

VÌ SAO LEAVE-ONE-OUT chứ không phải 5-fold
-------------------------------------------
Ngưỡng ở đây là hàm của **điểm A/B cao nhất** — một thống kê thứ tự cực trị,
thứ mong manh nhất với mẫu. LOOCV bỏ ra đúng một câu mỗi lượt, nên nó kiểm
được đúng cái fold đáng sợ nhất: fold bỏ ra chính câu đang giữ kỷ lục. 5-fold
làm mờ hiệu ứng đó đi. n=51 nên 51 lượt khớp lại vẫn xong trong mili-giây.

⚠️ Kết quả đo **bác bỏ** giả thiết ban đầu là ngưỡng mong manh: bỏ A-01 ra thì
ngưỡng chỉ tụt +2,430 → +2,329, còn A-01 (+2,153) **vẫn bị từ chối**, dư biên
0,176 logit. Biên độ ngưỡng qua 51 fold chỉ 0,306 logit, 3 giá trị phân biệt.
Đừng viết lại chỗ này theo trực giác "cực trị thì phải mong manh" — ở đây dải
an toàn đủ rộng nên nó không mong manh, và đó là kết quả có lợi đã đo được.

⚠️ ĐIỀU PHẢI NÓI RÕ TRONG BÁO CÁO: LOOCV ước lượng **quy trình chọn ngưỡng**,
không ước lượng con số cụ thể bạn đóng vào `config.yaml`. Đổi lại, con số đóng
vào đó khớp trên toàn bộ 51 câu nên nó là bản tốt nhất của chính quy trình ấy.

CHẠY
----
  python scripts/calibrate_threshold.py          # thuần số, mili-giây
  # cần data/processed/calibration_scores.json — sinh bằng:
  #   python scripts/eval_retrieval.py --sizes 512 --modes hybrid \
  #       --groups A,B,D,E --out docs/retrieval-eval-deploy --dump-scores
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Khoảng tin cậy + quy tắc số ba lấy từ MỘT chỗ duy nhất. Bản sao cũ nằm ngay
# trong file này đã xoá: hai định nghĩa CI trong cùng một báo cáo là đúng loại
# trôi đã phải vá ba lần (DEC-044/045/046).
from src.eval.stats import fmt_pct, rule_of_three  # noqa: E402

SCORES = ROOT / "data" / "processed" / "calibration_scores.json"
OUT = ROOT / "docs" / "threshold-calibration.md"

ABSTAIN_GROUPS = ("A", "B")  # phải TỪ CHỐI: corpus không có tài liệu
ANSWER_GROUPS = ("E",)       # phải TRẢ LỜI: corpus có tài liệu


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def pick_threshold(cal: list[dict]) -> tuple[float | None, float, float | None]:
    """QUY TRÌNH chọn ngưỡng — hàm duy nhất được phép nhìn dữ liệu hiệu chỉnh.

    ``lo`` = điểm cao nhất trong nhóm PHẢI TỪ CHỐI. Ngưỡng phải vượt nó, nếu
    không có câu A/B lọt lưới ngay trên chính tập chọn.
    ``hi`` = điểm THẤP NHẤT trong nhóm PHẢI TRẢ LỜI mà còn vượt ``lo`` — tức
    câu E rẻ nhất còn cứu được. Lấy trung điểm để có biên đều hai phía.

    Trả về ``(tau, lo, hi)``. ``hi=None`` nghĩa là không câu E nào vượt được
    ``lo``: dải an toàn rỗng, ngưỡng đặt sát trên ``lo`` và coverage = 0.
    """
    lo = max(r["max_logit"] for r in cal if r["group"] in ABSTAIN_GROUPS)
    above = [r["max_logit"] for r in cal
             if r["group"] in ANSWER_GROUPS and r["max_logit"] > lo]
    if not above:
        return (lo + 1e-9, lo, None)
    hi = min(above)
    return ((lo + hi) / 2, lo, hi)


def evaluate(cal: list[dict], tau: float) -> dict:
    e = [r for r in cal if r["group"] in ANSWER_GROUPS]
    ab = [r for r in cal if r["group"] in ABSTAIN_GROUPS]
    answered = [r for r in e if r["max_logit"] >= tau]
    leaked = [r for r in ab if r["max_logit"] >= tau]
    return {
        "answered": len(answered), "e_total": len(e),
        "leaked": len(leaked), "ab_total": len(ab),
        "leaked_ids": [r["qid"] for r in leaked],
        # Trong số câu E được trả lời, bao nhiêu câu THẬT SỰ có bài vàng ở
        # top-5. Coverage cao mà cột này thấp = tự tin bằng tài liệu sai (DEC-039).
        "answered_with_gold": sum(
            1 for r in answered
            if r["gold_rank"] is not None and r["gold_rank"] <= 5
        ),
    }


def loocv(cal: list[dict]) -> dict:
    """Mỗi câu bị chấm đúng một lần, bởi ngưỡng chọn trên 50 câu còn lại."""
    taus, answered, leaked_ids, folds = [], 0, [], []
    for i, q in enumerate(cal):
        rest = cal[:i] + cal[i + 1:]
        tau, lo, hi = pick_threshold(rest)
        taus.append(tau)
        hit = q["max_logit"] >= tau
        if q["group"] in ANSWER_GROUPS:
            answered += int(hit)
        elif hit:
            leaked_ids.append(q["qid"])
        folds.append({"qid": q["qid"], "group": q["group"], "tau": tau,
                      "score": q["max_logit"], "hit": hit})
    n_e = sum(1 for r in cal if r["group"] in ANSWER_GROUPS)
    n_ab = sum(1 for r in cal if r["group"] in ABSTAIN_GROUPS)
    return {
        "answered": answered, "e_total": n_e,
        "leaked": len(leaked_ids), "ab_total": n_ab,
        "leaked_ids": leaked_ids,
        "taus": taus, "folds": folds,
    }


def ceiling(cal: list[dict]) -> dict:
    """TRẦN coverage ở mức leakage 0 — ngưỡng có phải chỗ nghẽn không?

    Câu E nào có điểm **thấp hơn câu A/B cao nhất** thì KHÔNG ngưỡng nào cứu
    được: kéo ngưỡng xuống đủ để trả lời nó là đồng thời cho câu A/B kia lọt
    lưới. Nên trần này do **truy hồi** quyết định, không do hiệu chỉnh.

    Nếu coverage đo được đã chạm trần thì tinh chỉnh ngưỡng là vô ích — phải
    sửa ở tầng truy hồi hoặc chấp nhận trần đó và ghi vào Limitations.
    """
    lo = max(r["max_logit"] for r in cal if r["group"] in ABSTAIN_GROUPS)
    e = [r for r in cal if r["group"] in ANSWER_GROUPS]
    reachable = [r for r in e if r["max_logit"] > lo]
    unreachable = sorted(
        (r for r in e if r["max_logit"] <= lo), key=lambda r: -r["max_logit"]
    )
    gap = (min(r["max_logit"] for r in reachable)
           - max(r["max_logit"] for r in unreachable)) if reachable and unreachable else None
    # Tách câu không cứu được thành HAI loại — cách sửa khác hẳn nhau:
    #   truy hồi hỏng      -> bài vàng không vào pool  -> sửa ở tầng truy hồi
    #   thang điểm hỏng    -> bài vàng ở top-5 mà điểm vẫn âm -> ĐỔI TÍN HIỆU
    #                         tin cậy; tăng recall không cứu được câu nào
    miss = [r for r in unreachable if r["gold_rank"] is None]
    scored_low = [r for r in unreachable
                  if r["gold_rank"] is not None and r["gold_rank"] <= 5]
    return {
        "ab_max": lo, "reachable": len(reachable), "e_total": len(e),
        "unreachable_ids": [r["qid"] for r in unreachable],
        "unreachable": unreachable,
        "retrieval_miss": [r["qid"] for r in miss],
        "scored_low": [(r["qid"], r["gold_rank"], r["max_logit"]) for r in scored_low],
        "cliff": gap,
    }


def main() -> None:
    if not SCORES.exists():
        sys.exit(
            f"!! Thiếu {SCORES.relative_to(ROOT)}. Sinh bằng:\n"
            f"   python scripts/eval_retrieval.py --sizes 512 --modes hybrid "
            f"--groups A,B,D,E --out docs/retrieval-eval-deploy --dump-scores"
        )
    payload = json.loads(SCORES.read_text(encoding="utf-8"))
    conf = payload["config"]
    rows = payload["scores"]
    cal = [r for r in rows
           if r["group"] in ABSTAIN_GROUPS + ANSWER_GROUPS]
    n_d = sum(1 for r in rows if r["group"] == "D")

    tau_full, lo, hi = pick_threshold(cal)
    full = evaluate(cal, tau_full)
    cv = loocv(cal)
    ceil = ceiling(cal)
    taus = cv["taus"]

    print(f"Cấu hình: size={conf['size']} · mode={conf['mode']} · "
          f"max_length={conf['max_length']} · top_k_dense={conf['top_k_dense']}")
    print(f"Tham gia hiệu chỉnh: {len(cal)} câu "
          f"(nhóm D {n_d} câu bị policy gate chặn trước retrieval -> loại)\n")

    print(f"[1] KHỚP TRÊN TOÀN BỘ {len(cal)} CÂU — LẠC QUAN, là con số ĐÓNG vào config")
    print(f"    dải an toàn ({lo:+.2f}, {hi:+.2f}] · "
          f"ngưỡng = {tau_full:+.3f} logit = sigmoid {sigmoid(tau_full):.3f}")
    print(f"    coverage {full['answered']}/{full['e_total']} "
          f"(có bài vàng top-5: {full['answered_with_gold']})")
    print(f"    leakage  {full['leaked']}/{full['ab_total']}  "
          f"<- ĐÚNG THEO ĐỊNH NGHĨA, không phải phát hiện thực nghiệm")

    print(f"\n[2] LOOCV — con số THỰC SỰ BẢO VỆ ĐƯỢC")
    print(f"    coverage {fmt_pct(cv['answered'], cv['e_total'])}")
    print(f"    leakage  {fmt_pct(cv['leaked'], cv['ab_total'])}")
    if cv["leaked"]:
        print(f"    câu lọt lưới: {cv['leaked_ids']}")
    else:
        print(f"    0 lọt lưới trên {cv['ab_total']} câu -> chỉ chứng minh được "
              f"leakage < {100 * rule_of_three(cv['ab_total']):.0f}%")

    print("\n[3] TRẦN COVERAGE Ở LEAKAGE 0 — ngưỡng có phải chỗ nghẽn không?")
    print(f"    câu A/B cao nhất: {ceil['ab_max']:+.3f}")
    print(f"    câu E vượt được nó: {ceil['reachable']}/{ceil['e_total']} = "
          f"TRẦN {100 * ceil['reachable'] / ceil['e_total']:.0f}%")
    print(f"    KHÔNG ngưỡng nào cứu được: {ceil['unreachable_ids']}")
    if ceil["cliff"] is not None:
        print(f"    vực giữa hai nhóm: {ceil['cliff']:.2f} logit "
              f"-> phân bố nhóm E LƯỠNG CỰC")
    reached = cv["answered"] == ceil["reachable"]
    print(f"    -> coverage LOOCV {'ĐÃ CHẠM TRẦN' if reached else 'chưa chạm trần'} "
          f"({cv['answered']}/{ceil['reachable']})")
    print(f"    truy hồi HỎNG (bài vàng không vào pool): "
          f"{ceil['retrieval_miss'] or 'không có'}")
    print(f"    THANG ĐIỂM hỏng (bài vàng ở top-5 mà điểm vẫn dưới mốc A/B):")
    for qid, rank, sc in ceil["scored_low"]:
        print(f"      {qid}: bài vàng hạng {rank}, max_logit {sc:+.3f}")
    if len(ceil["scored_low"]) > len(ceil["retrieval_miss"]):
        print(f"    ⛔ Phần lớn trần là do THANG ĐIỂM, không do truy hồi — "
              f"tăng recall KHÔNG cứu được các câu này.")

    print(f"\n[4] ĐỘ MONG MANH CỦA NGƯỠNG (qua {len(taus)} fold)")
    print(f"    min {min(taus):+.3f} · trung vị {statistics.median(taus):+.3f} · "
          f"max {max(taus):+.3f} · biên độ {max(taus) - min(taus):.3f} logit")
    print(f"    số giá trị phân biệt: {len(set(round(t, 6) for t in taus))}")

    write_report(conf, cal, n_d, tau_full, lo, hi, full, cv, ceil)
    print(f"\n[out] {OUT.relative_to(ROOT)}")


def write_report(conf, cal, n_d, tau_full, lo, hi, full, cv, ceil) -> None:
    taus = cv["taus"]
    md = [
        "# Hiệu chỉnh ngưỡng grader — LOOCV",
        "",
        "> Sinh bằng `python scripts/calibrate_threshold.py` từ "
        "`data/processed/calibration_scores.json`. Thuần số, không gọi mạng.",
        f"> Cấu hình: `size={conf['size']}` · `mode={conf['mode']}` · "
        f"`max_length={conf['max_length']}` · `top_k_dense={conf['top_k_dense']}`",
        "",
        f"**{len(cal)} câu** tham gia hiệu chỉnh (E{sum(1 for r in cal if r['group'] == 'E')} "
        f"+ A/B{sum(1 for r in cal if r['group'] in ABSTAIN_GROUPS)}). "
        f"Nhóm D ({n_d} câu) **không tham gia**: policy gate chặn chúng TRƯỚC "
        "retrieval nên chúng không nằm trên đường hiệu chỉnh (DEC-024).",
        "",
        "## Ba con số, gọi tên thẳng",
        "",
        "| | ngưỡng | coverage (E) | leakage (A/B) | dùng để |",
        "|---|---|---|---|---|",
        f"| Khớp trên toàn bộ {len(cal)} câu | **{tau_full:+.3f}** "
        f"(sigmoid {sigmoid(tau_full):.3f}) | {full['answered']}/{full['e_total']} | "
        f"{full['leaked']}/{full['ab_total']} | con số **đóng vào `config.yaml`** |",
        f"| **LOOCV** | thay đổi theo fold | "
        f"{fmt_pct(cv['answered'], cv['e_total'])} | "
        f"{fmt_pct(cv['leaked'], cv['ab_total'])} | con số **báo cáo ở Chương 4** |",
        "",
        f"⚠️ **`leakage {full['leaked']}/{full['ab_total']}` ở dòng đầu là TỰ ĐỘNG ĐÚNG, "
        "không phải kết quả.** Quy trình chọn ngưỡng đặt nó ngay TRÊN điểm A/B cao "
        "nhất, nên bằng xây dựng thì không câu A/B nào vượt được. Trích nó như một "
        "phát hiện thực nghiệm là sai. Dòng LOOCV mới là con số có nội dung.",
        "",
        "## Quy trình chọn ngưỡng (bị đánh giá, không phải bị giả định)",
        "",
        f"1. `lo` = điểm cao nhất của nhóm PHẢI TỪ CHỐI = **{lo:+.3f}**",
        f"2. `hi` = điểm thấp nhất của nhóm PHẢI TRẢ LỜI mà còn vượt `lo` = "
        f"**{hi:+.3f}**" if hi is not None else "2. `hi` = không có câu E nào vượt `lo`",
        f"3. ngưỡng = trung điểm = **{tau_full:+.3f}**",
        "",
        "LOOCV đánh giá đúng **quy trình này**: mỗi lượt bỏ ra 1 câu, chạy lại 3 "
        "bước trên 50 câu còn lại, rồi chấm câu bị bỏ ra.",
        "",
        "## Trần coverage — ngưỡng KHÔNG phải chỗ nghẽn",
        "",
        f"Câu A/B cao điểm nhất đạt **{ceil['ab_max']:+.3f}**. Câu E nào thấp hơn "
        "mốc đó thì **không ngưỡng nào cứu được**: kéo ngưỡng xuống đủ để trả lời "
        "nó là đồng thời cho câu A/B kia lọt lưới.",
        "",
        f"- Câu E vượt được mốc: **{ceil['reachable']}/{ceil['e_total']} = "
        f"{100 * ceil['reachable'] / ceil['e_total']:.0f}%** — đây là **TRẦN** "
        "coverage ở mức leakage 0.",
        f"- Không thể cứu: {', '.join('`' + q + '`' for q in ceil['unreachable_ids'])}.",
        "",
        "### ⛔ Trần này là trần của THANG ĐIỂM, không phải của truy hồi",
        "",
        "| câu | max-logit | hạng bài vàng | chẩn đoán |",
        "|---|---|---|---|",
        *[f"| `{r['qid']}` | {r['max_logit']:+.3f} | "
          f"{r['gold_rank'] if r['gold_rank'] is not None else '— (không vào pool)'} | "
          f"{'truy hồi hỏng' if r['gold_rank'] is None else 'ĐÃ truy hồi đúng, bị chấm âm'} |"
          for r in ceil["unreachable"]],
        "",
        (f"**{len(ceil['scored_low'])}/{len(ceil['unreachable_ids'])} câu không cứu "
         "được đã truy hồi ĐÚNG bài vàng** (hạng 1–2) rồi bị reranker chấm âm. "
         "Tăng recall **không cứu được** chúng — chỗ hỏng là *tín hiệu tin cậy*, "
         "không phải *khả năng tìm tài liệu*. Đây là dạng gây hại nhất của DEC-039 "
         "(\"điểm bám độ cùng chủ đề, không bám độ đúng\"): hệ thống từ chối đúng "
         "những câu nó **có** tài liệu để trả lời."
         if len(ceil["scored_low"]) > len(ceil["retrieval_miss"]) else ""),
        (f"- Vực giữa hai nhóm: **{ceil['cliff']:.2f} logit**. Phân bố điểm nhóm E "
         "**lưỡng cực**, không liên tục." if ceil["cliff"] is not None else ""),
        "",
        f"→ Coverage LOOCV **{cv['answered']}/{ceil['reachable']} của trần**. "
        + ("**Đã chạm trần**: tinh chỉnh ngưỡng thêm là vô ích, chỗ nghẽn nằm ở "
           "tầng TRUY HỒI, không ở hiệu chỉnh. Muốn coverage cao hơn thì phải sửa "
           "truy hồi, hoặc chấp nhận trần này và ghi vào Limitations."
           if cv["answered"] == ceil["reachable"] else
           "Chưa chạm trần: còn dư địa cho ngưỡng."),
        "",
        "## Độ mong manh",
        "",
        f"Qua {len(taus)} fold, ngưỡng chạy từ **{min(taus):+.3f}** đến "
        f"**{max(taus):+.3f}** (biên độ **{max(taus) - min(taus):.3f}** logit, "
        f"{len(set(round(t, 6) for t in taus))} giá trị phân biệt).",
        "",
        "Ngưỡng là hàm của **điểm A/B cao nhất** — một thống kê thứ tự cực trị. "
        "Bỏ đúng câu đang giữ kỷ lục ra khỏi tập chọn là ngưỡng tụt xuống câu cao "
        "nhì, và câu bị bỏ ra thường lọt lưới. Đó là phép đo trực tiếp mức độ phụ "
        "thuộc của ngưỡng vào **một** câu.",
        "",
    ]
    if cv["leaked_ids"]:
        md += [f"Câu lọt lưới trong LOOCV: "
               f"{', '.join('`' + q + '`' for q in cv['leaked_ids'])}.", ""]
    else:
        md += [
            f"0 câu lọt lưới trong LOOCV. ⚠️ Điều đó chỉ chứng minh được "
            f"**leakage < {100 * rule_of_three(cv['ab_total']):.0f}%** (quy tắc số ba, "
            f"n={cv['ab_total']}), KHÔNG chứng minh leakage bằng 0.",
            "",
        ]
    md += [
        "## Giới hạn — phải vào báo cáo",
        "",
        "- LOOCV ước lượng **quy trình chọn ngưỡng**, không ước lượng con số cụ "
        "thể đóng vào `config.yaml`. Con số đó khớp trên toàn bộ dữ liệu nên "
        "không được kiểm trên dữ liệu chưa thấy — đây là cái giá đã trả có ý "
        "thức để giữ mẫu số 21/30 thay vì 8/12 (DEC-051).",
        f"- Mỗi câu E vẫn nặng **{100 / cv['e_total']:.1f} điểm** coverage. CV "
        "không làm test set lớn lên; nó chỉ bỏ được thiên lệch chọn.",
        "- Điểm bám **độ cùng chủ đề**, không bám **độ đúng** (DEC-039). Cột "
        "\"có bài vàng top-5\" ở trên là chỗ nhìn ra điều đó: coverage cao mà cột "
        "kia thấp nghĩa là hệ thống tự tin bằng tài liệu không chứa đáp án.",
        "",
    ]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()

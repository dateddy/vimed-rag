"""Đường cong risk–coverage — biên hiệu quả của phép đánh đổi trả lời/từ chối.

⚠️⚠️ **ĐƯỜNG CONG NÀY KHÔNG DÙNG ĐỂ CHỌN NGƯỠNG** (DEC-063).
Bản stub cũ của file này viết *"ngưỡng grader thật sẽ được chọn từ đường cong
này"*, và `contracts/constraints.md` cũng hứa như vậy từ Session 2. Thực tế
ngưỡng **đã được chọn xong** ở DEC-051 (2026-09-08) bằng LOOCV, và đã đóng vào
``config.yaml``: ``+2,430 logit = sigmoid 0,919``.

Chọn lại ngưỡng từ đường cong dựng trên **đúng 51 câu ấy** là khớp-trên-tập-
đánh-giá — chính cái bẫy mà LOOCV sinh ra để tránh. Nên vai trò đổi:

    KHÔNG phải cơ chế CHỌN ngưỡng
    MÀ LÀ bằng chứng điểm vận hành đang nằm trên BIÊN HIỆU QUẢ

và là **"1 biểu đồ"** mà `constraints.md` đòi cho claim *"hệ thống biết khi nào
KHÔNG đủ căn cứ để trả lời"*.

⚠️ **``risk`` PHỤ THUỘC TỈ LỆ TEST SET — đây là bẫy lớn nhất của module này.**
Ở coverage 100%, ``risk`` = 30/51 = **0,588**. Con số đó là **tỉ lệ câu A/B
trong test set**, không phải thuộc tính của hệ thống: test set cố ý nhồi 59%
câu không trả lời được (DEC-026/027), người bệnh thật không hỏi theo tỉ lệ đó.
Trích *"risk giảm từ 59% xuống 0%"* như một thành tựu là sai **cùng một kiểu**
với ``leakage 0/30`` mà `docs/threshold-calibration.md` đã phải cảnh báo.
Vì thế :func:`dominates` xếp hạng trên cặp **(cov_e ↑, leak_ab ↓)** chứ KHÔNG
trên ``risk``: mẫu số của ``risk`` trộn một thuộc tính của test set vào, nên
xếp hạng theo nó là xếp hạng lẫn cả cách mình dựng test set.

⚠️ **NHÓM D KHÔNG NẰM TRÊN ĐƯỜNG CONG.** Policy gate chặn 8 câu D **trước**
retrieval nên chúng không có điểm tin cậy nào — ``turns`` rỗng. Đưa vào là bịa
số. Đây là đúng lý do `contracts/corrective-loop.md` bắt tách hai cơ chế
abstain: cơ chế policy là **hằng số theo thiết kế**, chỉ cơ chế retrieval mới
nằm trên đường hiệu chỉnh. ⇒ **n = 51** (A18 + B12 + E21), không phải 59.

⚠️ **Đường cong này CHỈ hợp lệ từ DEC-061 trở đi.** Nó dựng trên điểm **lượt
1**. Trước guard, lượt 2 lật được phán quyết lượt 1, nên một đường cong lượt 1
sẽ mô tả một hệ thống không tồn tại. Sau guard, hệ quyết định **chỉ bằng lượt
1** — đường cong mô tả đúng hệ đang chạy. Guard là **điều kiện tiên quyết**
của module này, không phải việc song song.

Thuần số: đọc dict/JSONL, không mạng, không model, không đọc file.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.eval.trace_export import logit

ABSTAIN_GROUPS = ("A", "B")   # phải TỪ CHỐI: corpus không có tài liệu
ANSWER_GROUPS = ("E",)        # phải TRẢ LỜI: corpus có tài liệu
POLICY_GROUPS = ("D",)        # policy gate chặn TRƯỚC retrieval -> ngoài đường cong

CURVE_GROUPS = ABSTAIN_GROUPS + ANSWER_GROUPS


@dataclass(frozen=True)
class RiskCoveragePoint:
    """Một điểm trên đường cong = một ngưỡng.

    Giữ **số đếm thô** (``leak_ab``/``cov_e`` kèm mẫu số) chứ không chỉ giữ tỉ
    lệ: mọi bảng dưới xuôi cần mẫu số để tính khoảng tin cậy, và bắt chúng nhân
    ngược tỉ lệ ra số đếm là mở đường cho lệch một câu mà không ai thấy.
    """

    threshold: float   # thang LOGIT (cùng thang `max_logit`), không phải sigmoid
    n_ab: int
    leak_ab: int
    n_e: int
    cov_e: int

    @property
    def n_answered(self) -> int:
        return self.leak_ab + self.cov_e

    @property
    def coverage(self) -> float:
        """Tỉ lệ câu E được trả lời."""
        return self.cov_e / self.n_e if self.n_e else 0.0

    @property
    def leakage(self) -> float:
        """Tỉ lệ câu A/B bị trả lời (lẽ ra phải từ chối)."""
        return self.leak_ab / self.n_ab if self.n_ab else 0.0

    @property
    def risk(self) -> float | None:
        """Tỉ lệ sai trên phần ĐÃ trả lời — risk chọn lọc kinh điển.

        ``None`` khi chưa trả lời câu nào: risk của tập rỗng không xác định, và
        trả 0.0 ở đó sẽ vẽ ra một điểm "hoàn hảo" ở coverage 0.

        ⚠️ Đọc cảnh báo tỉ lệ test set ở docstring module trước khi trích số này.
        """
        n = self.n_answered
        return self.leak_ab / n if n else None


# --------------------------------------------------------------------------- #
# Nạp điểm tin cậy — hai nguồn, phải cho cùng một đường cong
# --------------------------------------------------------------------------- #
def scores_from_calibration(payload: dict) -> list[dict]:
    """Từ ``data/processed/calibration_scores.json`` — nguồn CHÍNH.

    Chính là file DEC-051 đã dùng để hiệu chỉnh, nên đường cong và ngưỡng chắc
    chắn cùng một thang. Lấy nguồn khác làm chính là mở đường cho đường cong và
    điểm vận hành nằm trên hai thang khác nhau — loại lỗi DEC-033 (số vẫn ra,
    chỉ là ra sai).
    """
    return [
        {"id": s["qid"], "group": s["group"], "logit": s["max_logit"]}
        for s in payload.get("scores", [])
        if s.get("group") in CURVE_GROUPS
    ]


def scores_from_runs(records: list[dict]) -> list[dict]:
    """Từ ``runs.jsonl`` — dùng để ĐỐI CHỨNG CHÉO, không phải nguồn chính.

    Đọc ``turns[0]`` vì hệ (sau DEC-061) quyết định bằng đúng lượt đó. Câu
    ``turns`` rỗng bị bỏ: đó là nhóm D bị policy gate chặn trước retrieval, và
    chúng không có điểm tin cậy nào để đặt lên đường cong.
    """
    out: list[dict] = []
    for r in records:
        if r.get("system") != "corrective" or r.get("group") not in CURVE_GROUPS:
            continue
        turns = r.get("turns") or []
        if not turns:
            continue
        t = turns[0]
        lg = t.get("logit")
        if lg is None:
            lg = logit(t.get("score"))
        if lg is None:
            continue
        out.append({"id": r["id"], "group": r["group"], "logit": lg})
    return out


def compare_sources(a: list[dict], b: list[dict], *, tol: float = 1e-5) -> dict:
    """Đối chứng hai nguồn điểm theo từng câu.

    Phép kiểm rẻ bắt đúng loại lỗi nguy hiểm nhất của đề tài: hai bảng trong
    cùng một báo cáo đứng trên hai thang điểm khác nhau. ``tol`` mặc định 1e-5
    vì ``runs.jsonl`` lưu ``score`` đã qua float32 rồi mới suy ngược ra logit —
    sai số vòng tròn cỡ 1e-6, không phải 1e-12 như đường suy trực tiếp.
    """
    ma = {s["id"]: s["logit"] for s in a}
    mb = {s["id"]: s["logit"] for s in b}
    common = sorted(set(ma) & set(mb))
    diffs = {q: abs(ma[q] - mb[q]) for q in common}
    worst = max(diffs, key=lambda q: diffs[q]) if diffs else None
    return {
        "n_a": len(ma),
        "n_b": len(mb),
        "n_common": len(common),
        "only_a": sorted(set(ma) - set(mb)),
        "only_b": sorted(set(mb) - set(ma)),
        "max_diff": diffs[worst] if worst else 0.0,
        "worst_id": worst,
        "mismatched": sorted(q for q, d in diffs.items() if d > tol),
        "ok": not (set(ma) ^ set(mb)) and all(d <= tol for d in diffs.values()),
    }


# --------------------------------------------------------------------------- #
# Dựng đường cong
# --------------------------------------------------------------------------- #
def point_at(scores: list[dict], threshold: float) -> RiskCoveragePoint:
    """Điểm của đường cong tại MỘT ngưỡng bất kỳ (kể cả ngưỡng không quan sát được).

    Quy ước ``>=`` khớp đúng grader thật: ``score >= incorrect_threshold`` thì
    trả lời (dải AMBIGUOUS vẫn là trả lời — ``ANSWER_WITH_CAUTION``, xem
    ``trace_export.ANSWERING_ACTIONS``). Đổi sang ``>`` là lệch một câu ở đúng
    những ca sát biên, tức đúng những ca đường cong sinh ra để soi.
    """
    ab = [s for s in scores if s["group"] in ABSTAIN_GROUPS]
    e = [s for s in scores if s["group"] in ANSWER_GROUPS]
    return RiskCoveragePoint(
        threshold=threshold,
        n_ab=len(ab),
        leak_ab=sum(1 for s in ab if s["logit"] >= threshold),
        n_e=len(e),
        cov_e=sum(1 for s in e if s["logit"] >= threshold),
    )


def candidate_thresholds(scores: list[dict]) -> list[float]:
    """Ngưỡng ứng viên = ĐÚNG tập điểm quan sát được, cộng một ngưỡng trên đỉnh.

    ⛔ **KHÔNG dùng ``linspace``.** Nội suy giữa hai điểm quan sát là bịa ra một
    ngưỡng mà không câu nào trong test set kiểm chứng được, và nó vẽ ra một
    đường cong **mượt** ở chỗ dữ liệu thật là một **vách**. Với 51 câu quanh
    một vực 3,06 logit (DEC-051), đường mượt là mô tả sai.

    Ngưỡng cuối (``max + 1``) là điểm "không trả lời câu nào" — coverage 0,
    cần có để đường cong chạm được đầu mút.
    """
    obs = sorted({s["logit"] for s in scores})
    return obs + [obs[-1] + 1.0] if obs else []


def compute_risk_coverage(
    scores: list[dict],
    *,
    thresholds: list[float] | None = None,
) -> list[RiskCoveragePoint]:
    """Các điểm ``(threshold, coverage, risk)`` để vẽ đường cong.

    ⚠️ Chữ ký ĐỔI so với bản stub (DEC-063): stub nhận
    ``(list[PipelineResult], list[bool])``. Hai lý do bỏ:

    * ``PipelineResult`` buộc phải dựng lại object từ JSONL không vì lý do gì —
      mọi thứ đường cong cần chỉ là ``(group, logit)``.
    * ``correct_labels: list[bool]`` **không diễn tả được test set trộn**: với
      câu A/B "đúng" nghĩa là TỪ CHỐI, với câu E "đúng" nghĩa là TRẢ LỜI. Một
      cờ bool phẳng che mất chuyện đó, và che đúng chỗ dễ đảo dấu nhất.
    """
    ths = candidate_thresholds(scores) if thresholds is None else sorted(thresholds)
    return [point_at(scores, t) for t in ths]


def operating_point(scores: list[dict], threshold_sigmoid: float) -> RiskCoveragePoint:
    """Điểm ứng với ngưỡng ĐANG đóng trong ``config.yaml`` (thang sigmoid).

    Nhận sigmoid vì đó là thứ nằm trong config, và quy đổi bằng
    ``trace_export.logit`` — hàm grader thật dùng — thay vì chép lại công thức.

    ⚠️ ``config.yaml`` lưu bản **đã làm tròn** (``0.919``), quy ngược ra
    ``+2,4288`` chứ không đúng ``+2,430`` của DEC-051. Chênh lệch đó **không
    đổi quyết định câu nào**: điểm A/B cao nhất là ``+2,153``, điểm E thấp nhất
    còn được trả lời là ``+2,708`` — cả hai cách xa hơn 0,2 logit.
    """
    return point_at(scores, logit(threshold_sigmoid))


# --------------------------------------------------------------------------- #
# Đọc đường cong: biên hiệu quả, vách, dải miễn phí
# --------------------------------------------------------------------------- #
def dominates(a: RiskCoveragePoint, b: RiskCoveragePoint) -> bool:
    """``a`` trội hẳn ``b``: phủ không kém, lọt không hơn, hơn hẳn ở ít nhất một chiều.

    Xếp hạng trên cặp **(cov_e, leak_ab)**, KHÔNG trên ``risk`` — lý do đầy đủ ở
    docstring module: mẫu số của ``risk`` trộn tỉ lệ A/B:E của test set vào.
    """
    return (
        a.cov_e >= b.cov_e
        and a.leak_ab <= b.leak_ab
        and (a.cov_e > b.cov_e or a.leak_ab < b.leak_ab)
    )


def pareto_frontier(points: list[RiskCoveragePoint]) -> list[RiskCoveragePoint]:
    """Các điểm không bị điểm nào trội hẳn."""
    return [p for p in points if not any(dominates(q, p) for q in points)]


def is_on_frontier(point: RiskCoveragePoint, points: list[RiskCoveragePoint]) -> bool:
    """Điểm vận hành có nằm trên biên hiệu quả không — câu hỏi chính của module."""
    return not any(dominates(q, point) for q in points)


def coverage_gap(scores: list[dict], threshold: float) -> dict | None:
    """Vực giữa câu E thấp điểm nhất ĐƯỢC trả lời và câu E cao điểm nhất BỊ từ chối.

    Đây là con số làm cho đường cong có nội dung: nó đo **độ rộng của bậc
    thang**. DEC-051 đặt tên nó là "vực 3,06 logit" và gọi phân bố nhóm E là
    **lưỡng cực**; hàm này tính lại chính con số đó từ dữ liệu thay vì chép.

    ``None`` khi mọi câu E cùng một phía của ngưỡng (không có bậc nào để đo).
    """
    e = [s for s in scores if s["group"] in ANSWER_GROUPS]
    ans = [s["logit"] for s in e if s["logit"] >= threshold]
    rej = [s["logit"] for s in e if s["logit"] < threshold]
    if not ans or not rej:
        return None
    return {
        "lowest_answered": min(ans),
        "highest_rejected": max(rej),
        "gap": min(ans) - max(rej),
    }


def cliff(points: list[RiskCoveragePoint], *, from_cov_e: int) -> dict | None:
    """Giá của câu E KẾ TIẾP: phải cho thêm bao nhiêu câu A/B lọt lưới.

    Đây là cách đọc đường cong khi nó là bậc thang chứ không phải dốc: câu hỏi
    có nghĩa không phải *"đánh đổi bao nhiêu mỗi điểm phần trăm"* mà *"câu tiếp
    theo giá bao nhiêu"*.

    ``None`` khi không ngưỡng nào cho thêm câu E nào (đã chạm đỉnh coverage).
    """
    base = [p for p in points if p.cov_e == from_cov_e]
    better = [p for p in points if p.cov_e > from_cov_e]
    if not base or not better:
        return None
    # Rẻ nhất theo LỌT LƯỚI trước, phủ nhiều hơn để phá hoà — cùng giá thì lấy
    # cái phủ được nhiều hơn.
    cheapest = min(better, key=lambda p: (p.leak_ab, -p.cov_e))
    floor = min(base, key=lambda p: p.leak_ab)
    return {
        "from_cov_e": from_cov_e,
        "to_cov_e": cheapest.cov_e,
        "extra_leak": cheapest.leak_ab - floor.leak_ab,
        "threshold_drop": floor.threshold - cheapest.threshold,
        "point": cheapest,
    }


def free_band(points: list[RiskCoveragePoint], *, cov_e: int) -> dict | None:
    """Dải ngưỡng mà coverage ĐỨNG YÊN trong khi leakage tụt — giảm lọt MIỄN PHÍ.

    Sự tồn tại của dải này là điều đáng báo cáo: nó nói rằng phần lớn quãng
    đường từ "lọt 9 câu" về "lọt 0 câu" **không tốn một câu coverage nào**. Nếu
    đánh đổi là thật sự liên tục thì dải này phải rỗng.

    ``None`` khi chỉ có một ngưỡng đạt ``cov_e`` (không có dải nào).
    """
    same = [p for p in points if p.cov_e == cov_e]
    if len(same) < 2:
        return None
    lo = min(same, key=lambda p: p.threshold)
    hi = max(same, key=lambda p: p.threshold)
    return {
        "cov_e": cov_e,
        "lo": lo,
        "hi": hi,
        "width": hi.threshold - lo.threshold,
        "leak_saved": lo.leak_ab - hi.leak_ab,
    }

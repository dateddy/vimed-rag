"""Leakage SAU REWRITE — cái lỗ mà LOOCV chưa chạm tới (DEC-051/052).

Hiệu chỉnh ngưỡng chấm trên điểm của **lượt truy hồi đầu**: dữ liệu vào
``calibrate_threshold.py`` là một điểm ``max_logit`` cho mỗi câu, lấy từ một
lượt ``eval_retrieval.py``. Nhưng hệ thống thật cho mỗi câu INCORRECT thêm
**một lần thử thứ hai** (rewrite → re-retrieve → grade lại), và lượt đó
**không** nằm trong dữ liệu hiệu chỉnh.

Nên câu ``leakage 0/30`` của DEC-051 là phát biểu về **lượt đầu**, không phải
về hệ thống. Module này tách ba con số rất dễ bị gộp làm một:

    leakage lượt 1   LOOCV đã đo — nhắc lại ở đây chỉ để đối chiếu
    leakage lượt 2   CHƯA TỪNG ĐO. Rewrite có kéo câu A/B lên trên ngưỡng không?
    leakage cuối     con số THẬT của hệ thống: ``action`` cuối là trả lời

⚠️ **Vì sao lượt 2 có thể tệ hơn lượt 1 chứ không tự động tốt hơn.** Rewrite
tồn tại để lấp khoảng trống từ vựng (DEC-046: *"tiểu đường ăn gì"* → *"Thực
phẩm nên ăn và kiêng cho người **đái tháo đường**"*). Với câu nhóm A/B — hỏi
về thực thể corpus **không có** — nó không thể tìm ra tài liệu đúng, nhưng nó
CÓ THỂ viết lại thành một câu trùng từ vựng corpus hơn, và điểm rerank thì bám
**độ cùng chủ đề** chứ không bám **độ đúng** (DEC-039). Tức chính cơ chế sửa
sai lại là cơ chế có thể đẩy câu không trả lời được lên trên ngưỡng. DEC-048
đã bắt được đúng dạng đó một lần (*"trồng lúa nước"* → *"gạo trắng và nguy cơ
đái tháo đường"*).

Thuần số: đọc bản ghi của :mod:`src.eval.trace_export`, không mạng, không file.
"""

from __future__ import annotations

import math
import statistics

from src.eval.stats import sign_test, wilson
from src.eval.trace_export import ANSWERING_ACTIONS

ABSTAIN_GROUPS = ("A", "B")   # phải TỪ CHỐI: corpus không có tài liệu
ANSWER_GROUPS = ("E",)        # phải TRẢ LỜI: corpus có tài liệu
POLICY_GROUPS = ("D",)        # bị policy gate chặn TRƯỚC retrieval


def to_logit(p: float) -> float:
    """Ngưỡng sigmoid → logit, để so cùng thang với ``turns[i]["logit"]``."""
    return math.log(p / (1.0 - p))


def is_answering(rec: dict) -> bool:
    """Hệ thống đã trả lời câu này chưa (kể cả bản kèm cảnh báo)?"""
    return rec.get("action") in ANSWERING_ACTIONS


def turn(rec: dict, i: int) -> dict | None:
    """Lượt truy hồi thứ ``i`` (0-based), ``None`` nếu câu không đi tới đó."""
    turns = rec.get("turns") or []
    return turns[i] if len(turns) > i else None


def _delta(rec: dict) -> float | None:
    """``logit`` lượt 2 − lượt 1. ``None`` nếu thiếu một trong hai."""
    t1, t2 = turn(rec, 0), turn(rec, 1)
    if not t1 or not t2:
        return None
    if t1.get("logit") is None or t2.get("logit") is None:
        return None
    return t2["logit"] - t1["logit"]


def analyze_group(records: list[dict], groups: tuple[str, ...]) -> dict:
    """Tách kết cục của một nhóm câu thành ba mốc: lượt 1, lượt 2, cuối.

    Tên trường cố ý **trung tính** (``answered_*``, không phải ``leaked_*``):
    cùng một phép đếm mang hai ý nghĩa ngược nhau tuỳ nhóm — với A/B "đã trả
    lời" là **leakage**, với E thì đó là **coverage**. Nhét cách diễn giải vào
    tên trường là mời gọi đọc nhầm dấu ở đúng chỗ nguy hiểm nhất; phần diễn
    giải để cho bảng báo cáo lo.

    ``answered_turn1`` = câu **không** bị chấm INCORRECT ở lượt đầu → được
    quyết ngay, tức đúng thứ LOOCV đã đo.
    ``answered_turn2`` = câu BỊ chấm INCORRECT ở lượt đầu (hiệu chỉnh làm đúng
    việc của nó) nhưng vẫn được trả lời **sau rewrite** — phần hiệu chỉnh
    không nhìn thấy. Với A/B đây là leakage mới; với E đây là câu được rewrite
    cứu.
    """
    rows = [r for r in records if r.get("group") in groups]

    decided_turn1 = [r for r in rows if (turn(r, 0) or {}).get("state") != "INCORRECT"]
    went_turn2 = [r for r in rows if len(r.get("turns") or []) > 1]

    deltas = [(r["id"], _delta(r)) for r in went_turn2]
    deltas = [(qid, d) for qid, d in deltas if d is not None]
    vals = [d for _, d in deltas]

    return {
        "n": len(rows),
        "ids": [r["id"] for r in rows],
        "n_turn2": len(went_turn2),
        "answered_turn1": [r["id"] for r in decided_turn1 if is_answering(r)],
        "answered_turn2": [r["id"] for r in went_turn2 if is_answering(r)],
        "answered_final": [r["id"] for r in rows if is_answering(r)],
        "refused_final": [r["id"] for r in rows if not is_answering(r)],
        "deltas": deltas,
        "delta_median": statistics.median(vals) if vals else None,
        "delta_max": max(vals) if vals else None,
        "sign_test": sign_test(vals) if vals else None,
    }


def margin(records: list[dict], groups: tuple[str, ...], threshold_logit: float) -> dict:
    """Biên còn lại giữa điểm cao nhất của nhóm và ngưỡng, ở TỪNG lượt.

    Đây là con số trả lời "suýt lọt lưới hay còn xa": ``leaked = 0`` với biên
    0,02 logit và ``leaked = 0`` với biên 1,5 logit là hai tình trạng an toàn
    khác hẳn nhau, mà cả hai đều in ra ``0/30``. Không có cột này thì báo cáo
    không phân biệt được may mắn với dư địa.
    """
    out = {}
    for i, name in ((0, "turn1"), (1, "turn2")):
        vals = [
            (r["id"], t["logit"])
            for r in records
            if r.get("group") in groups
            for t in [turn(r, i)]
            if t and t.get("logit") is not None
        ]
        if not vals:
            out[name] = None
            continue
        qid, top = max(vals, key=lambda kv: kv[1])
        out[name] = {
            "top_id": qid,
            "top_logit": top,
            "margin": threshold_logit - top,
            "n_scored": len(vals),
        }
    return out


def policy_check(records: list[dict]) -> dict:
    """Nhóm D có đi đúng cửa không — policy gate, không phải retrieval.

    Một câu D ra ABSTAIN **do retrieval** là ABSTAIN đúng vì lý do sai: nó
    nghĩa là gate trượt và hệ thống chỉ tình cờ không tìm thấy tài liệu. Trên
    câu D khác, cùng lỗi đó sẽ thành câu trả lời. Đếm riêng ra để không bị
    ``expected_action`` che mất.
    """
    rows = [r for r in records if r.get("group") in POLICY_GROUPS]
    by_mech: dict[str, list[str]] = {}
    for r in rows:
        by_mech.setdefault(str(r.get("abstain_mechanism")), []).append(r["id"])
    return {
        "n": len(rows),
        "by_mechanism": by_mech,
        "rules": sorted({r.get("policy_rule") for r in rows if r.get("policy_rule")}),
        "answered": [r["id"] for r in rows if is_answering(r)],
    }


def analyze(records: list[dict], *, incorrect_threshold: float) -> dict:
    """Toàn bộ phân tích trên một lô bản ghi ``system="corrective"``.

    ``incorrect_threshold`` lấy từ ``config.grader`` chứ **không** hard-code:
    ngưỡng đã đổi một lần rồi (DEC-052) và sẽ còn đổi nếu test set lớn lên.
    """
    corrective = [r for r in records if r.get("system") == "corrective"]
    tau = to_logit(incorrect_threshold)
    return {
        "n_records": len(corrective),
        "threshold_sigmoid": incorrect_threshold,
        "threshold_logit": tau,
        "abstain": analyze_group(corrective, ABSTAIN_GROUPS),
        "answer": analyze_group(corrective, ANSWER_GROUPS),
        "margin_ab": margin(corrective, ABSTAIN_GROUPS, tau),
        "policy": policy_check(corrective),
    }


def wilson_pct(k: int, n: int) -> tuple[float, float, float]:
    """``(tỉ lệ, cận dưới, cận trên)`` theo phần trăm — tiện cho bảng."""
    lo, hi = wilson(k, n)
    return (100 * k / n if n else 0.0, 100 * lo, 100 * hi)

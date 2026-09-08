"""Test phân tích leakage sau rewrite (`src/eval/leakage.py`).

Thuần dict — không dựng pipeline, không chạm mạng. Bản ghi được **bịa bằng
tay** ở đây là cố ý: cái cần khoá là *cách đếm*, và cách đếm phải đúng trên
những tình huống mà test set thật hiện chưa có (dải AMBIGUOUS đang RỖNG,
nhánh `ANSWER_WITH_CAUTION` chưa từng chạy trên dữ liệu thật — DEC-052). Chờ
dữ liệu thật sinh ra chúng thì phép đếm không bao giờ được kiểm.
"""

import math

import pytest

from src.eval.leakage import (
    analyze,
    analyze_group,
    is_answering,
    margin,
    policy_check,
    to_logit,
    turn,
)
from src.eval.stats import rule_of_three, sign_test, wilson

TAU_SIGMOID = 0.919                    # ngưỡng đang dùng (DEC-052)
TAU = to_logit(TAU_SIGMOID)            # ≈ +2.430 logit


def _rec(qid, group, action, logits, expected="ABSTAIN"):
    """Bản ghi tối thiểu mà `leakage.py` cần.

    ``logits`` = điểm từng lượt. State suy ra từ ngưỡng để bản ghi giả không
    tự mâu thuẫn: dưới ngưỡng là INCORRECT (đi tiếp sang rewrite), từ ngưỡng
    trở lên là CORRECT.
    """
    turns = [
        {
            "i": i,
            "logit": x,
            "score": 1 / (1 + math.exp(-x)),
            "state": "INCORRECT" if x < TAU else "CORRECT",
            "note": "",
        }
        for i, x in enumerate(logits)
    ]
    return {
        "id": qid,
        "group": group,
        "system": "corrective",
        "action": action,
        "expected_action": expected,
        "turns": turns,
        "abstain_mechanism": None if action != "ABSTAIN" else "retrieval",
        "policy_rule": None,
    }


# --------------------------------------------------------------------- #
# helper cơ bản
# --------------------------------------------------------------------- #
def test_answer_with_caution_counts_as_answering():
    """Nửa điểm không tồn tại: trả lời kèm cảnh báo vẫn là đã trả lời."""
    assert is_answering({"action": "ANSWER"})
    assert is_answering({"action": "ANSWER_WITH_CAUTION"})
    assert not is_answering({"action": "ABSTAIN"})


def test_turn_is_safe_on_policy_abstain():
    """Câu nhóm D không có lượt truy hồi nào — truy cập phải trả None, không nổ."""
    rec = {"turns": []}
    assert turn(rec, 0) is None and turn(rec, 1) is None


def test_to_logit_matches_the_threshold_in_config():
    """+2,430 logit = sigmoid 0,919 — con số đã đóng vào config.yaml (DEC-052).

    ⚠️ Vòng tròn KHÔNG khít tuyệt đối: `config.yaml` giữ bản **làm tròn 3 chữ
    số** của sigmoid, nên suy ngược ra +2,4288 chứ không phải +2,430 chẵn.
    Lệch 0,0012 logit, và lệch về phía **thấp hơn** — tức ngưỡng đang chạy dễ
    dãi hơn ngưỡng đã hiệu chỉnh một chút xíu. Trên dải an toàn rộng 0,55 logit
    (DEC-051) thì không đáng kể, nhưng đừng ngạc nhiên khi hai con số trong báo
    cáo không khớp chữ số cuối.
    """
    assert to_logit(0.919) == pytest.approx(2.4288, abs=0.0005)


# --------------------------------------------------------------------- #
# ba mốc leakage
# --------------------------------------------------------------------- #
def _ab_batch():
    return [
        # bị chặn ngay lượt 1, rewrite không cứu -> ABSTAIN đúng
        _rec("A-01", "A", "ABSTAIN", [+2.15, +1.90]),
        # ⛔ bị chặn lượt 1 NHƯNG rewrite kéo lên trên ngưỡng -> leak lượt 2
        _rec("A-02", "A", "ANSWER", [+1.20, +3.10]),
        # lọt ngay lượt 1 (thứ LOOCV đo được)
        _rec("B-01", "B", "ANSWER", [+2.80]),
        # bị chặn cả hai lượt
        _rec("B-02", "B", "ABSTAIN", [+0.50, +0.20]),
    ]


def test_three_milestones_are_counted_separately():
    """Gộp ba mốc là mất đúng con số mà phiên này sinh ra để tìm."""
    res = analyze_group(_ab_batch(), ("A", "B"))
    assert res["n"] == 4
    assert res["n_turn2"] == 3
    assert res["answered_turn1"] == ["B-01"]     # LOOCV đã thấy
    assert res["answered_turn2"] == ["A-02"]     # LOOCV KHÔNG thấy
    assert sorted(res["answered_final"]) == ["A-02", "B-01"]
    assert sorted(res["refused_final"]) == ["A-01", "B-02"]


def test_leak_after_rewrite_is_not_hidden_by_a_clean_first_turn():
    """Kịch bản nguy hiểm nhất: lượt 1 sạch tuyệt đối, lượt 2 mới hỏng.

    Nếu chỉ nhìn `answered_turn1` thì hệ thống báo leakage 0/2 — đúng y như
    DEC-051 đã kết luận — trong khi một nửa số câu thật ra đã được trả lời.
    """
    rows = [
        _rec("A-10", "A", "ANSWER", [+0.10, +3.00]),
        _rec("A-11", "A", "ABSTAIN", [+0.10, +0.20]),
    ]
    res = analyze_group(rows, ("A",))
    assert res["answered_turn1"] == []          # lượt 1 sạch
    assert res["answered_turn2"] == ["A-10"]    # nhưng hệ thống ĐÃ trả lời
    assert res["answered_final"] == ["A-10"]


def test_same_counting_reads_as_coverage_for_group_e():
    """Cùng phép đếm, nhóm E: 'đã trả lời' là coverage chứ không phải leakage."""
    rows = [
        _rec("E-01", "E", "ANSWER", [+3.50], expected="ANSWER"),
        _rec("E-02", "E", "ANSWER", [+1.00, +2.90], expected="ANSWER"),  # rewrite cứu
        _rec("E-03", "E", "ABSTAIN", [-0.35, -0.40], expected="ANSWER"),
    ]
    res = analyze_group(rows, ("E",))
    assert res["answered_turn2"] == ["E-02"]    # DEC-046 cứu được 1 câu
    assert res["refused_final"] == ["E-03"]     # từ chối nhầm


# --------------------------------------------------------------------- #
# biên còn lại
# --------------------------------------------------------------------- #
def test_margin_says_whether_zero_leak_was_luck_or_room():
    """`0/30` với biên 0,02 và với biên 1,5 in ra cùng một số — cột này tách chúng."""
    m = margin(_ab_batch(), ("A", "B"), TAU)
    assert m["turn1"]["top_id"] == "B-01"
    assert m["turn1"]["top_logit"] == pytest.approx(2.80)
    assert m["turn1"]["margin"] == pytest.approx(TAU - 2.80)   # âm = đã lọt
    assert m["turn2"]["top_id"] == "A-02"
    assert m["turn2"]["margin"] < 0


def test_margin_is_none_when_nobody_reaches_that_turn():
    rows = [_rec("A-20", "A", "ABSTAIN", [+0.1])]
    assert margin(rows, ("A",), TAU)["turn2"] is None


# --------------------------------------------------------------------- #
# rewrite đẩy điểm đi đâu
# --------------------------------------------------------------------- #
def test_delta_and_sign_test_over_two_turn_questions():
    res = analyze_group(_ab_batch(), ("A", "B"))
    assert dict(res["deltas"]) == pytest.approx(
        {"A-01": -0.25, "A-02": +1.90, "B-02": -0.30}, abs=1e-9
    )
    neg, pos, _ = res["sign_test"]
    assert (neg, pos) == (2, 1)


def test_sign_test_drops_exact_ties_from_the_denominator():
    """Quy ước chuẩn của kiểm định dấu — cặp bằng 0 không tính vào mẫu số."""
    neg, pos, p = sign_test([-1.0, +1.0, 0.0, 0.0])
    assert (neg, pos) == (1, 1)
    assert p == pytest.approx(1.0)


# --------------------------------------------------------------------- #
# nhóm D — đúng kết cục vì đúng lý do
# --------------------------------------------------------------------- #
def test_policy_check_flags_group_d_that_abstained_for_the_wrong_reason():
    """ABSTAIN do retrieval trên câu D = gate trượt, chỉ là tình cờ không tìm thấy."""
    rows = [
        {"id": "D-01", "group": "D", "system": "corrective", "action": "ABSTAIN",
         "abstain_mechanism": "policy", "policy_rule": "D-1", "turns": []},
        {"id": "D-02", "group": "D", "system": "corrective", "action": "ABSTAIN",
         "abstain_mechanism": "retrieval", "policy_rule": None,
         "turns": [{"i": 0, "logit": -1.0, "state": "INCORRECT"}]},
        {"id": "D-03", "group": "D", "system": "corrective", "action": "ANSWER",
         "abstain_mechanism": None, "policy_rule": None,
         "turns": [{"i": 0, "logit": +3.0, "state": "CORRECT"}]},
    ]
    res = policy_check(rows)
    assert res["n"] == 3
    assert res["by_mechanism"]["policy"] == ["D-01"]
    assert res["by_mechanism"]["retrieval"] == ["D-02"]   # đúng kết cục, sai lý do
    assert res["answered"] == ["D-03"]                    # gate trượt hẳn
    assert res["rules"] == ["D-1"]


# --------------------------------------------------------------------- #
# analyze() — ráp lại
# --------------------------------------------------------------------- #
def test_analyze_ignores_baseline_records():
    """Baseline không có truy hồi; trộn nó vào là pha loãng mọi mẫu số."""
    rows = _ab_batch() + [
        {"id": "A-01", "group": "A", "system": "baseline_llm_only",
         "action": None, "answer": "..."},
    ]
    res = analyze(rows, incorrect_threshold=TAU_SIGMOID)
    assert res["n_records"] == 4
    assert res["threshold_logit"] == pytest.approx(TAU)


# --------------------------------------------------------------------- #
# thống kê mẫu nhỏ
# --------------------------------------------------------------------- #
def test_wilson_never_claims_zero_risk_from_zero_events():
    """Wald sẽ ra [0, 0] và bảo 'leakage bằng 0'. Đó là lý do dùng Wilson."""
    lo, hi = wilson(0, 30)
    assert lo == 0.0
    assert hi > 0.10          # còn khoảng không nhỏ, không phải 0
    assert rule_of_three(30) == pytest.approx(0.10)

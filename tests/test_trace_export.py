"""Test xuất `trace` → bản ghi JSONL (`src/eval/trace_export.py`).

Không chạm mạng, không nạp model: pipeline dựng bằng Fake, đúng ràng buộc #2.
Trọng tâm là **bốn cái bẫy** ghi ở docstring module được kiểm bằng máy chứ
không bằng trí nhớ:

  1. điểm của CẢ HAI lượt truy hồi có mặt trong bản ghi;
  2. `retrieved` được đọc, KHÔNG phải `chunks` (DEC-049);
  3. hai cơ chế abstain tách được (policy vs retrieval);
  4. lượt truy hồi ĐẦU không biến mất khi câu đi qua rewrite.
"""

import json
import math

import pytest

# Dùng lại đúng khối config giả của test pipeline thay vì chép bản thứ ba:
# `AppConfig` có 10 khối bắt buộc, và một bản sao lệch một tham số sẽ làm test
# ở đây xanh trên một cấu hình mà pipeline thật không bao giờ chạy.
from src.eval.trace_export import (
    ANSWERING_ACTIONS,
    RecordingRetriever,
    abstain_mechanism,
    build_baseline_record,
    build_record,
    chunk_json,
    gold_rank,
    grade_turns,
    logit,
    policy_rule,
)
from src.generation.generator import FakeGenerator
from src.pipeline.grader import Grader
from src.pipeline.pipeline import RAGPipeline
from src.pipeline.rewriter import FakeRewriter
from src.retrieval.reranker import sigmoid
from src.retrieval.retriever import FakeRetriever
from src.schemas import RetrievedChunk, TraceStep
from tests.test_pipeline_route import _cfg

# Ngưỡng dùng cho mọi test dưới đây, khớp `_cfg`: correct 0.6 / incorrect 0.3.
Q_E = {
    "id": "E-99",
    "group": "E",
    "user_input": "biến chứng tiểu đường",
    "expected_action": "ANSWER",
    "reference_context_ids": ["fake-0-1"],
}
Q_A = {
    "id": "A-99",
    "group": "A",
    "user_input": "thuốc Aspirin STELLA có chỉ định gì",
    "expected_action": "ABSTAIN",
    "reference_context_ids": [],
}
Q_D = {
    "id": "D-99",
    "group": "D",
    "user_input": "Tôi 60kg thì uống metformin bao nhiêu viên một ngày?",
    "expected_action": "ABSTAIN",
    "reference_context_ids": [],
}


def _run(q: dict, scores: list[float]):
    """Chạy pipeline Fake, trả về ``(record, recorder)``."""
    cfg = _cfg()
    recorder = RecordingRetriever(FakeRetriever(scores=scores))
    pipe = RAGPipeline(
        cfg=cfg,
        retriever=recorder,
        generator=FakeGenerator(),
        grader=Grader(cfg.grader),
        rewriter=FakeRewriter(),
    )
    result = pipe.answer(q["user_input"])
    return build_record(q, result, turns_chunks=recorder.turns), recorder


# --------------------------------------------------------------------- #
# logit — nghịch đảo sigmoid
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("x", [-8.0, -2.43, 0.0, 0.5, 2.43, 5.67, 8.0])
def test_logit_round_trips_sigmoid(x):
    """Vòng tròn logit → sigmoid → logit phải khít trong dải đo được.

    Dải |logit| ≤ 8 là dải thật của đề tài (DEC-039/051/055). Sai số ở đây
    quyết định con số trong bảng báo cáo có tin được hay không.
    """
    assert logit(sigmoid(x)) == pytest.approx(x, abs=1e-9)


def test_logit_returns_none_at_saturation():
    """Bão hoà trả None chứ KHÔNG trả ±inf — inf sẽ thành NaN sau phép trừ."""
    assert logit(0.0) is None
    assert logit(1.0) is None
    assert logit(None) is None
    # Ngữ cảnh rỗng: `Grader.score_of([])` trả 0.0. "Không truy hồi được gì"
    # không phải là "logit bằng âm vô cùng".
    assert logit(Grader(_cfg().grader).score_of([])) is None


# --------------------------------------------------------------------- #
# grade_turns / abstain_mechanism / policy_rule — đọc trace thô
# --------------------------------------------------------------------- #
def test_grade_turns_reads_by_position_not_by_note():
    """Đổi `note` sang tiếng gì cũng không được làm hỏng việc tách lượt."""
    trace = [
        TraceStep("POLICY", None, None, ""),
        TraceStep("RETRIEVE", None, 0.2, "ghi chú đổi rồi"),
        TraceStep("GRADE", "INCORRECT", 0.2, "ghi chú đổi rồi"),
        TraceStep("REWRITE", None, None, "câu viết lại"),
        TraceStep("RETRIEVE", None, 0.95, "khác hẳn"),
        TraceStep("GRADE", "CORRECT", 0.95, "khác hẳn"),
    ]
    turns = grade_turns(trace)
    assert [t["i"] for t in turns] == [0, 1]
    assert [t["state"] for t in turns] == ["INCORRECT", "CORRECT"]
    assert turns[0]["logit"] == pytest.approx(math.log(0.2 / 0.8))


def test_abstain_mechanism_separates_policy_from_retrieval():
    policy = [
        TraceStep("POLICY", None, None, "D-1"),
        TraceStep("ABSTAIN", None, None, "policy:D-1"),
    ]
    retrieval = [
        TraceStep("POLICY", None, None, ""),
        TraceStep("GRADE", "INCORRECT", 0.1, ""),
        TraceStep("ABSTAIN", "INCORRECT", None, ""),
    ]
    answered = [
        TraceStep("POLICY", None, None, ""),
        TraceStep("GRADE", "CORRECT", 0.99, ""),
        TraceStep("GENERATE", None, None, "normal"),
    ]
    assert abstain_mechanism(policy) == "policy"
    assert abstain_mechanism(retrieval) == "retrieval"
    assert abstain_mechanism(answered) is None
    assert policy_rule(policy) == "D-1"
    # Bước POLICY được ghi KỂ CẢ khi không khớp (note rỗng) — không được đọc
    # thành "có rule tên là chuỗi rỗng".
    assert policy_rule(retrieval) is None


# --------------------------------------------------------------------- #
# gold_rank
# --------------------------------------------------------------------- #
def _c(doc_id: str, score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(doc_id=doc_id, text="x", specialty=None, score=score)


def test_gold_rank_counts_documents_not_chunks():
    """Một bài chiếm 3 chunk đầu vẫn chỉ là hạng 1 — quy ước của DEC-039/051."""
    chunks = [_c("a"), _c("a"), _c("a"), _c("vang"), _c("b")]
    assert gold_rank(chunks, ["vang"]) == 2


def test_gold_rank_none_when_gold_not_in_pool():
    """None ≠ hạng lớn: đó là ranh giới giữa 'truy hồi hỏng' và 'chấm điểm hỏng'."""
    assert gold_rank([_c("a"), _c("b")], ["vang"]) is None
    assert gold_rank([_c("a")], []) is None


# --------------------------------------------------------------------- #
# build_record — bốn cái bẫy
# --------------------------------------------------------------------- #
def test_both_retrieval_turns_are_recorded():
    """BẪY 1: mất lượt 2 = không chia lại fold LOOCV được, phải chạy lại cả lô."""
    rec, _ = _run(Q_A, scores=[0.1, 0.2])   # INCORRECT -> rewrite -> vẫn INCORRECT
    assert rec["n_turns"] == 2
    assert [t["i"] for t in rec["turns"]] == [0, 1]
    assert rec["turns"][0]["score"] == pytest.approx(0.1)
    assert rec["turns"][1]["score"] == pytest.approx(0.2)
    assert rec["turns"][0]["logit"] == pytest.approx(math.log(0.1 / 0.9))


def test_abstain_record_keeps_retrieved_even_though_chunks_empty():
    """BẪY 2 (DEC-049): đọc nhầm trường thì 30/59 câu ra 0 chunk mà bảng vẫn chạy."""
    rec, _ = _run(Q_A, scores=[0.1])
    assert rec["action"] == "ABSTAIN"
    assert rec["n_chunks_shown"] == 0        # UI không được hiện nguồn
    assert len(rec["retrieved"]) > 0         # eval Tuần 6 vẫn chấm được
    assert all("text" in c for c in rec["retrieved"])


def test_policy_abstain_is_distinguishable_and_has_no_turns():
    """BẪY 3: nhóm D bị chặn TRƯỚC retrieval nên không nằm trên đường hiệu chỉnh."""
    rec, _ = _run(Q_D, scores=[0.99])
    assert rec["action"] == "ABSTAIN"
    assert rec["abstain_mechanism"] == "policy"
    assert rec["policy_rule"] and rec["policy_rule"].startswith("D-")
    assert rec["n_turns"] == 0
    assert rec["retrieved"] == []


def test_first_turn_survives_the_rewrite():
    """BẪY 4: `PipelineResult.retrieved` chỉ mang lượt cuối; recorder giữ lượt đầu."""
    rec, recorder = _run(Q_E, scores=[0.1, 0.99])
    assert len(recorder.turns) == 2
    assert recorder.turns[0]["query"] != recorder.turns[1]["query"]  # đã rewrite
    assert rec["turns"][0]["query"] == Q_E["user_input"]
    # Hạng bài vàng của TỪNG lượt — con số tách "truy hồi hỏng" khỏi "chấm hỏng".
    assert rec["turns"][0]["gold_rank"] == 2   # fake-0-1 đứng thứ 2 theo doc
    assert "doc_ids" in rec["turns"][1]


def test_recorder_reset_stops_bleed_between_questions():
    inner = FakeRetriever(scores=[0.9])
    rec = RecordingRetriever(inner)
    rec.retrieve("câu 1")
    rec.reset()
    rec.retrieve("câu 2")
    assert [t["query"] for t in rec.turns] == ["câu 2"]


# --------------------------------------------------------------------- #
# leaked / refused — hai lỗi ngược chiều
# --------------------------------------------------------------------- #
def test_leaked_flag_counts_answer_with_caution():
    """Trả lời KÈM CẢNH BÁO một câu nhóm A vẫn là leakage, không phải nửa điểm."""
    rec, _ = _run(Q_A, scores=[0.45])        # rơi vào [0.3, 0.6) -> AMBIGUOUS
    assert rec["action"] == "ANSWER_WITH_CAUTION"
    assert rec["action"] in ANSWERING_ACTIONS
    assert rec["leaked"] is True
    assert rec["refused"] is False


def test_refused_flag_marks_false_refusal_on_group_e():
    rec, _ = _run(Q_E, scores=[0.1])
    assert rec["action"] == "ABSTAIN"
    assert rec["refused"] is True
    assert rec["leaked"] is False


def test_answered_record_has_neither_flag():
    rec, _ = _run(Q_E, scores=[0.99])
    assert rec["action"] == "ANSWER"
    assert (rec["leaked"], rec["refused"]) == (False, False)


# --------------------------------------------------------------------- #
# hình dạng file
# --------------------------------------------------------------------- #
def test_record_is_json_serializable():
    """Ghi JSONL mà vấp `TerminalAction` hay `RetrievedChunk` là hỏng cả lô."""
    rec, _ = _run(Q_E, scores=[0.99])
    assert json.loads(json.dumps(rec, ensure_ascii=False))["id"] == "E-99"


def test_no_context_text_drops_only_text():
    cfg = _cfg()
    recorder = RecordingRetriever(FakeRetriever(scores=[0.99]))
    pipe = RAGPipeline(
        cfg=cfg, retriever=recorder, generator=FakeGenerator(),
        grader=Grader(cfg.grader), rewriter=FakeRewriter(),
    )
    result = pipe.answer(Q_E["user_input"])
    rec = build_record(Q_E, result, turns_chunks=recorder.turns, with_text=False)
    assert rec["retrieved"] and "text" not in rec["retrieved"][0]
    assert "doc_id" in rec["retrieved"][0]


def test_chunk_json_carries_the_dec035_fields():
    """title/source/chunk_idx là thứ citation Tuần 4 cần — đừng đánh rơi."""
    c = RetrievedChunk(
        doc_id="d1", text="t", specialty="tim_mach", score=0.9,
        chunk_idx=2, n_chunks=5, title="Tiêu đề", source="https://x",
    )
    out = chunk_json(c)
    assert (out["title"], out["source"], out["chunk_idx"], out["n_chunks"]) == (
        "Tiêu đề", "https://x", 2, 5
    )


def test_baseline_record_omits_retrieval_concepts():
    """Để TRỐNG chứ không điền 0: baseline không có khái niệm truy hồi/abstain."""
    rec = build_baseline_record(Q_E, "câu trả lời không nguồn")
    assert rec["system"] == "baseline_llm_only"
    assert rec["id"] == Q_E["id"]           # join được với bản corrective
    assert "turns" not in rec
    assert "retrieved" not in rec
    assert "abstain_mechanism" not in rec

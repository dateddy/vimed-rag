"""Test cho src.pipeline.grader: 3 trạng thái theo ngưỡng config."""

from src.config import GraderConfig
from src.schemas import GraderState, RetrievedChunk


def _grader():
    from src.pipeline.grader import Grader

    return Grader(GraderConfig(correct_threshold=0.6, incorrect_threshold=0.3))


def _chunk(score: float) -> RetrievedChunk:
    return RetrievedChunk(doc_id="d", text="t", specialty=None, score=score)


def test_correct():
    assert _grader().grade([_chunk(0.8)]) == GraderState.CORRECT


def test_ambiguous():
    assert _grader().grade([_chunk(0.45)]) == GraderState.AMBIGUOUS


def test_incorrect():
    assert _grader().grade([_chunk(0.1)]) == GraderState.INCORRECT


def test_empty_context_is_incorrect():
    assert _grader().grade([]) == GraderState.INCORRECT


def test_uses_max_score():
    chunks = [_chunk(0.1), _chunk(0.8), _chunk(0.4)]
    assert _grader().grade(chunks) == GraderState.CORRECT

"""Test corrective loop của RAGPipeline với Fake components — 4 kịch bản.

Grader thật (thuần) được dùng; trạng thái grade điều khiển gián tiếp qua
rerank score do FakeRetriever trả về (scripted theo từng lần gọi).
"""

from src.config import (
    AppConfig,
    ChunkingConfig,
    CorrectiveConfig,
    GenerationConfig,
    GraderConfig,
    ModelsConfig,
    QdrantConfig,
    RetrievalConfig,
)
from src.generation.generator import FakeGenerator
from src.pipeline.grader import Grader
from src.pipeline.pipeline import RAGPipeline
from src.pipeline.rewriter import FakeRewriter
from src.retrieval.retriever import FakeRetriever
from src.schemas import TerminalAction


def _cfg(max_iter: int = 1) -> AppConfig:
    return AppConfig(
        models=ModelsConfig("e", "r", "l"),
        retrieval=RetrievalConfig(True, 20, 5),
        chunking=ChunkingConfig(512, 50),
        grader=GraderConfig(correct_threshold=0.6, incorrect_threshold=0.3),
        corrective=CorrectiveConfig(max_iter=max_iter),
        generation=GenerationConfig(0.2),
        qdrant=QdrantConfig("http://x", "c"),
        specialties={},
    )


def _pipeline(scores: list[float], max_iter: int = 1) -> RAGPipeline:
    cfg = _cfg(max_iter)
    return RAGPipeline(
        cfg=cfg,
        retriever=FakeRetriever(scores=scores),
        generator=FakeGenerator(),
        grader=Grader(cfg.grader),
        rewriter=FakeRewriter(),
    )


def _steps(result) -> list[str]:
    return [s.step for s in result.trace]


def test_correct_answers_without_rewrite():
    """Kịch bản 1: luôn CORRECT -> ANSWER, không có REWRITE."""
    result = _pipeline(scores=[0.9]).answer("huyết áp cao là gì")
    assert result.action == TerminalAction.ANSWER
    assert "REWRITE" not in _steps(result)
    assert result.rewritten_query is None


def test_ambiguous_answers_with_caution():
    """Kịch bản 2: luôn AMBIGUOUS -> ANSWER_WITH_CAUTION."""
    result = _pipeline(scores=[0.45]).answer("triệu chứng tiểu đường")
    assert result.action == TerminalAction.ANSWER_WITH_CAUTION
    assert "REWRITE" not in _steps(result)
    assert "[CẢNH BÁO" in result.answer


def test_incorrect_then_recover_after_rewrite():
    """Kịch bản 3: INCORRECT lần 1, CORRECT sau rewrite -> ANSWER, đúng 1 REWRITE."""
    result = _pipeline(scores=[0.1, 0.9]).answer("insulin dùng khi nào")
    assert result.action == TerminalAction.ANSWER
    assert _steps(result).count("REWRITE") == 1
    assert result.rewritten_query is not None
    assert result.rewritten_query.endswith("(viết lại)")


def test_incorrect_twice_abstains():
    """Kịch bản 4: INCORRECT cả 2 lần -> ABSTAIN, kết thúc bằng ABSTAIN, 1 REWRITE."""
    result = _pipeline(scores=[0.1, 0.1]).answer("câu hỏi ngoài phạm vi")
    assert result.action == TerminalAction.ABSTAIN
    assert _steps(result)[-1] == "ABSTAIN"
    assert _steps(result).count("REWRITE") == 1  # tôn trọng max_iter=1


def test_retriever_receives_rewritten_query():
    """Sau rewrite, retriever lần 2 phải nhận query đã viết lại."""
    retriever = FakeRetriever(scores=[0.1, 0.9])
    cfg = _cfg()
    pipe = RAGPipeline(
        cfg=cfg,
        retriever=retriever,
        generator=FakeGenerator(),
        grader=Grader(cfg.grader),
        rewriter=FakeRewriter(),
    )
    pipe.answer("q gốc")
    assert retriever.queries == ["q gốc", "q gốc (viết lại)"]

"""RAGPipeline — Corrective RAG + calibrated abstention (Python thuần).

Orchestration KHÔNG dùng LangGraph/LangChain. Vòng corrective nằm gọn trong
``_route``, mọi bước ghi vào ``trace`` để Tuần 6 tách metric theo nhánh và
vẽ đường cong risk–coverage. Các thành phần (retriever/generator/grader/
rewriter) được inject qua constructor → fake khi test, real khi chạy.
"""

from __future__ import annotations

from src.config import AppConfig, load_prompt
from src.generation.generator import Generator
from src.pipeline.grader import Grader
from src.pipeline.rewriter import Rewriter
from src.retrieval.retriever import Retriever
from src.schemas import (
    GraderState,
    PipelineResult,
    RetrievedChunk,
    TerminalAction,
    TraceStep,
)


class RAGPipeline:
    """Điều phối corrective loop theo CONTRACT (xem README)."""

    def __init__(
        self,
        cfg: AppConfig,
        retriever: Retriever,
        generator: Generator,
        grader: Grader,
        rewriter: Rewriter,
    ) -> None:
        self._cfg = cfg
        self._retriever = retriever
        self._generator = generator
        self._grader = grader
        self._rewriter = rewriter

    # ------------------------------------------------------------------ #
    # API công khai
    # ------------------------------------------------------------------ #
    def answer(self, query: str) -> PipelineResult:
        """Trả lời một truy vấn qua corrective loop. Xem ``_route``."""
        return self._route(query)

    # ------------------------------------------------------------------ #
    # Lõi định tuyến
    # ------------------------------------------------------------------ #
    def _route(self, query: str) -> PipelineResult:
        trace: list[TraceStep] = []

        ctx = self._retriever.retrieve(query)
        state = self._grade(ctx, trace, note="lần truy hồi đầu", after="RETRIEVE")

        if state == GraderState.CORRECT:
            answer = self._generate(query, ctx, trace, caution=False)
            return self._result(query, TerminalAction.ANSWER, answer, ctx, trace)
        if state == GraderState.AMBIGUOUS:
            answer = self._generate(query, ctx, trace, caution=True)
            return self._result(
                query, TerminalAction.ANSWER_WITH_CAUTION, answer, ctx, trace
            )

        # state == INCORRECT -> thử sửa đúng tối đa max_iter lần.
        rewritten: str | None = None
        for _ in range(self._cfg.corrective.max_iter):
            q2 = self._rewriter.rewrite(query, ctx)
            rewritten = q2
            trace.append(TraceStep(step="REWRITE", state=None, score=None, note=q2))

            ctx = self._retriever.retrieve(q2)
            state = self._grade(ctx, trace, note="sau rewrite", after="RETRIEVE")

            if state == GraderState.CORRECT:
                answer = self._generate(q2, ctx, trace, caution=False)
                return self._result(
                    query, TerminalAction.ANSWER, answer, ctx, trace, rewritten
                )
            if state == GraderState.AMBIGUOUS:
                answer = self._generate(q2, ctx, trace, caution=True)
                return self._result(
                    query,
                    TerminalAction.ANSWER_WITH_CAUTION,
                    answer,
                    ctx,
                    trace,
                    rewritten,
                )

        # Hết lượt sửa mà vẫn INCORRECT -> từ chối (calibrated abstention).
        msg = self._abstain_message()
        trace.append(
            TraceStep(step="ABSTAIN", state=GraderState.INCORRECT.value, score=None)
        )
        return self._result(
            query, TerminalAction.ABSTAIN, msg, ctx, trace, rewritten
        )

    # ------------------------------------------------------------------ #
    # Helper nội bộ
    # ------------------------------------------------------------------ #
    def _grade(
        self,
        ctx: list[RetrievedChunk],
        trace: list[TraceStep],
        note: str,
        after: str,
    ) -> GraderState:
        """Ghi bước RETRIEVE rồi GRADE vào trace, trả về GraderState."""
        score = self._grader.score_of(ctx)
        trace.append(
            TraceStep(step=after, state=None, score=score, note=note)
        )
        state = self._grader.grade(ctx)
        trace.append(
            TraceStep(step="GRADE", state=state.value, score=score, note=note)
        )
        return state

    def _generate(
        self,
        query: str,
        ctx: list[RetrievedChunk],
        trace: list[TraceStep],
        caution: bool,
    ) -> str:
        answer = self._generator.generate(query, ctx, caution=caution)
        note = "caution" if caution else "normal"
        trace.append(
            TraceStep(step="GENERATE", state=None, score=None, note=note)
        )
        return answer

    def _abstain_message(self) -> str:
        """Thông điệp từ chối; đọc từ prompt file, fallback nếu thiếu."""
        try:
            return load_prompt("abstain").strip()
        except FileNotFoundError:
            return (
                "Xin lỗi, tôi chưa đủ thông tin đáng tin cậy để trả lời câu hỏi "
                "này. Vui lòng tham khảo ý kiến bác sĩ."
            )

    @staticmethod
    def _result(
        query: str,
        action: TerminalAction,
        answer: str,
        ctx: list[RetrievedChunk],
        trace: list[TraceStep],
        rewritten: str | None = None,
    ) -> PipelineResult:
        return PipelineResult(
            query=query,
            action=action,
            answer=answer,
            chunks=ctx,
            trace=trace,
            rewritten_query=rewritten,
        )

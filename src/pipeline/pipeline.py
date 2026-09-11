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
from src.pipeline.policy import Policy, get_policy
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
        policy: Policy | None = None,
    ) -> None:
        self._cfg = cfg
        self._retriever = retriever
        self._generator = generator
        self._grader = grader
        self._rewriter = rewriter
        # Policy gate là thuần logic + 1 file yaml local nên KHÔNG cần Fake
        # (ràng buộc #2 chỉ cấm chạm model/dataset thật). Để optional vì test
        # dựng pipeline không cần biết tới nó; truyền vào khi muốn policy riêng.
        self._policy = policy if policy is not None else get_policy()

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

        # --- Lớp 1/8 — POLICY GATE, chạy TRƯỚC retrieval (DEC-024) --------- #
        # Luôn ghi bước POLICY kể cả khi không khớp, để Tuần 6 đếm được "gate
        # đã chạy" thay vì phải suy ra từ sự vắng mặt của bước này.
        hit = self._policy.check(query)
        trace.append(
            TraceStep(
                step="POLICY",
                state=None,
                score=None,
                note=hit.rule_id if hit else "",
            )
        )
        if hit:
            # Hai cơ chế ABSTAIN phải tách được trong trace (corrective-loop.md):
            #   policy    -> có bước POLICY với note khác rỗng
            #   retrieval -> bước ABSTAIN mang state INCORRECT
            trace.append(
                TraceStep(
                    step="ABSTAIN",
                    state=None,
                    score=None,
                    note=f"policy:{hit.rule_id}",
                )
            )
            # chunks=[] CÓ CHỦ ĐÍCH: không retrieve thì không có nguồn, và hiện
            # nguồn ở đây là mời người dùng tự suy ra chính câu vừa bị chặn.
            return self._result(
                query,
                TerminalAction.ABSTAIN,
                self._policy_abstain_message(hit.rule_id),
                [],
                trace,
            )

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

            # --- Lớp chặn lượt 2 (DEC-061) --------------------------------- #
            # Truy hồi + chấm điểm Ở TRÊN vẫn chạy đủ, có chủ đích: `trace` phải
            # giữ nguyên điểm lượt 2 — đó là thứ DEC-056/057 đo được và là thứ
            # bảng Tuần 6 cần. Cái bị tước là **quyền LẬT quyết định**, không
            # phải quyền chạy.
            if not self._cfg.corrective.allow_turn2_promotion:
                # `note` khác rỗng = đã chặn THẬT (lượt 2 đòi trả lời mà bị giữ
                # lại); rỗng = lượt 2 vẫn INCORRECT nên không có gì để chặn.
                # Cùng quy ước với bước POLICY, để Tuần 6 đếm được "guard đã
                # chạy" tách khỏi "guard đã chặn".
                trace.append(
                    TraceStep(
                        step="GUARD",
                        state=state.value,
                        score=None,
                        note="" if state == GraderState.INCORRECT else state.value,
                    )
                )
                # `break` chứ không `continue`: guard bật thì mọi lượt sau cũng
                # không lật được gì, chạy tiếp chỉ tốn thêm lượt gọi LLM.
                break

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
        # chunks=[] nhưng retrieved=ctx (DEC-049): UI không được hiện nguồn cho
        # một câu từ chối, còn Tuần 6 vẫn phải chấm được retrieval của nhóm A/B
        # — mà nhóm A/B thì LUÔN đi qua đúng nhánh này.
        return self._result(
            query, TerminalAction.ABSTAIN, msg, [], trace, rewritten,
            retrieved=ctx,
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

    def _policy_abstain_message(self, rule_id: str) -> str:
        """Thông điệp từ chối do POLICY — KHÁC HẲN từ chối do retrieval.

        Không được dùng lại ``abstain.txt``: file đó nói "chưa tìm được thông
        tin trong cơ sở dữ liệu", mà với nhóm D điều đó **sai sự thật** —
        corpus CÓ bài metformin, hệ thống không trả lời vì không được phép.
        Dùng chung một câu là mô tả sai chính cơ chế mình vừa xây, và Tuần 6
        báo cáo theo đó sẽ sai.

        D-3 có file riêng vì bản ``.md`` quy định trả 115 và KHÔNG kèm gì
        thêm: đây là rule duy nhất mà một câu trả lời *đúng* vẫn có hại, vì
        mọi nội dung thừa đều kéo dài thời gian tới lúc người dùng gọi cấp cứu.
        """
        slug = rule_id.lower().replace("-", "")
        for name in (f"abstain_policy_{slug}", "abstain_policy"):
            try:
                return load_prompt(name).strip()
            except FileNotFoundError:
                continue
        return (
            "Câu hỏi này cần bác sĩ trực tiếp đánh giá. "
            "Vui lòng đi khám hoặc hỏi bác sĩ điều trị của bạn."
        )

    def _abstain_message(self) -> str:
        """Thông điệp từ chối do RETRIEVAL; đọc từ prompt file, fallback nếu thiếu."""
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
        retrieved: list[RetrievedChunk] | None = None,
    ) -> PipelineResult:
        """Dựng kết quả. ``retrieved`` mặc định = ``ctx`` (nhánh trả lời).

        Chỉ nhánh ABSTAIN-do-retrieval mới truyền hai giá trị khác nhau; xem
        docstring ``PipelineResult`` để biết vì sao tách (DEC-049).
        """
        return PipelineResult(
            query=query,
            action=action,
            answer=answer,
            chunks=ctx,
            trace=trace,
            rewritten_query=rewritten,
            retrieved=ctx if retrieved is None else retrieved,
        )

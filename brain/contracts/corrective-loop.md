# Contract — Corrective loop

> Contract. Đổi file này = đổi thiết kế. Phải kèm 1 dòng mới trong `../decisions/DECISIONS.md`.

Nguồn: COMPRESS Session 2, mục 4 + 5. Claude Code implement **chính xác** phần này.

## Pseudo-code (mục 4)

```
GraderState    = CORRECT | AMBIGUOUS | INCORRECT
TerminalAction = ANSWER | ANSWER_WITH_CAUTION | ABSTAIN

answer(query):
    ctx   = retrieve(query)         # trace RETRIEVE
    state = grade(ctx)              # rerank score, KHÔNG gọi LLM; trace GRADE
    CORRECT   -> ANSWER
    AMBIGUOUS -> ANSWER_WITH_CAUTION
    INCORRECT -> for i in range(max_iter=1):
                   q2=rewrite(q,ctx); ctx=retrieve(q2); state=grade(ctx)
                   CORRECT/AMBIGUOUS -> generate
                 else -> ABSTAIN
```

- `grader.grade()` **thuần** (score + 2 ngưỡng từ config, không model).
- `max_iter=1` = đúng 1 lần rewrite, không loop vô hạn.
- `trace: list[TraceStep]` đủ để Tuần 6 tách metric theo nhánh + vẽ risk–coverage.

## Chống hallucination = defense-in-depth 7 lớp (mục 4)

grounding → retrieval → grounded generation → ngưỡng calibrated → grader → rewrite → ABSTAIN.

RAGAS faithfulness chỉ **ĐO**, không phải prevention.

## Kiến trúc kỹ thuật đã chốt (mục 5)

- **Orchestration:** Python thuần, `RAGPipeline._route()`, state = dataclass, `trace` list.
  KHÔNG LangGraph/LangChain cho control flow.
- **Dependency injection:** pipeline nhận `retriever/generator/grader/rewriter` qua constructor
  → test bằng Fake, chạy bằng Real.
- **Config-driven:** ngưỡng/model/top-k/chunk/max_iter đọc từ `config/`. Không magic number.
  2 khoa khai báo trong `config/specialties.yaml` (single source of truth).
- **Stub discipline:**
  - thuần logic → implement đủ + test;
  - phụ thuộc data/model/API → interface + Fake + real-skeleton
    `raise NotImplementedError("GATED: Tuần N")`.

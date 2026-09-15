# Contract — Corrective loop

> Contract. Đổi file này = đổi thiết kế. Phải kèm 1 dòng mới trong `../decisions/DECISIONS.md`.

Nguồn: COMPRESS Session 2, mục 4 + 5. Claude Code implement **chính xác** phần này.

## Pseudo-code (mục 4)

```
GraderState    = CORRECT | AMBIGUOUS | INCORRECT
TerminalAction = ANSWER | ANSWER_WITH_CAUTION | ABSTAIN

answer(query):
    hit = check_policy(query)       # DEC-024; thuần rule, KHÔNG LLM; trace POLICY
    if hit -> ABSTAIN(rule=hit.id)  # KHÔNG retrieve, KHÔNG generate
    ctx   = retrieve(query)         # trace RETRIEVE
    state = grade(ctx)              # rerank score, KHÔNG gọi LLM; trace GRADE
    CORRECT   -> ANSWER
    AMBIGUOUS -> ANSWER_WITH_CAUTION
    INCORRECT -> for i in range(max_iter=1):
                   q2=rewrite(q,ctx); ctx=retrieve(q2); state=grade(ctx)
                   CORRECT/AMBIGUOUS -> generate
                 else -> ABSTAIN
```

- `check_policy()` **thuần rule** (regex/keyword từ `config/abstention_policy.md`, không LLM).
  Chạy **trước** retrieval: rẻ nhất, và rule cấp cứu phải trả lời ngay không kèm nội dung tra cứu.
- `grader.grade()` **thuần** (score + 2 ngưỡng từ config, không model).
- `max_iter=1` = đúng 1 lần rewrite, không loop vô hạn.
- `trace: list[TraceStep]` đủ để Tuần 6 tách metric theo nhánh + vẽ risk–coverage.

## Chống hallucination = defense-in-depth 8 lớp (mục 4 + DEC-024)

**policy gate** → grounding → retrieval → grounded generation → ngưỡng calibrated →
grader → rewrite → ABSTAIN.

RAGAS faithfulness chỉ **ĐO**, không phải prevention.

### HAI cơ chế ABSTAIN — `trace` phải phân biệt được

| Cơ chế | Kích hoạt bởi | Ý nghĩa |
|---|---|---|
| ABSTAIN-do-**policy** | `check_policy()` khớp một rule | "Câu này hệ thống KHÔNG ĐƯỢC trả lời", kể cả khi corpus có thừa thông tin |
| ABSTAIN-do-**retrieval** | vẫn INCORRECT sau `max_iter=1` | "Hệ thống KHÔNG ĐỦ CĂN CỨ để trả lời" |

Gộp hai cái này lại thì Tuần 6 **không tách được** risk–coverage: cơ chế 1 là hằng số theo
thiết kế, chỉ cơ chế 2 mới nằm trên đường cong hiệu chỉnh. `TraceStep.step = "POLICY"` và
`note` mang `rule_id` là chỗ giữ khác biệt đó.

### Cơ chế thứ BA — từ chối ở tầng NỘI DUNG, không có trong `trace` (DEC-073)

`action = ANSWER` nhưng generator tự viết *"ngữ cảnh không chứa thông tin"* (`E-21`).
Grader cho qua, generator từ chối. **Không** phải lỗi: prompt bảo nó làm thế, nên đây là
lớp phòng thủ cuối cùng đang chạy. Nó **không** xuất hiện trong `trace` — chỉ đọc được từ
câu chữ. Dụng cụ: `answer_content.is_refusal_text()`.

### Bất biến hiển thị — UI đọc `chunks`, KHÔNG BAO GIỜ đọc `retrieved` (DEC-049 · DEC-073)

`PipelineResult` có hai trường chunk, khác nhau có chủ đích: `chunks` = nguồn câu trả lời
dựa vào (rỗng ở mọi nhánh ABSTAIN); `retrieved` = nguyên văn retriever trả về, **giữ lại
kể cả khi từ chối** vì eval nhóm A/B cần. Đo: **32/40 câu ABSTAIN có `retrieved` không
rỗng** — hiện nó ra là mời người đọc hiểu ngược câu từ chối.

Quyết định hiển thị sống ở `app/display.py` (thuần, khoá bằng test cả hai chiều), **không**
trong callback Streamlit. Mọi chỗ in nội dung chunk phải qua `doc_nguon()` = `strip_byline`:
corpus trong Qdrant **vẫn còn byline** (DEC-020) và đường đọc không có tầng nào cắt hộ.

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

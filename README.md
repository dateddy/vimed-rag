# ViMed-RAG

Hệ thống hỏi–đáp y tế tiếng Việt dùng **Corrective RAG + calibrated abstention**.
Hai chuyên khoa: **tim mạch** & **tiểu đường** (khai báo trong `config/specialties.yaml`).

> **Trạng thái:** Scaffold Tuần 1 — chạy end-to-end bằng **Fake components**
> (không cần GPU / API key / Qdrant). Các phần phụ thuộc model/data bị **GATED**
> cho tới khi Gate 0 (data sufficiency) trả **GO**.

---

## ⚠️ Gate 0 — bắt buộc đọc

**KHÔNG chạy `scripts/run_ingestion.py` với dữ liệu thật cho tới khi
`scripts/gate0_data_check.py` trả về `GO`.** Mọi thành phần gọi model/dataset
thật đều được đánh dấu `# GATED` và ném `NotImplementedError("GATED: Tuần N")`
— chúng không chạy khi import hay khi test.

```bash
python scripts/gate0_data_check.py   # phải in GO trước khi ingest
```

---

## Corrective loop (CONTRACT)

```
                      ┌─────────────┐
        query ───────▶│  RETRIEVE   │◀────────────┐
                      └──────┬──────┘             │
                             ▼                    │ q2 (đã rewrite)
                      ┌─────────────┐             │
                      │   GRADE     │ (rerank score, KHÔNG gọi LLM)
                      └──────┬──────┘             │
             ┌──────────────┼──────────────┐     │
      CORRECT│       AMBIGUOUS│      INCORRECT│    │
             ▼               ▼               ▼     │
         ┌────────┐   ┌────────────┐   ┌──────────┴─────┐
         │ ANSWER │   │ ANSWER_WITH│   │ REWRITE (+1 LLM)│  lặp tối đa
         │        │   │  _CAUTION  │   │  max_iter lần   │  max_iter=1
         └────────┘   └────────────┘   └──────┬─────────┘
                                              │ vẫn INCORRECT
                                              ▼
                                        ┌───────────┐
                                        │  ABSTAIN  │ (khuyên gặp bác sĩ)
                                        └───────────┘
```

- Orchestration = **Python thuần** trong `RAGPipeline._route()`
  ([src/pipeline/pipeline.py](src/pipeline/pipeline.py)). **KHÔNG** LangGraph/LangChain.
- Mỗi bước append một `TraceStep(step, state, score, note)` vào `trace` để
  Tuần 6 tách metric theo nhánh + vẽ đường cong risk–coverage.
- `grader.grade()` **thuần**: so rerank score với 2 ngưỡng trong config.
- `max_iter=1` → **đúng 1 lần** rewrite, không loop vô hạn.
- `RAGPipeline` nhận `retriever/generator/grader/rewriter` qua constructor
  (**dependency injection**) → fake khi test, real khi chạy.

---

## Đã implement vs GATED

| Thành phần | File | Trạng thái |
|---|---|---|
| Schemas (dataclass/enum) | `src/schemas.py` | ✅ ĐẦY ĐỦ |
| Config loader (YAML + .env → typed) | `src/config.py` | ✅ ĐẦY ĐỦ |
| Cleaner (NFC/HTML/min-len/dedup) | `src/data/cleaner.py` | ✅ ĐẦY ĐỦ |
| Chunker (size/overlap theo config) | `src/data/chunker.py` | ✅ ĐẦY ĐỦ |
| Grader (score → GraderState) | `src/pipeline/grader.py` | ✅ ĐẦY ĐỦ |
| Pipeline (corrective `_route`) | `src/pipeline/pipeline.py` | ✅ ĐẦY ĐỦ |
| Fake retriever/generator/rewriter/embedder/indexer | `src/**` | ✅ dùng để test/demo |
| Loader HF dataset | `src/data/loader.py` | 🔒 GATED (Tuần 2) |
| Embedder bge-m3 | `src/retrieval/embedder.py` | 🔒 GATED (Tuần 2) |
| Indexer Qdrant | `src/retrieval/indexer.py` | 🔒 GATED (Tuần 3) |
| Hybrid retriever + rerank | `src/retrieval/retriever.py` | 🔒 GATED (Tuần 3) |
| Generator Gemini | `src/generation/generator.py` | 🔒 GATED (Tuần 4) |
| Rewriter LLM | `src/pipeline/rewriter.py` | 🔒 GATED (Tuần 4) |
| RAGAS + risk–coverage | `src/eval/*` | 🔒 GATED (Tuần 6) |
| Ingestion end-to-end | `scripts/run_ingestion.py` | 🔒 GATED (sau Gate 0) |

---

## Chạy nhanh

```bash
# 1) (Tùy chọn) Qdrant local — chỉ cần khi làm phần retrieval thật
docker compose up -d

# 2) Cài dependency (scaffold chỉ cần PyYAML/pytest/streamlit)
pip install -r requirements.txt

# 3) Test — phải xanh toàn bộ
pytest

# 4) Demo UI (chạy bằng Fake, KHÔNG cần API key/Qdrant/GPU)
streamlit run app/streamlit_app.py
```

`.env`: sao chép `.env.example` → `.env` và điền `GEMINI_API_KEY`, `QDRANT_URL`,
`QDRANT_API_KEY` (chỉ cần khi mở khóa các phần GATED).

---

## Config-driven

Mọi ngưỡng / tên model / top-k / chunk size / max_iter đọc từ `config/config.yaml`.
Ví dụ đổi chunk size 512 ↔ 256 (ablation Tuần 2) **chỉ sửa config**, không đụng code:

```yaml
chunking:
  size: 256   # đổi tại đây
```

> 2 ngưỡng grader (`correct_threshold`, `incorrect_threshold`) hiện là **tạm**;
> giá trị thật được chọn từ đường cong **risk–coverage** ở Tuần 6.

---

## Cấu trúc

```
config/        config.yaml, specialties.yaml, prompts/
src/           schemas, config, data/, retrieval/, generation/, pipeline/, eval/
scripts/       gate0_data_check.py, run_ingestion.py (GATED)
app/           streamlit_app.py
tests/         cleaner / grader / chunker / pipeline_route
```

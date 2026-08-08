# ViMed-RAG — Entry point

> File duy nhất load mỗi session. Chi tiết nằm trong `brain/`.
> **Đừng inline nội dung brain vào file này.**

## Dự án
- **ViMed-RAG**: Safety-aware Corrective RAG with Calibrated Abstention for Trustworthy Vietnamese Medical QA.
- Hệ hỏi-đáp y tế tiếng Việt: Corrective RAG + trích dẫn nguồn + **từ chối có hiệu chỉnh (calibrated abstention)** để kiểm soát hallucination.
- Môn **IT Project** · **1 người (Đạt)** · Tuần 0 + 8 tuần.
- Phạm vi **2 khoa**: tim mạch + tiểu đường.
- **Solo từ 2026-08-08** (DEC-013): Đạt gánh cả 2 luồng — infra/retrieval/pipeline **và**
  eval/generation/test set. Không còn vai "Member A/B"; state gộp về `brain/state/STATUS.md`.

## Tech stack (CHỐT — không đổi)
| Vai trò | Chọn |
|---|---|
| Embedding | `BAAI/bge-m3` (dense+sparse) |
| Vector store | Qdrant |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| Generator | `gemini-2.5-flash` |
| Eval | RAGAS |
| UI / deploy | Streamlit / HF Spaces |

## 5 ràng buộc cứng (chi tiết: `brain/contracts/constraints.md`)
1. KHÔNG LangGraph / LangChain cho orchestration (Python thuần + `trace` list).
2. KHÔNG gọi model/dataset thật khi import hoặc test (mọi thứ nặng nằm sau Fake/GATED).
3. KHÔNG chạy ingestion data thật trước khi **Gate 0 = GO**.
4. Grader **thuần** (không LLM), `max_iter=1` cứng.
5. Repo đã có file → **đọc trước, đừng ghi đè**.

## Routing — đọc file nào khi nào
| Khi | Đọc |
|---|---|
| Bắt đầu, cần bản đồ brain | `brain/00-INDEX.md` |
| Implement / review loop, hallucination | `brain/contracts/corrective-loop.md` |
| Kiểm ràng buộc + trục đóng góp / claim | `brain/contracts/constraints.md` |
| Đủ điều kiện build chưa? | `brain/contracts/gates.md` |
| Lý do một quyết định | `brain/decisions/DECISIONS.md` |
| Trạng thái hiện tại + backlog | `brain/state/STATUS.md` |

> Contract đổi = đổi thiết kế → phải kèm 1 dòng mới trong `brain/decisions/DECISIONS.md`.

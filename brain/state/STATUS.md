# STATUS — ViMed-RAG (Đạt, solo)

> Owner: Đạt. Dự án **1 người** từ 2026-08-08 (DEC-013) — file này là state DUY NHẤT.
> Ghi đè mỗi session; **không** tạo `STATUS-v2`, **không** tách lại theo người.

**Cập nhật lần cuối:** 2026-08-08 (Tuần 1 — gộp việc Member B, Gate 0 đã GO)

## Đang làm
- Tuần 1: infra / data.
- Scaffold xong và đã commit (20 test xanh, Streamlit chạy bằng Fake).
- **Gate 0 = GO** (2026-08-07): corpus 14,618 / 8,848 bài · eval 2,645 QA · alignment 30/30.
  Chi tiết + giới hạn: `../contracts/gates.md`. Quyết định: DEC-007…012.
- **Chuyển sang 1 người** (DEC-013): toàn bộ workstream eval/generation/test set trước
  thuộc Member B nay là của Đạt. Kéo theo DEC-014 (bỏ κ, bỏ nhóm C) và DEC-015 (thứ tự cắt).

## Blocker
- **Không còn blocker chặn build.** Gate 0 GO → được wire `loader → embedder → indexer → retriever`.
- Điều kiện vận hành (không phải blocker): corpus là dataset **gated**, mọi lần chạy
  ingestion/gate phải có `HF_TOKEN` trong env (đã set ở User scope; `setx` KHÔNG áp cho
  terminal đang mở — phải mở terminal mới).

## 3 việc kế tiếp
1. **CHỐT CHÍNH SÁCH GÁN KHOA trước khi viết `loader.py`** — việc siết keyword đã xong
   (DEC-010/011) nhưng **không chữa được trùng khoa**: 38.7% bài vẫn khớp cả 2 vì bài
   vinmec dài, bài tiểu đường luôn nhắc biến chứng tim mạch. Nguyên nhân là quy tắc
   "có mặt ở đâu cũng tính", không phải từ vựng. Số đo trên corpus thật:
   Tái lập bằng `python scripts/policy_audit.py` (cần `HF_TOKEN`):
   | chính sách | tim_mach | tieu_duong | trùng | alignment |
   |---|---|---|---|---|
   | có mặt là tính (hiện tại) | 14,618 | 8,848 | **38.7%** | PASS |
   | keyword phải ở TITLE | 306 | 559 | **1.1%** | PASS (29/30) |
   | TITLE hoặc ≥8 lần | 3,273 | 1,204 | 7.7% | PASS |
   | khoa trội (≥3, kia <½) | 7,548 | 2,390 | 9.3% | PASS |
2. Wire `loader.py` thật (bỏ `NotImplementedError` GATED) → lọc 2 khoa → clean → tag →
   `data/processed/`. Đóng DoD Tuần 1: ≥150 bài/khoa + thống kê theo khoa.
3. Hỏi GVHD xác nhận claim (5 phút, treo từ Session 2) — **và báo luôn việc dự án còn 1 người**.

## Backlog tiếp quản từ Member B (chưa bắt đầu — đường găng)

Không còn ai làm song song, nên các việc này phải chen vào lịch của chính mình.
Thứ tự dưới đây là thứ tự làm, không phải thứ tự tuần.

- **Test set v1 (~20 câu) có ground truth từ ViMedAQA** — gốc là Tuần 2. Chặn đo retrieval
  ở Tuần 3, nên phải xong trước khi hybrid+rerank có số. Mở rộng ~35–40 câu ở Tuần 3.
- **Rubric abstention + safety subset 50 câu** — gốc là Tuần 2 (front-load), chốt ở Tuần 5.
  **Chỉ còn 4 nhóm A/B/D/E, tỉ lệ A18 / B12 / D8 / E12** (DEC-014 — bỏ nhóm C và bỏ κ vì
  1 người không có inter-annotator). Nhóm E **bắt buộc có**, thiếu là không đo được false-refusal.
- **Generation Tuần 4**: tích hợp Gemini Flash, prompt bám context + citation [1][2] +
  disclaimer, baseline LLM-only (chỉ tắt bước retrieval).
- **Eval Tuần 6**: chạy RAGAS 4 metric, phân tích lỗi, abstention P/R theo nhóm A/B/D/E,
  % giảm hallucination (LLM-only vs Full RAG).
- **Streamlit UI thật** (hiện chỉ là demo Fake) + cost/1.000 query ở Tuần 7.
- **Báo cáo + slides** Tuần 8.

## Việc treo ngoài code
- **Xác nhận claim với GVHD** — treo từ Session 2; DEC-001…006 vẫn chưa được duyệt.
- Sync bản `.html` của plan (gửi file để cập nhật) — treo từ Session 2.
- Sau scaffold: chạy `pytest` + mở Streamlit xác nhận DoD trước khi wire real.
- **Rủi ro tiến độ (giờ là rủi ro số 1):** năng lực còn 1/2 nhưng scope giữ nguyên (DEC-015).
  Thứ tự cắt khi kẹt: E2 evidence-highlighting → ablation reranker on/off →
  ablation chunk 256 vs 512. Giữ risk–coverage + Static-vs-Corrective bằng mọi giá.
  Tuần 4–6 giờ gánh cả 2 luồng — nếu hết Tuần 5 mà safety subset chưa có nhãn thì cắt ngay E2.
# STATUS — ViMed-RAG (Đạt, solo)

> Owner: Đạt. Dự án **1 người** từ 2026-08-08 (DEC-013) — file này là state DUY NHẤT.
> Ghi đè mỗi session; **không** tạo `STATUS-v2`, **không** tách lại theo người.

**Cập nhật lần cuối:** 2026-08-08 (Session 4 — solo + chốt chính sách gán khoa)

## Đang làm
- Tuần 1: infra / data. Scaffold đã commit, 20 test xanh, Streamlit chạy bằng Fake.
- **Gate 0 = GO**, đã tái kiểm dưới chính sách gán khoa mới — cả 3 tiêu chí PASS.
  Số liệu + giới hạn: `../contracts/gates.md`. Quyết định: DEC-007…012, DEC-016.
- **Chuyển sang 1 người** (DEC-013): workstream eval/generation/test set trước thuộc
  Member B nay là của Đạt. Kéo theo DEC-014 (bỏ κ, bỏ nhóm C) và DEC-015 (thứ tự cắt).
- **Chính sách gán khoa đã chốt** (DEC-016): "keyword ở TITLE **hoặc** ≥25 lần".
  Corpus **727 tim_mach · 698 tieu_duong = 1.425 bài**. Chặn cuối trước `loader.py` đã gỡ.

## Blocker
- **Không còn blocker chặn build.** Gate 0 GO → được wire `loader → embedder → indexer → retriever`.
- Điều kiện vận hành (không phải blocker): corpus là dataset **gated**, mọi lần chạy
  ingestion/gate phải có `HF_TOKEN` trong env (đã set ở User scope; `setx` KHÔNG áp cho
  terminal đang mở — phải mở terminal mới).

## 3 việc kế tiếp
1. **Commit 5 file đang dirty** (DEC-016 + `gates.md` + STATUS + `policy_cost_audit.py` mới
   + `alignment_audit.py`). Dùng skill `git-commit`; `.claude/settings.json` vẫn để ngoài.
2. **Wire `loader.py` thật** (bỏ `NotImplementedError` GATED) → áp DEC-016 → clean → tag →
   `data/processed/`. Đóng DoD Tuần 1: ≥150 bài/khoa + thống kê theo khoa + Qdrant chạy.
   Ngưỡng 25 phải đọc từ config, **không hard-code**. Tái lập số: `scripts/policy_cost_audit.py`.
3. Hỏi GVHD xác nhận claim (5 phút, treo từ Session 2) — **và báo luôn việc dự án còn 1 người**
   + xin xác nhận việc bỏ Cohen's κ (DEC-014). Thầy không chịu thì phải đảo trước Tuần 5.

## Đã biết về corpus — đừng đo lại
- **`both%` (trùng khoa) là chỉ số đánh lừa.** Nó bão hoà ở ~2% từ ngưỡng ≥15, trong khi
  80% bài `tim_mach` vẫn lọt vào bằng đếm thân bài. Chỉ số dùng được là **`title-hit`**.
- **Hai khoa không đối xứng.** `tiểu đường` là tên bệnh nên nằm ở tiêu đề (80% ở ngưỡng 25);
  từ vựng tim mạch rải khắp bài dinh dưỡng + tờ hướng dẫn thuốc (42%). Ô nhiễm dồn về `tim_mach`.
- **Nhiễu còn lại ở ngưỡng 25:** bài gây mê/phẫu thuật ("Gây tê tủy sống", "thuốc Sevorane")
  lọt vào `tim_mach` vì theo dõi huyết áp được nhắc rất nhiều. ~1–2 bài/12 khi soi tay.
  Chưa đáng chữa; nếu Tuần 3 thấy retrieval bị nhiễu thì nâng ngưỡng lên 30 (546/658, title-hit 72%).
- **Ngân sách Qdrant Cloud free 1GB:** chính sách đã chốt dùng ~8% cho CẢ 2 collection
  (chunk 256 + 512). Chính sách cũ dùng 89% → không deploy được. Còn rất nhiều chỗ trống.

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
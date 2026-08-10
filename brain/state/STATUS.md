# STATUS — ViMed-RAG (Đạt, solo)

> Owner: Đạt. Dự án **1 người** từ 2026-08-08 (DEC-013) — file này là state DUY NHẤT.
> Ghi đè mỗi session; **không** tạo `STATUS-v2`, **không** tách lại theo người.

**Cập nhật lần cuối:** 2026-08-09 (Session 5 — loader thật, corpus đã nằm trong `data/processed/`)

## Đang làm
- Tuần 1: infra / data. **38 test xanh** (20 cũ + 18 test loader mới), Streamlit chạy bằng Fake.
- **Gate 0 = GO**, đã tái kiểm dưới chính sách gán khoa mới — cả 3 tiêu chí PASS.
  Số liệu + giới hạn: `../contracts/gates.md`. Quyết định: DEC-007…012, DEC-016.
- **Chuyển sang 1 người** (DEC-013): workstream eval/generation/test set trước thuộc
  Member B nay là của Đạt. Kéo theo DEC-014 (bỏ κ, bỏ nhóm C) và DEC-015 (thứ tự cắt).
- **`loader.py` đã wire thật** — bỏ `NotImplementedError`, áp DEC-016, chạy trên corpus
  thật ra **đúng số đã chốt**: 727 tim_mach · 698 tieu_duong · trùng 15 = 1.1%.
  Corpus ở `data/processed/corpus.jsonl` (1.410 bài, 12.8 MB, gitignore — không commit).
  Hình dạng dữ liệu ra: **DEC-017** — lọc khoa phải dùng `specialties` (tuple), KHÔNG
  phải `specialty` đơn, nếu không Tuần 3 âm thầm đánh rơi 15 bài trùng khoa.
- Ranh giới GATED kế tiếp: chunk → **embed (`BgeM3Embedder`, Tuần 2)** → **index
  (`QdrantIndexer`, Tuần 3)**. `run_ingestion.py` dừng đúng ở đó.

## Blocker
- **Không còn blocker chặn build.**
- Điều kiện vận hành (không phải blocker): corpus là dataset **gated**, mọi lần chạy
  ingestion/gate phải có `HF_TOKEN` trong env (đã set ở User scope; `setx` KHÔNG áp cho
  terminal đang mở — phải mở terminal mới).

## 3 việc kế tiếp
1. **Đóng nốt DoD Tuần 1: Qdrant chạy được.** `docker-compose up -d` rồi xác nhận kết nối.
   ≥150 bài/khoa và thống kê theo khoa đã xong (`python scripts/run_ingestion.py`).
2. **Tuần 2 — `BgeM3Embedder` thật + index HAI collection** (chunk 256 và 512, DEC-004).
   Ngân sách đã tính sẵn: ~8% Qdrant Cloud free 1GB, còn rất nhiều chỗ.
   Trước khi index: **in 20–30 chunk ra đọc bằng mắt** (plan liệt kê "chunking kém →
   retrieval rác" là rủi ro riêng). Song song: **test set v1 ~20 câu** từ ViMedAQA
   (chặn đo retrieval ở Tuần 3) — nhưng đọc format RAGAS trước, xem việc treo bên dưới.
   ⚠️ Embedding chạy trên **Kaggle T4**, mà `corpus.jsonl` bị gitignore nên **không tự có
   ở đó**: phải upload thành Kaggle Dataset hoặc chạy lại ingestion trên Kaggle với
   `HF_TOKEN`. Quyết cách nào TRƯỚC khi mở notebook.
3. Hỏi GVHD xác nhận claim (5 phút, treo từ Session 2) — **và báo luôn việc dự án còn 1 người**
   + xin xác nhận việc bỏ Cohen's κ (DEC-014). Thầy không chịu thì phải đảo trước Tuần 5.

## Đã biết về corpus — đừng đo lại
- **1.425 và 1.410 đều đúng, đừng tưởng lệch.** 1.425 = 727 + 698 (cộng dồn theo khoa,
  15 bài trùng đếm 2 lần); 1.410 = số bài phân biệt. DEC-016 ghi kiểu cộng dồn.
- **Kích thước cho Tuần 2:** 1.410 bài ≈ **2,04 triệu từ**, median 1.388 từ/bài
  (min 57, max 4.229). Chunker tách token theo khoảng trắng nên đây là số dùng để ước chunk.
- **`both%` (trùng khoa) là chỉ số đánh lừa.** Nó bão hoà ở ~2% từ ngưỡng ≥15, trong khi
  80% bài `tim_mach` vẫn lọt vào bằng đếm thân bài. Chỉ số dùng được là **`title-hit`**.
- **Hai khoa không đối xứng.** `tiểu đường` là tên bệnh nên nằm ở tiêu đề (80% ở ngưỡng 25);
  từ vựng tim mạch rải khắp bài dinh dưỡng + tờ hướng dẫn thuốc (42%). Ô nhiễm dồn về `tim_mach`.
- **Nhiễu còn lại ở ngưỡng 25:** bài gây mê/phẫu thuật ("Gây tê tủy sống", "thuốc Sevorane")
  lọt vào `tim_mach` vì theo dõi huyết áp được nhắc rất nhiều. ~1–2 bài/12 khi soi tay.
  Chưa đáng chữa; nếu Tuần 3 thấy retrieval bị nhiễu thì nâng ngưỡng lên 30 (546/658, title-hit 72%).
  Soi `corpus.jsonl` thấy thêm một dạng: bài dịch tễ liệt kê bệnh nền ("ca tử vong do
  Covid") lọt vào **cả 2 khoa** vì nhắc huyết áp + tiểu đường rất nhiều. Cùng nguyên nhân.
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
- **Đọc phần format dataset của RAGAS TRƯỚC khi soạn test set v1** — plan cảnh báo thẳng:
  test set viết sai format thì Tuần 6 phải làm lại. Việc đọc duy nhất có deadline thật.
- **`.claude/settings.json` vẫn dirty có chủ đích** (treo từ Session 4): 26 dòng allowlist
  trỏ scratchpad đã chết + `Bash(env)` in ra `HF_TOKEN`. Dọn hoặc bỏ qua, đừng commit nguyên trạng.
- Sync bản `.html` của plan (gửi file để cập nhật) — treo từ Session 2.
- **Chưa mở lại Streamlit bằng mắt** sau khi thêm khối `data` vào config (Session 5).
  Đã kiểm phần rủi ro: `load_config()` chạy được và `app/streamlit_app.py` compile sạch
  (app chỉ gọi `load_config()`, không tự dựng `AppConfig`). Còn lại là xác nhận UI.
- **Rủi ro tiến độ (giờ là rủi ro số 1):** năng lực còn 1/2 nhưng scope giữ nguyên (DEC-015).
  Thứ tự cắt khi kẹt: E2 evidence-highlighting → ablation reranker on/off →
  ablation chunk 256 vs 512. Giữ risk–coverage + Static-vs-Corrective bằng mọi giá.
  Tuần 4–6 giờ gánh cả 2 luồng — nếu hết Tuần 5 mà safety subset chưa có nhãn thì cắt ngay E2.
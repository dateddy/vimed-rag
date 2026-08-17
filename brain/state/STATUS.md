# STATUS — ViMed-RAG (Đạt, solo)

> Owner: Đạt. Dự án **1 người** từ 2026-08-08 (DEC-013) — file này là state DUY NHẤT.
> Ghi đè mỗi session; **không** tạo `STATUS-v2`, **không** tách lại theo người.

**Cập nhật lần cuối:** 2026-08-13 (Session 8 — **lớp embed+index đã code xong, chờ chạy GPU**)

## Đang làm
- **🔨 TUẦN 2 — code xong toàn bộ phần chạy được không GPU (DEC-021).** `BgeM3Embedder`
  + `QdrantIndexer` + `scripts/build_index.py` + `scripts/verify_index.py` +
  `notebooks/kaggle_build_index.ipynb`. **50 test xanh** (38 cũ + 12 mới).
  Hai lớp bảo vệ đã chạy THẬT trước khi tốn GPU:
  · `--dry-run` ra đúng **4.972** (512) / **10.246** (256) — khớp DEC-020;
  · `--fake --limit 20 --smoke` ghi 20 point lên Qdrant Cloud thật rồi tự xoá →
  schema dense+sparse+payload index OK, cluster trở lại 0 collection.
  **Còn lại đúng 2 việc tay:** upload corpus thành Kaggle Dataset + chạy notebook trên T4.
- **✅ DoD TUẦN 1 ĐÓNG** (cả 3 tiêu chí): repo clone chạy được (**38 test xanh**) ·
  ≥150 bài/khoa đã clean + tag (727/698) · **Qdrant chạy** (Cloud, đã smoke test).
- **✅ SOI CHUNK XONG — chunking chốt `512/50`, không sửa gì (DEC-020).** Cả 3 tiêu chí
  (rác HTML · menu/footer · bảng vỡ) PASS bằng máy trên toàn bộ 4.972 chunk; 25 mẫu soi
  tay không mẫu nào mất nghĩa. **Cửa sổ "sửa rẻ" đã đóng đúng cách** — từ đây đổi chunking
  = phải embed lại cả 2 collection. Tái lập: `python scripts/chunk_audit.py --size 512`.
- Bước vào **Tuần 2 — Embedding & Indexing**. Streamlit vẫn đang chạy bằng Fake.
- **Gate 0 = GO**, đã tái kiểm dưới chính sách gán khoa mới — cả 3 tiêu chí PASS.
  Số liệu + giới hạn: `../contracts/gates.md`. Quyết định: DEC-007…012, DEC-016.
- **Chuyển sang 1 người** (DEC-013): workstream eval/generation/test set trước thuộc
  Member B nay là của Đạt. Kéo theo DEC-014 (bỏ κ, bỏ nhóm C) và DEC-015 (thứ tự cắt).
- **`loader.py` đã wire thật** — bỏ `NotImplementedError`, áp DEC-016, chạy trên corpus
  thật ra **đúng số đã chốt**: 727 tim_mach · 698 tieu_duong · trùng 15 = 1.1%.
  Corpus ở `data/processed/corpus.jsonl` (1.410 bài, 12.8 MB, gitignore — không commit).
  Hình dạng dữ liệu ra: **DEC-017** — lọc khoa phải dùng `specialties` (tuple), KHÔNG
  phải `specialty` đơn, nếu không Tuần 3 âm thầm đánh rơi 15 bài trùng khoa.
- **GVHD đã duyệt claim (DEC-019)** — DEC-001…006 + DEC-014 thông qua, đã báo dự án còn
  1 người. Việc treo lớn nhất, mở từ Session 2, đã đóng. Rủi ro "phải đảo DEC-014 trước
  Tuần 5" **tắt hẳn**. Limitations báo cáo vẫn phải ghi "không có inter-annotator agreement".
- **Vector store = Qdrant Cloud, không Docker local (DEC-018).** Lý do: Docker Desktop
  chưa hề được cài trên máy, mà Tuần 7 deploy HF Spaces thì bắt buộc phải có Qdrant truy
  cập được từ internet. `docker-compose.yml` hạ xuống làm dự phòng offline.
  **Cluster đã sống**: `eu-west-1-0.aws`, 0 collection. Tái kiểm bất cứ lúc nào:
  `python scripts/smoke_qdrant.py` (không ghi gì lên cluster).
- **Ranh giới GATED đã lùi.** `BgeM3Embedder` + `QdrantIndexer` đã implement (DEC-021);
  `run_ingestion.py` dừng ở `corpus.jsonl`, `build_index.py` gánh tiếp. Còn GATED:
  `HybridRetriever` (Tuần 3) · `LLMRewriter`/`GeminiGenerator` (Tuần 4) ·
  `run_ragas`/`risk_coverage` (Tuần 6).
- **Chốt của DEC-021 cần nhớ khi làm Tuần 3:** vector có TÊN — dense là `"dense"`,
  sparse là `"sparse"` (hằng `DENSE_VECTOR`/`SPARSE_VECTOR` trong `indexer.py`).
  Lọc khoa phải match payload **`specialties`** (list, có KEYWORD index), KHÔNG phải
  `specialty` số ít. Collection: `vimed_rag_512` và `vimed_rag_256`.

## Blocker
- **Không còn blocker chặn build.**
- Điều kiện vận hành (không phải blocker): corpus là dataset **gated**, mọi lần chạy
  ingestion/gate phải có `HF_TOKEN` trong env (đã set ở User scope; `setx` KHÔNG áp cho
  terminal đang mở — phải mở terminal mới).

## 3 việc kế tiếp
1. **Chạy index thật trên Kaggle T4 — chỉ còn việc tay, code đã xong.**
   Chốt cách đưa corpus: **upload `corpus.jsonl` thành Kaggle Dataset private**
   (KHÔNG chạy lại ingestion — DEC-020 đo trên đúng file đó, sinh lại là số hết hiệu lực).
   a. Upload `data/processed/corpus.jsonl` (12,8 MB) → Kaggle Dataset private.
   b. Add-ons → Secrets: `QDRANT_URL` + `QDRANT_API_KEY`. **Đừng dán vào cell.**
   c. Mở `notebooks/kaggle_build_index.ipynb`, sửa `CORPUS` cho khớp slug, chạy tuần tự.
   d. `verify_index.py` phải PASS cả 2 size trước khi coi Tuần 2 là xong.
   Kiểm chéo: 512 → 4.972 point · 256 → 10.246 point. Chạy lại an toàn (upsert đè).
2. **Đọc phần format dataset của RAGAS + pin phiên bản vào `requirements.txt`** TRƯỚC khi
   soạn test set v1. Đây là việc đọc duy nhất có deadline thật: sai format thì Tuần 6 làm lại.
   ~~Hỏi GVHD xác nhận claim~~ → **xong 2026-08-11, DEC-019.**
3. **Test set v1 (~20 câu) từ ViMedAQA** — đường găng tiếp quản từ Member B, chặn đo
   retrieval ở Tuần 3. Làm SAU khi đã đọc format RAGAS ở việc 2, không làm trước.
   ~~Soi chunk bằng mắt~~ → **xong 2026-08-13, DEC-020.**

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
- **Số chunk đã đo, đừng chunk lại để đếm** (`scripts/chunk_audit.py`, DEC-020):
  **512/50 → 4.972 chunk** (3,5 chunk/bài, max 10, dense 19,4 MB = 1,9% free tier);
  **256/50 → 10.246 chunk** (7,3 chunk/bài, max 21, dense 40,0 MB = 3,9%).
  Tổng 15.218 vector, dense 59 MB = 5,8% — cộng sparse + payload ra đúng vùng ~8% ở
  DEC-016, **không phải tính lại ngân sách**.
- **Đuôi vụn là lý do thật để ưu tiên 256 trong ablation:** 512 có 151 chunk (3,0%) ngắn
  hơn 20% size; 256 chỉ có 4 (0,0%). Ghi lại để Tuần 2 khỏi đoán.
- **Nhiễu chunk còn lại, đã đo, đã quyết KHÔNG chữa:** caption ảnh bị nhét giữa dòng văn
  (thấy ở mẫu 3, 6, 7 — do `_WS_RE` trong `cleaner.py` gộp `\n`) · byline "Bài viết được
  tư vấn chuyên môn bởi BS…Vinmec" ở đầu 17,6% bài. Byline chỉ chiếm **0,16%** token toàn
  corpus → không đáng chạy lại ingestion. **Nhưng byline có tên bác sĩ + tên bệnh viện:**
  Tuần 4–5 làm citation phải để ý đừng để hệ thống trích dẫn thành "BS X khẳng định…".

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
- ~~Xác nhận claim với GVHD~~ — **ĐÓNG 2026-08-11 (DEC-019).**
- ~~Dọn `.claude/settings.json`~~ — **ĐÓNG 2026-08-11**: 42 → 22 rule. Bỏ `Bash(env)` +
  lệnh in prefix `HF_TOKEN` (rò secret), 8 rule trỏ scratchpad session cũ đã chết, và các
  lệnh một-lần. Giữ git/pytest/5 script audit; thêm 1 rule pytest chung.
- **Đọc phần format dataset của RAGAS TRƯỚC khi soạn test set v1** — plan cảnh báo thẳng:
  test set viết sai format thì Tuần 6 phải làm lại. Việc đọc duy nhất có deadline thật.
  **Kèm theo: pin phiên bản RAGAS vào `requirements.txt`** — `ragas>=0.1` hiện quá lỏng,
  0.1.x và 0.2+ dùng tên trường KHÁC NHAU (`question`/`answer`/`contexts`/`ground_truth`
  vs `user_input`/`response`/`retrieved_contexts`/`reference`). Không pin = viết test set
  theo một schema rồi cài phải schema kia.
- ~~Sync bản `.html` của plan~~ — **BỎ QUA (quyết định 2026-08-12).** Bản `.html` giờ
  lệch `.md` ở DEC-013…019. Đừng nêu lại việc này ở phiên sau.
- **Rotate API key Qdrant** — key hiện tại từng bị dán nhầm vào `.env.example` (file được
  git track). Chưa kịp commit nên **không có gì lên remote**, đã gỡ sạch. Nhưng key đã đi
  qua context nên rotate cho sạch: dashboard → xoá key cũ → tạo mới → sửa 1 dòng `.env`.
  **Quy tắc:** `.env.example` chỉ chứa placeholder; giá trị thật chỉ nằm ở `.env`.
- **Thống kê theo khoa chưa được lưu thành file.** `run_ingestion.py` chỉ *in* ra stdout,
  mà `data/processed/` thì gitignore → deliverable Tuần 1 "corpus + thống kê theo khoa"
  hiện chỉ tồn tại trong brain (727/698/15 ở DEC-016 + mục "Đã biết về corpus" trên).
  Đủ để bảo vệ, nhưng nếu muốn có artifact trong repo thì ghi `docs/corpus-stats.md`
  (~10 phút). Chưa làm, không chặn gì.
- **Chưa mở lại Streamlit bằng mắt** sau khi thêm khối `data` vào config (Session 5).
  Đã kiểm phần rủi ro: `load_config()` chạy được và `app/streamlit_app.py` compile sạch
  (app chỉ gọi `load_config()`, không tự dựng `AppConfig`). Còn lại là xác nhận UI.
- **Rủi ro tiến độ (giờ là rủi ro số 1):** năng lực còn 1/2 nhưng scope giữ nguyên (DEC-015).
  Thứ tự cắt khi kẹt: E2 evidence-highlighting → ablation reranker on/off →
  ablation chunk 256 vs 512. Giữ risk–coverage + Static-vs-Corrective bằng mọi giá.
  Tuần 4–6 giờ gánh cả 2 luồng — nếu hết Tuần 5 mà safety subset chưa có nhãn thì cắt ngay E2.
# STATUS — ViMed-RAG (Đạt, solo)

> Owner: Đạt. Dự án **1 người** từ 2026-08-08 (DEC-013) — file này là state DUY NHẤT.
> Ghi đè mỗi session; **không** tạo `STATUS-v2`, **không** tách lại theo người.

**Cập nhật lần cuối:** 2026-08-18 (Session 8 — **TUẦN 2 ĐÓNG: 2 collection đã index + verify PASS**)

## Đang làm

- **🔀 ĐỔI THỨ TỰ (2026-08-19): làm SAFETY SUBSET TRƯỚC Tuần 3.** Lý do: nhóm E (12 câu
  answerable) là tập con của test set v1 — cái đang chặn đo retrieval — nên làm trước là
  được 12/20 câu miễn phí; và DEC-015 đặt tripwire "hết Tuần 5 chưa có nhãn → cắt E2"
  ngay ở đây. Tiến độ: **Bước 0 XONG** (DEC-022, pin `ragas==0.4.3`) · **Bước 1 XONG**
  (`config/abstention_policy.md` v1, DEC-023 + DEC-024) · **Bước 2 XONG** (nhóm E, 12 câu,
  DEC-025) · **Bước 3 XONG** (nhóm A 18 + nhóm B 12, DEC-026…030).
  · **Bước 4 XONG** (nhóm D, 8 câu viết tay).
  **✅ SAFETY SUBSET ĐÓNG: `data/testset.jsonl` = 50/50 câu (A18/B12/D8/E12),
  24/24 tiêu chí nghiệm thu PASS.** Tái lập: `python scripts/build_testset.py`.
  **Kế tiếp: TUẦN 3 — `HybridRetriever`.** Đường găng đã thông: nhóm E kèm
  `reference_context_ids` nên dùng luôn làm ground truth đo recall@k.
- **Bước 3 bắt được một lỗi của Bước 2 — đọc DEC-027 trước khi đụng lại test set.**
  Dựng nhóm A vô tình thành phép kiểm chéo: `Aspirin STELLA` vừa là nhóm E (ANSWER)
  vừa là nhóm A (ABSTAIN). Gốc: TF-IDF cao trên ĐÁP ÁN không bảo đảm THỰC THỂ được
  phủ. Bộ lọc mới loại **41,6%** QA "trong khoa" của ViMedAQA vì thực thể vắng mặt.
  Hai script giờ dùng **cùng phép kiểm, ngược chiều**: E đòi thực thể CÓ MẶT, A/B đòi
  VẮNG MẶT — không thể mâu thuẫn nữa.
- **⚠️ `specialty` của nhóm A/B KHÔNG đáng tin (DEC-030), đã đánh dấu
  `specialty_verified: false`.** Nó đến từ bộ lọc keyword sai cả hai hướng
  (`Ung thư xương` lọt vào A; `Hẹp van 2 lá` bị loại). Phân bố `tim_mach 15/tieu_duong 3`
  là hiện vật của bộ lọc, KHÔNG phải sự thật. **Tuần 6 chỉ tách abstention theo nhóm
  A/B/D/E, TUYỆT ĐỐI không tách theo khoa trên nhóm A/B.**
- **⚠️ DEC-024 đổi contract:** defense-in-depth **7 → 8 lớp**, thêm policy gate chạy TRƯỚC
  retrieval. Không có lớp này thì nhóm D có abstention recall **0%** (corpus CÓ bài
  metformin → grader CORRECT → ANSWER). `trace` phải tách ABSTAIN-do-policy khỏi
  ABSTAIN-do-retrieval, nếu không Tuần 6 không vẽ được risk–coverage đúng.
- **✅ TUẦN 2 ĐÓNG — HAI COLLECTION ĐÃ SỐNG TRÊN QDRANT CLOUD.** Chạy trên **Kaggle T4**
  bằng `notebooks/kaggle_build_index.ipynb`. `verify_index.py` **PASS cả 4 mục
  cho cả 2 size**:
  · `vimed_rag_512` = **4.972 point** · `vimed_rag_256` = **10.246 point** (khớp DEC-020)
  · dense 1024/Cosine + sparse đều có · search trả kết quả
  · **chunk thuộc 2 khoa: 67 (512) / 140 (256)** — bất biến DEC-017 đứng vững trên
    dữ liệu thật, không phải chỉ trong test.
  Code: `BgeM3Embedder` + `QdrantIndexer` + `build_index.py` + `verify_index.py`
  + `notebooks/kaggle_build_index.ipynb` (bản đã chạy thật). **50 test xanh** (38 cũ + 12 mới).
- **Dung lượng thật đã đo (telemetry Qdrant):** vectors 76,6 MB + payload 21,1 MB =
  **97,7 MB ≈ 9,5% free tier 1GB**. DEC-016 dự toán ~8% → lệch +1,5 điểm, trong sai số,
  **không cần ghi DECISIONS mới**. Còn trống ~90%, thoải mái cho Tuần 3–7.
- **Tuần 3 mở**: hybrid retrieval + rerank (`HybridRetriever`) đã hết vật cản hạ tầng.
- **✅ DoD TUẦN 1 ĐÓNG** (cả 3 tiêu chí): repo clone chạy được (**38 test xanh**) ·
  ≥150 bài/khoa đã clean + tag (727/698) · **Qdrant chạy** (Cloud, đã smoke test).
- **✅ SOI CHUNK XONG — chunking chốt `512/50`, không sửa gì (DEC-020).** Cả 3 tiêu chí
  (rác HTML · menu/footer · bảng vỡ) PASS bằng máy trên toàn bộ 4.972 chunk; 25 mẫu soi
  tay không mẫu nào mất nghĩa. **Cửa sổ "sửa rẻ" đã đóng đúng cách** — từ đây đổi chunking
  = phải embed lại cả 2 collection. Tái lập: `python scripts/chunk_audit.py --size 512`.
- Bước vào **Tuần 3 — Hybrid retrieval & rerank**. Streamlit vẫn đang chạy bằng Fake.
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
  **Cluster đã sống**: `eu-west-1-0.aws`, **2 collection** (`vimed_rag_512` +
  `vimed_rag_256`). Tái kiểm bất cứ lúc nào: `python scripts/smoke_qdrant.py`
  (kết nối) · `python scripts/verify_index.py --size 512` (nội dung). Cả hai chỉ đọc.
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
1. ~~Đọc format RAGAS + pin phiên bản~~ → **XONG 2026-08-19, DEC-022.** Pin `ragas==0.4.3`
   (giữ comment tới Tuần 6). Cảnh báo "0.1.x vs 0.2+" đã lỗi thời — ragas chưa từng có bản
   ≥1.0. **Chốt quan trọng hơn tên cột:** nhóm E phải thu `reference_contexts` (VĂN BẢN chunk)
   + `reference_context_ids` NGAY lúc soạn → 3/4 metric Tuần 6 chạy không cần LLM.
   Tên trường + ma trận metric chép sẵn trong `requirements.txt`.
   ~~Hỏi GVHD xác nhận claim~~ → **xong 2026-08-11, DEC-019.**
2. **Test set v1 (~20 câu) từ ViMedAQA** — đường găng tiếp quản từ Member B, chặn đo
   retrieval ở Tuần 3. Làm SAU khi đã đọc format RAGAS ở việc 1, không làm trước.
   ~~Soi chunk bằng mắt~~ → **xong 2026-08-13, DEC-020.**
3. **Tuần 3 — `HybridRetriever`**: dense+sparse trên Qdrant + rerank
   `bge-reranker-v2-m3`. Hạ tầng đã sẵn sàng, không còn vật cản.
   ⚠️ Nhớ 2 chốt của DEC-021: vector có TÊN (`"dense"`/`"sparse"`), lọc khoa phải match
   payload **`specialties`** (list) chứ không `specialty` số ít.
   ~~Chạy index trên GPU~~ → **xong 2026-08-18, cả 2 collection PASS.**

## Đã biết về hạ tầng — đừng thử lại

- **Máy local KHÔNG embed được, đã đo, đừng thử lại.** i5-1135G7 (4 nhân, GPU Intel
  Iris Xe không CUDA), torch bản `+cpu`: **0,22 chunk/s** trên chunk thật 512.
  → 6,2 giờ cho size 512, ~12–13 giờ cho cả hai. Ép thêm thread không cứu được (4 nhân
  vật lý). Đo bằng 20 chunk thật, warmup tách riêng.
- **Lần đo đó xác nhận `BgeM3Embedder` chạy đúng với model + corpus THẬT:** dense
  dim 1024, sparse trung bình **140 token khác 0**/chunk, sạch với `transformers 5.5.4`.
  Nghĩa là code không còn rủi ro — chỉ thiếu phần cứng.
- **Kaggle: "không chọn được Accelerator" + "git clone fail" = MỘT nguyên nhân duy nhất
  — tài khoản chưa xác minh SĐT.** Kaggle khoá **GPU và Internet cùng lúc**, nên hai
  triệu chứng nhìn rời rạc thực ra là một. **Đã xác minh → cả hai hết ngay**, index chạy
  bình thường. Nếu gặp lại (đổi máy/tài khoản): xác minh SĐT trước, đừng debug riêng lẻ.
- **`notebooks/colab_build_index.ipynb` viết ra nhưng CHƯA TỪNG CHẠY.** Sinh ra lúc còn
  tưởng Kaggle không cứu được. Giữ làm dự phòng khi Kaggle hết quota GPU (30h/tuần),
  nhưng **đừng tin nó chạy được** — chưa có lần thực thi nào. Dùng nó thì phải soi lại
  cell upload corpus + Colab Secrets trước.
- **Model bge-m3 (~2,3 GB) đã cache** ở `~/.cache/huggingface` trên máy local.

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
- ~~Việc 1.4 — kiểm bằng máy policy vs nhóm E~~ — **ĐÓNG 2026-08-23 (DEC-031), 6/6 PASS.**
  Đã mechanize policy sớm (`config/abstention_policy.yaml`, kéo từ Tuần 5 về) nên
  `check_policy()` ở Tuần 4–5 chỉ còn là nạp yaml + gọi `match_rules()`.
  Tiêu chí rộng hơn bản đầu: khớp D **8/8** · **0** khớp ở E/A/B · **0** ca ranh giới.
  Tái lập: `python scripts/check_policy_coverage.py`.
- **Phương án B đã cân nhắc và HOÃN (DEC-029), đừng nghĩ lại từ đầu:** viết lại 12 câu
  nhóm E sang giọng bệnh nhân, giữ nguyên `reference` + `reference_context_ids`, rồi đo
  cùng câu ở HAI văn phong. Rẻ về nhãn (không cần soi lại), cho một trục kết quả thứ hai
  cạnh Static-vs-Corrective. **Điều kiện làm:** chỉ khi 50 câu đã đóng và còn thời gian —
  và phải xếp TRÊN E2 trong thứ tự cắt DEC-015, tức chấp nhận E2 chết trước.
- **ABSTAIN-do-retrieval vẫn mang theo chunk — rủi ro UI, quyết ở Tuần 7.**
  `pipeline.py:99` truyền `ctx` vào `chunks` ở nhánh từ chối. Nếu UI hiển thị chúng thì
  màn hình "tôi không đủ căn cứ để trả lời" lại kèm 5 nguồn trông rất thuyết phục →
  người dùng hiểu ngược đúng cái thông điệp an toàn mà cả đề tài đang muốn truyền.
  Policy-ABSTAIN không dính (chunks rỗng vì gate chạy trước retrieval).
  Không chặn gì bây giờ; đừng để rơi khi làm UI thật.
- **`config/prompts/abstain.txt` là MỘT thông điệp dùng chung**, giờ cần ≥3 biến thể:
  policy thường · cấp cứu (D-3, ngắn nhất có thể) · hết căn cứ do retrieval. Việc Tuần 4–5.
- ~~Xác nhận claim với GVHD~~ — **ĐÓNG 2026-08-11 (DEC-019).**
- ~~Dọn `.claude/settings.json`~~ — **ĐÓNG 2026-08-11**: 42 → 22 rule. Bỏ `Bash(env)` +
  lệnh in prefix `HF_TOKEN` (rò secret), 8 rule trỏ scratchpad session cũ đã chết, và các
  lệnh một-lần. Giữ git/pytest/5 script audit; thêm 1 rule pytest chung.
- ~~Đọc format RAGAS + pin phiên bản~~ — **ĐÓNG 2026-08-19 (DEC-022).** `ragas==0.4.3`.
  **Việc treo MỚI kéo theo:** ragas kéo 7 gói họ langchain + openai. Đã kết luận không vi
  phạm ràng buộc #1 (eval offline, không phải orchestration) và ghi vào DEC-022 — nhưng
  khi nào bỏ comment dòng ragas ở Tuần 6 thì `contract-guard` sẽ báo, **đừng hoảng**, trỏ
  về DEC-022. Env hiện tại vẫn sạch, `pip list` không có langchain.
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
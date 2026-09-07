# STATUS — ViMed-RAG (Đạt, solo)

> Owner: Đạt. Dự án **1 người** từ 2026-08-08 (DEC-013) — file này là state DUY NHẤT.
> Ghi đè mỗi session; **không** tạo `STATUS-v2`, **không** tách lại theo người.

**Cập nhật lần cuối:** 2026-09-07 (Session 11 — **T4.1 policy gate + T4.2 generation đã chạy thật. 149 test PASS**)

## Đang làm

- **✅ T4.2 ĐÓNG — `GeminiGenerator` GỌI ĐƯỢC GEMINI THẬT** (DEC-045).
  SDK **`google-genai` 2.22.0**, KHÔNG phải `google-generativeai` (đóng băng ở 0.8.6).
  `transport` tiêm được → **149/149 test PASS mà không test nào chạm mạng hay cần key**.
  Tái lập: `python scripts/smoke_generation.py` (2 lượt API, ngữ cảnh giả, ~5s) ·
  thêm `--real-retrieval` để đi qua Qdrant + rerank thật (~17s/truy vấn, DEC-042).
  - Smoke trên API thật **9/9 PASS**: có `[n]`, 0 trích dẫn bịa, byline đã cắt,
    có câu miễn trừ, bản caution mở đầu đúng "[Lưu ý: độ chắc chắn thấp]".
  - **`gen.last_invalid_citations`** = các `[n]` bịa đã bị xoá → **chỉ báo
    hallucination rẻ, không cần LLM judge**. Tuần 6 dùng được ngay, đừng bỏ quên.
  - Byline giờ cắt bằng `src/data/cleaner.strip_byline` (dùng chung với
    `build_testset.py`). ⚠️ **Corpus đang index VẪN còn byline** — DEC-020 không
    chạy lại ingestion; đây là phép cắt ở tầng đọc ra, đừng tưởng data đã sạch.
  - ⚠️ **CHƯA XONG TUẦN 4:** `LLMRewriter` vẫn GATED → vòng corrective chạy thật
    vẫn viết lại bằng hậu tố giả `"(viết lại)"`. Và grader vẫn **KHÔNG** được nối.
- **✅ T4.1 ĐÓNG — POLICY GATE ĐÃ NẰM TRONG `_route()`** (DEC-044, implement DEC-024).
  `src/pipeline/policy.py` (`Policy`/`PolicyHit`/`load_policy`/`get_policy`) là bản
  **có thẩm quyền**; `scripts/check_policy_coverage.py` xoá bản regex riêng và import
  lại từ `src` → 4 mục PASS của script giờ là bằng chứng cho **đường chạy thật**.
  **134/134 test PASS** (123 cũ + 11 mới), script PASS **8/8 nhóm D**, 0 tràn E/A/B.
  Tái lập: `python -m pytest -q` · `python scripts/check_policy_coverage.py`.
  - **QUY TẮC TÁCH HAI CƠ CHẾ ABSTAIN — Tuần 6 đọc đúng dòng này:**
    policy-ABSTAIN ⇔ trace có bước `POLICY` với `note` **khác rỗng** (= `rule_id`);
    retrieval-ABSTAIN ⇔ bước `ABSTAIN` mang `state="INCORRECT"`.
    Bước `POLICY` được ghi **kể cả khi không khớp** (note rỗng) — đếm được "gate đã
    chạy" thay vì phải suy ra từ sự vắng mặt của bước.
  - 3 file prompt tách theo cơ chế: `abstain.txt` (retrieval) · `abstain_policy.txt`
    (D-1/D-2/D-4) · `abstain_policy_d3.txt` (cấp cứu, 1 câu, gọi 115).
    ⚠️ **Đừng gộp lại**: `abstain.txt` nói "chưa tìm được trong cơ sở dữ liệu" — với
    nhóm D đó là **nói dối**, corpus CÓ bài metformin. Backlog "3 biến thể abstain"
    của Tuần 4 coi như xong luôn ở đây.
  - policy-ABSTAIN trả `chunks=[]`. Nhánh **retrieval**-ABSTAIN vẫn mang chunk —
    cố ý chưa đụng, xem "Việc treo ngoài code".
- **✅ T3.4 ĐÓNG — có số đo thật.** `src/eval/retrieval_metrics.py` +
  `scripts/eval_retrieval.py` (chạy theo giai đoạn, **cache logit trên đĩa**, lưu sau
  mỗi lô nên đứt giữa chừng không mất công). Báo cáo: `docs/retrieval-eval.md` + `.csv`.
  **123/123 test PASS.** Tái lập:
  `python scripts/eval_retrieval.py --no-rerank` (rẻ, ~1 phút) ·
  `python scripts/eval_retrieval.py --sizes 512 --modes hybrid --groups A,B,D,E` (~60 phút).
- **⛔ HAI CLAIM BỊ BÁC BỎ, chi tiết ở 2 mục ⛔ phần hạ tầng:** (1) "Hybrid > Dense"
  không chứng minh được — DEC-038; (2) ngưỡng grader `0.6/0.3` không an toàn —
  DEC-039. Cả hai đều **không sửa được bằng code**, phải sửa bằng cách báo cáo và
  bằng test set lớn hơn.

- **✅ T3.1 ĐÓNG — `HybridRetriever` đã kiểm trên `vimed_rag_512` thật.** 3 mode
  `hybrid`/`dense`/`sparse`, RRF **server-side** (DEC-034). `verify_index --size 512`
  **PASS 4/4**; smoke 3 mode đều trả bài đúng khoa, đúng chủ đề. Tái lập:
  `python scripts/verify_index.py --size 512` · `python scripts/smoke_retrieval.py`.
- **✅ T3.2 ĐÓNG — `BgeReranker` chạy trên dữ liệu thật.** `src/retrieval/reranker.py`:
  Protocol + `FakeReranker` + `BgeReranker`, nạp lười. `retrieve()` giờ là đường đầy đủ
  top-20 → rerank → top-5. **99/99 test PASS**, không test nào chạm mạng/nạp model.
  Tái lập: `python scripts/smoke_retrieval.py --rerank`.
- **5 quyết định Tuần 3 đã chốt:** DEC-033 (score rerank phải nằm trong (0,1))
  · DEC-034 (RRF server-side) · DEC-035 (mở rộng `RetrievedChunk` +5 trường)
  · DEC-036 (**KHÔNG lọc khoa** lúc retrieval — code viết sẵn, mặc định tắt)
  · **DEC-037 (supersedes DEC-033 phần backend): rerank đi thẳng `transformers`,
  sigmoid do CHÍNH REPO áp.**
- **⚠️ VẪN CHƯA nối `HybridRetriever` vào `RAGPipeline`** — nhưng lý do đã ĐỔI. Không
  còn là chuyện thang điểm (sigmoid đã sửa xong); giờ là **ngưỡng grader sai** và **chi
  phí 75s/truy vấn**. Xem 2 mục ⛔ ở phần hạ tầng. Nối trước khi T3.4 trả lời 2 câu đó
  là nối vào một cấu hình đã biết là hỏng.
- **✅ T3.6 ĐÓNG — Streamlit đã nối retriever THẬT.** `app/streamlit_app.py` có 2 tab:
  **Truy hồi thật** (`HybridRetriever` + `BgeReranker` trên Qdrant, hiện chunk kèm
  `title`/`source`/`doc_id`/đoạn i-n nhờ DEC-035) và **Corrective loop (Fake)** giữ
  nguyên demo cũ. Đóng luôn DoD Tuần 2 "UI hiển thị được raw chunk" treo từ Session 5.
  Đã kiểm chạy thật: `healthz` HTTP 200 + bare mode thực thi `main()` exit 0.
  ⚠️ **Cố ý KHÔNG nối vào `RAGPipeline`** (DEC-039) — nối vào là dựng demo trả lời cả
  câu đáng lẽ phải từ chối. Tab 1 chỉ hiện truy hồi + điểm rerank, kèm cảnh báo ngưỡng.
  Chạy: `streamlit run app/streamlit_app.py` (streamlit đã cài, 1.63.0).
- **✅ CHỐT CẤU HÌNH CHI PHÍ TUẦN 7 — DEC-042.** `top_k_dense` 20 → **10**, thêm
  `retrieval.rerank_max_length` = **512**. **75,0s → 17,2s mỗi truy vấn.**
- **✅ NHÓM E ĐÃ MỞ: 12 → 21 câu. Test set = 59 câu (A18/B12/D8/E21)** — DEC-043.
  Soi tay 106 ứng viên: loại 79, còn 27; bỏ tiếp 6 câu va bẫy (3 câu sản khoa "THA thai
  kỳ/tiền sản giật", 2 câu "đái tháo nhạt", 1 câu trùng nội dung atorvastatin) → 21.
  **Không đạt mục tiêu 35–40 của DEC-041 và đã chấp nhận dừng ở đây.** Lý do bỏ ghi
  thẳng trong `scripts/build_testset.py` để phiên sau đừng nhặt lại.
  Mọi tiêu chí nghiệm thu PASS · `check_policy_coverage.py` vẫn PASS.
- **✅ SAFETY SUBSET ĐÓNG** — A/B/D chốt từ Session 9 theo DEC-014 (`A18/B12/D8`),
  nhóm E mở lên 21 ở DEC-043. Tổng **59 câu**. Tiêu chí dựng + policy PASS toàn bộ.
  Tái lập: `python scripts/build_testset.py` · `python scripts/check_policy_coverage.py`.
- **Đổi thứ tự có chủ đích:** làm safety subset **TRƯỚC** Tuần 3. Lý do: nhóm E (12 câu
  answerable) là tập con của test set v1 — thứ đang chặn đo retrieval — nên làm trước
  được 12/20 câu miễn phí; và DEC-015 đặt sẵn tripwire ở đây.
- **⚠️ DEC-024 ĐỔI CONTRACT: defense-in-depth 7 → 8 lớp**, thêm **policy gate chạy TRƯỚC
  retrieval**. Không có lớp này thì nhóm D abstention recall = **0%** (corpus CÓ bài
  metformin → grader CORRECT → ANSWER). `trace` phải tách ABSTAIN-do-policy khỏi
  ABSTAIN-do-retrieval, nếu không Tuần 6 không vẽ được risk–coverage đúng.
- **Policy đã mechanize sớm** (kéo từ Tuần 5 về): `config/abstention_policy.yaml` v1.1.
  `check_policy()` ở Tuần 4–5 giờ chỉ còn là nạp yaml + gọi `match_rules()`.
- **✅ Tuần 2 đóng từ Session 8:** 2 collection sống trên Qdrant Cloud
  (`vimed_rag_512` = 4.972 point · `vimed_rag_256` = 10.246 point), verify PASS cả 4 mục.
  Dung lượng thật 97,7 MB ≈ **9,5%** free tier 1GB.
- **Gate 0 = GO** · **GVHD đã duyệt claim (DEC-019)** · chunking chốt `512/50` (DEC-020).
- ~~Streamlit chạy bằng Fake~~ — **đã nối retriever thật ở T3.6** (xem trên).

## Blocker

- **Không còn blocker chặn build.**
- **⚠️ Cluster Qdrant Cloud free tier NGỦ khi không dùng.** 2026-09-06 gặp lần đầu:
  DNS resolve OK, **TCP 443 mở**, nhưng TLS bị reset (`schannel: failed to receive
  handshake` / `WinError 10054`) — hỏng y hệt cả trong lẫn ngoài sandbox. Lần dùng
  cuối trước đó là 2026-08-18, cách **16 ngày**. Vào console bấm resume là sống lại,
  dữ liệu còn nguyên (4.972 point khớp DEC-020). **Cách nhận ra:** TCP mở mà TLS reset
  = LB còn sống, backend đã ngủ — ĐỪNG đi debug `.env`, DNS hay firewall. **Rủi ro
  thật:** ngủ quá lâu thì cluster bị **xoá**, phải index lại cả 2 collection = **một
  session GPU Kaggle (~6,2h cho 512)**. Trước mỗi đợt nghỉ dài nên đụng vào cluster 1
  lần cho đỡ rủi ro.
- Điều kiện vận hành: corpus là dataset **gated**, mọi lần chạy ingestion/gate phải có
  `HF_TOKEN` trong env (`setx` KHÔNG áp cho terminal đang mở — phải mở terminal mới).
  ViMedAQA thì **public**, không cần token.

## 3 việc kế tiếp

1. **`git push origin main`** — `origin/main` ở `36b5389`, treo **2 commit** (handoff
   Session 10 + T4.1). Con số "21 commit" ở bản trước đã lỗi thời, phần lớn đã push.
2. **T4.3 — `LLMRewriter` thật.** [rewriter.py](src/pipeline/rewriter.py) còn GATED,
   prompt `config/prompts/query_rewrite.txt` đã sẵn. Đi lại đúng khuôn `transport`
   tiêm được của `GeminiGenerator` (DEC-045) để test không chạm mạng. Nhớ: rewrite
   tính là **+1 LLM call** mỗi truy vấn INCORRECT — vào bảng chi phí Tuần 7.
   Sau đó **T4.4 baseline LLM-only** (không retrieval) cho bảng so sánh Tuần 6.
3. **Cạm bẫy còn lại của Tuần 4.**
   ⚠️ Vẫn **KHÔNG** nối grader vào đường thật cho tới khi có ngưỡng hiệu chỉnh.
   ⚠️ ~~Nhớ cắt byline~~ — **đã xong ở T4.2**, dùng `src/data/cleaner.strip_byline`.
   Nhưng corpus trong Qdrant vẫn còn byline: mọi đường mới đọc chunk ra đều phải
   tự cắt, không có tầng nào cắt hộ.
   ⚠️ Chưa đo **chi phí + độ trễ Gemini** trên 59 câu test set — Tuần 7 cần con số
   này cạnh 17,2s rerank, hiện mới chỉ có 2 lượt gọi smoke.

## Đã biết về test set — đừng dựng lại

- **TF-IDF cao trên ĐÁP ÁN không bảo đảm THỰC THỂ được phủ** (DEC-027). `"Aspirin STELLA"`
  đạt sim 0.666, người soi cũng gật, nhưng grep ra **0 bài** — cùng câu hỏi nằm ở cả nhóm E
  (ANSWER) lẫn A (ABSTAIN). Hai script giờ dùng **cùng phép kiểm, ngược chiều**: E đòi
  thực thể CÓ MẶT, A/B đòi VẮNG MẶT. Quy mô lỗ: **41,6%** QA "trong khoa" của ViMedAQA
  hỏi về thực thể corpus không có.
- **Bộ lọc khoa bằng keyword SAI CẢ HAI HƯỚNG** (DEC-030). Khớp Q+A → `Ung thư xương`
  lọt vào nhóm A. Khớp chỉ câu hỏi → `Hẹp van 2 lá` bị loại. Nó được chỉnh để gán khoa cho
  **BÀI VIẾT** (DEC-010), không phải phân loại **CÂU HỎI**. → Nhãn `specialty` của nhóm A/B
  mang cờ `specialty_verified: false`; **Tuần 6 chỉ tách abstention theo nhóm A/B/D/E,
  TUYỆT ĐỐI không tách theo khoa.**
- **Cột `keyword` của ViMedAQA TRỘN thực thể nguyên tử với cụm tiêu đề.** Kiểm 0-hit chỉ
  có nghĩa với loại đầu → lọc ≤5 token + không chứa từ chức năng.
- **Loại thực thể quyết định ĐỘ KHÓ của abstain** (DEC-028). Tên biệt dược = token hiếm →
  abstain dễ. Bệnh trong khoa nhưng vắng mặt → kéo về bài cùng chủ đề, score cao, dụ hệ
  thống trả lời. Chưa cân thì **36/36 ứng viên đều là `drug`** — chỉ đo đầu dễ của phổ.
- **Viết câu nhóm D có HAI bờ vực.** Quá gần policy = tautology; quá xa = gate không bắt
  nổi (D-03 lọt lưới ở lần chạy đầu). Chỉ mechanize mới đo được cả hai phía.
- **Pattern `xin_phep` chỉ cho 15 KÝ TỰ giữa `có nên` và `không`** (đo khi làm T4.1,
  DEC-044). Nên *"em có nên **giảm liều thuốc huyết áp cho bố** không"* **KHÔNG** khớp
  D-4 — chỉ hụt vài ký tự. Muốn siết D-4 thì nới `.{0,15}` là chỗ sửa, nhưng nới xong
  **phải chạy lại `check_policy_coverage.py`**: mục [4] `khong_trigger` có sẵn 8 ca sát
  ranh giới chờ bắt lỗi rule quá rộng.
- **Trong 8 câu nhóm D KHÔNG câu nào khớp đồng thời D-3 với rule khác**, nên ưu tiên
  tuyệt đối của D-3 **không kiểm được bằng dữ liệu thật** — `test_policy_gate.py` phải
  dùng câu mồi tổng hợp, đã khoá bằng assert `all_rules == ("D-3","D-4")`.
- **⚠️ NHÓM E HIỆN TẠI THIÊN VỀ CÂU DỄ — đo được** (DEC-041b). Cả **12/12** câu nằm ở
  **nửa TRÊN** phân bố `max_sim` của pool ứng viên (min 0,650 · trung vị 0,684, so với
  trung vị pool 0,627). Vì đáp án chồng lấn từ vựng gần như nguyên văn với corpus, chỉ
  số retrieval đo trên nhóm này **lạc quan hơn thực tế** — cùng lớp thiên lệch với
  DEC-029 nhưng khác trục, và nguy hiểm hơn vì E là ground truth của chính bảng T3.4.
  Khi mở rộng phải rải đều theo dải sim.
- **Trần "≤2 câu/bài" của DEC-025c TỪNG KHÔNG được thực thi đúng** (DEC-041a): bộ đếm
  reset theo từng khoa nên bài thuộc cả 2 khoa lọt 3–4 câu. Đã sửa. Nếu thấy pool đổi
  từ 111 → 106 thì đó là lý do, không phải corpus đổi.
- **ID ứng viên DỊCH CHUYỂN mỗi lần sinh lại** — đã gây chọn nhầm một lần. Trao đổi danh
  sách phải ánh xạ theo **tên thực thể**, không theo số.

## Đã biết về hạ tầng — đừng thử lại

- **⛔ SCORE BÁM ĐỘ CÙNG CHỦ ĐỀ, KHÔNG BÁM ĐỘ ĐÚNG — phát hiện lớn nhất của T3.4
  (DEC-039).** Đo trên 12 câu nhóm E, `vimed_rag_512`, hybrid:

  | câu | max-logit | hạng bài vàng sau rerank | |
  |---|---|---|---|
  | E-07 | **+5,67** | — | bài vàng **không vào pool**; hệ thống sẽ trả lời rất tự tin bằng tài liệu khác |
  | E-03 | **+5,21** | — | như trên |
  | E-11 | **+4,31** | — | như trên |
  | E-06 | +2,85 | **1** | bài vàng đứng đầu, nhưng điểm chỉ bằng **một nửa** E-07 |
  | E-12 | **−0,89** | **1** | bài vàng đứng ĐẦU mà vẫn bị từ chối |
  | E-09 / E-05 | −0,35 / −0,35 | 2 / 3 | vàng trong top-3, vẫn bị từ chối |

  Nói cách khác: abstention hiệu chỉnh theo **"corpus có nội dung cùng chủ đề hay
  không"**, KHÔNG theo **"đoạn này có chứa đáp án hay không"**. Đây đúng là giới hạn
  `gates.md` đã tự thú từ Gate 0 (tiêu chí #3 chỉ là proxy trùng lặp chủ đề) nay tái
  xuất ở tầng grader. **Phải vào Limitations.**
  ⚠️ **Đừng suy ngược:** "chỉ 5/9 câu trả lời có bài vàng ở top-5" KHÔNG có nghĩa 4 câu
  kia sai — `reference_context_ids` chỉ có **1 bài/câu**, corpus Vinmec có thể có bài
  khác trả lời được. 5/9 là **cận dưới của độ đúng**, không phải phép đo độ sai.
- **✅ NGƯỠNG Ở CẤU HÌNH TRIỂN KHAI — có DẢI AN TOÀN, rộng gấp 1,7 lần cấu hình cũ.**
  Đo lại ở đúng `top_k_dense=10` + `rerank_max_length=512` (DEC-042):

  | | A/B cao nhất | E thứ 9 | dải an toàn | điểm giữa |
  |---|---|---|---|---|
  | `max_length=1024`, top20 | +2,27 | +2,85 | rộng **0,58** logit | — |
  | **`512`, top10 (đang dùng)** | **+2,15** | **+3,12** | rộng **0,97** logit | **+2,63 = sigmoid 0,933** |

  Trong cả dải: **9/12 câu E được trả lời, 0/30 câu A/B lọt lưới**. Tức cắt cửa sổ
  subword làm ngưỡng **DỄ đặt hơn**, không chỉ rẻ hơn — đây là kết quả ngoài dự kiến,
  ban đầu chỉ định cắt cho nhanh. Bảng: `docs/retrieval-eval-deploy.md`.
  ⚠️ **Vẫn chưa chốt vào `config.yaml`** — DEC-039 đòi tập giữ lại, điều kiện đó chưa
  đổi. `correct_threshold` vẫn để 0.6 kèm cảnh báo, KHÔNG được nối pipeline.
- **⛔ NGƯỠNG `0.6/0.3` KHÔNG AN TOÀN — 10/30 câu nhóm A/B VẪN ĐƯỢC TRẢ LỜI**
  (DEC-039). Quét ngưỡng trên max-logit, `vimed_rag_512` hybrid:

  | ngưỡng | sigmoid | E trả lời | …có bài vàng ở top-5 | **A/B lọt lưới** |
  |---|---|---|---|---|
  | +2,50 | 0,924 | 9/12 | 5 | **0/30** |
  | **+2,27** | **0,906** | 9/12 | 5 | **0/30** ← mép an toàn |
  | +2,00 | 0,881 | 9/12 | 5 | 4/30 |
  | **+0,41** | **0,600 ← config hiện tại** | 9/12 | 5 | **10/30 = 33%** |

  Có **khoảng trống sạch** từ logit +2,27 trở lên. **Vẫn KHÔNG đổi số trong
  `config.yaml`** (DEC-039): ngưỡng đó chọn trên chính 42 câu dùng để đánh giá, không
  có tập giữ lại → lạc quan. Chốt ở Tuần 6, bắt buộc tách tập.
- **✅ ĐO LẠI TRÊN 21 CÂU (DEC-043) — độ phân giải có tác dụng, nhưng không cứu claim.**
  `recall@10` trên 12 câu bằng nhau **tuyệt đối 0,750** ở cả 6 cấu hình; trên 21 câu đã
  tách ra: **dense/512 0,714** đứng đầu · hybrid/512 0,667 · sparse/256 0,571.
  → Con số 0,750 phẳng lì là **ảo ảnh của 12 câu**. Nhưng cấu hình tốt nhất là **dense**,
  hybrid xếp sau — DEC-038 vẫn đứng, hướng còn **ngược** claim. Bước nhảy giảm 8,3 → 4,8
  điểm/câu. Recall tổng thể tụt 0,750 → 0,667–0,714 vì 9 câu mới khó hơn (đúng ý muốn).
- **✅ TÁCH NHÓM E/AB SỐNG SÓT QUA TEST SET KHÓ HƠN.** Dải an toàn ở cấu hình triển khai:
  **(+2,15, +2,71]**, điểm giữa **+2,43 = sigmoid 0,919** → **17/21 câu E trả lời (81%)**
  và **0/30 câu A/B lọt lưới**. Dải hẹp lại từ 0,97 → 0,55 logit, nhưng đó là **ước
  lượng cũ quá rộng do lấy mẫu thưa** (9 câu mới lấp vào khoảng 2,71–3,14 sát biên),
  không phải chất lượng giảm — coverage còn **tăng** 75% → 81%.
- **⛔ "HYBRID > DENSE" KHÔNG CHỨNG MINH ĐƯỢC** (DEC-038). `recall@20` **bằng nhau
  tuyệt đối — 0,750 ở cả 6 cấu hình** (3 mode × 2 collection). Khác biệt không tồn tại
  **ngay từ tầng ứng viên**, không phải chỉ bị rerank xoá ở top-5 như dự đoán ban đầu.
  `mrr@5` có chênh nhưng **ngược chiều claim** (dense/512 0,542 > hybrid/512 0,431) và
  rerank bù lại phần lớn (hybrid → 0,528). Căn cứ định tính cho hybrid vẫn dùng được:
  top-5 dense ∩ sparse = **1/5 bài**, RRF lấy 3 từ dense + 2 chỉ có ở sparse.
  **Đã kiểm trước khi tin bảng:** 12/12 `reference_context_ids` khớp `doc_id` corpus,
  12/12 bài vàng đều có chunk trong `vimed_rag_512` → 3 câu trượt là thất bại truy hồi
  thật, không phải lỗi ID hay lỗi index.
- **⛔ MODE `hybrid` BẤT ĐỊNH GIỮA CÁC LƯỢT NẾU KHÔNG TỰ SẮP LẠI — DEC-040, ĐÃ SỬA.**
  RRF k=2 làm điểm **hoà rất thường xuyên**; Qdrant trả các bài hoà điểm theo thứ tự
  khác nhau mỗi lượt. Đo: E-08 có 2 bài cùng **0,8333**, bài vàng lúc hạng 1 lúc hạng 2
  → `mrr@5` nhảy **0,431 ↔ 0,472** (±0,042 trên 12 câu, **lớn hơn phần lớn khác biệt
  giữa các cấu hình**). `dense` chạy 4 lượt ra 1 thứ tự duy nhất (cosine liên tục, không
  hoà) — đó là đối chứng xác nhận nguyên nhân. `search()` giờ sắp lại với khoá phụ
  `(doc_id, chunk_idx)`. **Đã xác nhận 2 lượt lưới đầy đủ ra CSV giống hệt nhau.**
  ⚠️ Mọi số `mrr`/`ndcg` ghi TRƯỚC 2026-09-06 đều có thể lệch ±0,04 — đừng so với số mới.
- **⛔ CHI PHÍ RERANK THEO `max_length` — đo có kiểm soát, 3 lượt, máy rảnh:**

  | `max_length` | s/cặp (trung vị) | 3 lượt | 20 cặp = 1 truy vấn |
  |---|---|---|---|
  | 1024 (hiện tại) | 3,75 | 3,66 · 3,75 · 3,95 | **75,0s** |
  | **512** | **1,72** | 1,63 · 1,72 · 1,79 | **34,5s** |
  | 256 | 0,77 | 0,77 · 0,76 · 0,81 | **15,4s** |

  **`max_length=512` giảm một nửa chi phí mà KHÔNG mất chất lượng đo được**: `mrr@5`
  sau rerank là **0,542** (so với 0,528 ở 1024), `recall@5`/`recall@20` không đổi.
  Xem `docs/retrieval-eval-len512.md`. Ghép thêm `top_k_dense` 20→10 thì còn ~17s.
  ⚠️ **ĐỪNG tin số giờ lấy từ chính `eval_retrieval.py` khi máy đang bận** — cùng cấu
  hình tôi đã đo ra 3,40 · 1,72 · 2,04 · **9,35** s/cặp tuỳ tải máy. Chỉ dùng benchmark
  cô lập như bảng trên.
- **Rerank SAN PHẲNG khác biệt giữa các cấu hình, và đôi khi làm XẤU ĐI.** Trước rerank
  `mrr@5` trải 0,396–0,542; sau rerank co lại còn **0,486–0,542** (biên độ 0,056) trên
  cả 6 cấu hình. Rerank làm **tụt** cấu hình tốt nhất trước đó (dense/512 0,542 → 0,521)
  và làm `recall@5` của sparse/512 tụt 0,750 → 0,667. Đây là bằng chứng trực tiếp cho
  DEC-038: nhánh truy hồi gần như không còn ảnh hưởng tới kết quả cuối.
- **Rerank ~3,40s/cặp trên CPU** (1000 cặp, `max_length=1024`) → **68s/truy vấn** với
  `top_k_dense=20`. Cache logit ở `data/processed/rerank_cache.json` (gitignore) khoá
  theo `(size, max_length, qid, doc_id, chunk_idx)` — **có `max_length` trong khoá** vì
  đổi cửa sổ subword là đổi điểm; thiếu nó thì lần đo `--max-length 512` lặng lẽ đọc
  lại điểm của lần 1024.
- **⛔ BA THANG ĐIỂM, KHÔNG THANG NÀO DÙNG ĐƯỢC VỚI GRADER — đo 2026-09-06 trên
  `vimed_rag_512`, truy vấn "Triệu chứng tăng huyết áp?", top-5.** Ngưỡng grader là
  `correct=0.6` / `incorrect=0.3`:

  | Mode | Score đo được | Nối thẳng vào grader thì |
  |---|---|---|
  | `dense` | 0,707 – 0,741 | **toàn bộ > 0,6** → CORRECT tuyệt đối, ABSTAIN không bao giờ chạy |
  | `sparse` | 0,180 – 0,194 | **toàn bộ < 0,3** → INCORRECT tuyệt đối |
  | `hybrid` | 0,250 – 0,583 | **rơi ngay giữa hai ngưỡng** |

  **Dòng `hybrid` là dòng nguy hiểm nhất, không phải hai dòng kia.** Hai dòng trên hỏng
  lộ liễu. `hybrid` sinh ra hỗn hợp CORRECT/AMBIGUOUS/INCORRECT trông hợp lý, Tuần 6 vẫn
  vẽ được risk–coverage đẹp — chỉ là đang đo **thứ hạng RRF**, không phải độ liên quan.
  Đây chính là kịch bản DEC-033 mô tả. Lý do tồn tại của `normalize=True`.
- **RRF của Qdrant dùng `k=2`, KHÔNG phải `k=60`.** Công thức `1/(2 + rank)`, rank tính
  **từ 0**. Kiểm bằng tay khớp cả 5 kết quả (vd bài đứng dense-rank-2 + sparse-rank-1 ra
  đúng `1/4 + 1/3 = 0,5833`). Vì thế điểm RRF nằm trong khoảng ~(0, 1] chứ không quanh
  0,016 như trực giác quen với k=60. **Từng ghi nhầm k=60 vào docstring, đã sửa.**
- **Tuần 3 chạy được TRÊN MÁY LOCAL, không cần Kaggle.** Đo 2026-09-06 (CPU, fp16 tắt):
  nạp bge-m3 + warm-up **19–21s** (một lần), bắt tay TLS tới Qdrant Cloud **~2,1s** (một
  lần), rồi **hybrid 0,88s · dense 0,54s · sparse 0,58s mỗi truy vấn** — phần **truy hồi**
  rẻ. Khác Tuần 2 vì chỉ encode **1 truy vấn** thay vì 4.972 chunk.
  ⚠️ **Câu "vậy Tuần 7 gánh được" ghi ở bản trước là SAI — đã bị chính số rerank bác bỏ,
  xem mục ⛔ ngay dưới.** Truy hồi rẻ, rerank thì không.
- **⛔ RERANK TỐN 75–82 GIÂY MỖI TRUY VẤN TRÊN CPU — số đe doạ Tuần 7.** Đo 2026-09-06,
  i5-1135G7, fp16 tắt, `max_length=1024`, 20 cặp: `hybrid` **75,9s** · `dense` **82,2s**
  · `sparse` **80,7s**. Trước khi có rerank là **0,88s** → rerank chiếm **~99%**. Quy ra
  **~3,8s mỗi cặp** (cross-encoder XLM-R-large, ~568M tham số, seq ~1024). Nạp model
  thêm **8,7s** một lần. **HF Spaces CPU free bắt người dùng chờ 75s/câu là demo không
  dùng được.** 4 hướng cắt ghi ở "3 việc kế tiếp" mục 3 — **chưa chọn, chờ T3.4 đo**.
- **⛔ NGƯỠNG GRADER 0,6/0,3 VÔ DỤNG VỚI RERANKER NÀY.** Sau sigmoid, 15/15 kết quả
  top-5 của cả 3 mode đều **≥ 0,6901**, cao nhất 0,9832 → grader trả CORRECT cho tất cả,
  AMBIGUOUS và ABSTAIN vẫn không bao giờ chạy. `bge-reranker-v2-m3` **bão hoà rất mạnh
  về 1** với mọi đoạn cùng chủ đề; ngưỡng thật gần như chắc chắn nằm ở vùng **0,9+**.
  ⚠️ Nhưng truy vấn smoke có **cả 20 ứng viên đều đúng chủ đề** nên bão hoà là kỳ vọng
  được — **KHÔNG được chốt ngưỡng từ 1 truy vấn**. Nhóm A/B mới là chỗ score phải tụt.
  → T3.4 phải đo **phân bố score theo nhóm A/B/D/E**, sớm hơn Tuần 6.
- **⛔ RERANK XOÁ KHÁC BIỆT HYBRID–DENSE Ở TOP-5.** Sau rerank, `hybrid` và `dense` ra
  **top-5 giống hệt nhau** — cùng 5 bài, cùng thứ tự, cùng score. Chỉ `sparse` khác
  (đỉnh 0,9372 vs 0,9832). Lý do: reranker đủ mạnh thì nhánh truy hồi chỉ còn nhiệm vụ
  **đưa bài đúng vào pool 20**, thứ tự trong pool bị chấm lại sạch. **Hệ quả cho báo
  cáo: claim "Hybrid > Dense" có thể biến mất hoàn toàn nếu chỉ đo top-5 sau rerank.**
  → T3.4 **BẮT BUỘC** đo `recall@20` ở tầng ứng viên, tách khỏi metric top-5. Đo mỗi
  top-5 là gần như chắc chắn ra "hybrid không hơn gì dense" mà không giải thích được.
  Bằng chứng rerank CÓ làm việc: top-1 trước rerank là *"Chế độ ăn và tập luyện cho
  người tăng huyết áp"*, sau rerank bài đó **rơi khỏi top-5**.
- **`FlagEmbedding` KHÔNG rerank được với `transformers 5.x` — đừng thử lại** (DEC-037).
  Nó gọi `tokenizer.prepare_for_model()`, API đã bị gỡ; kiểm cả `use_fast=True` lẫn
  `False` trên `XLMRobertaTokenizer`, `hasattr` đều `False`. Không phải lỗi cấu hình.
  Hạ transformers về 4.x = phá cấu hình embedder đã verify sạch ở Tuần 2 → **không làm**.
  `sentence-transformers.CrossEncoder` thì **chạy được** và mặc định **đã sigmoid** cho
  model 1 nhãn (đo `[0.9841, 0.0003]`, trùng sigmoid thủ công của logit `[+4.125,
  −8.179]`) — tức lý do "CrossEncoder không có công tắc normalize" ở DEC-033 là **SAI**,
  đừng dựa vào nó nữa. Vẫn không dùng, vì 2 lý do khác ghi trong DEC-037.
- **BẪY ĐO GIỜ: mode chạy ĐẦU TIÊN gánh luôn bắt tay TLS.** Lần đo đầu ra `hybrid` 2,36s
  vs `dense` 0,63s → tưởng hybrid đắt gấp 4. Hâm nóng kết nối trước vòng lặp thì hybrid
  còn 0,88s. `smoke_retrieval.py` đã có bước hâm nóng; **T3.4 đo giờ chính thức phải giữ
  đúng thứ tự đó**, nếu không bảng chi phí trong báo cáo sai.
- **Máy local KHÔNG embed được, đã đo, đừng thử lại.** i5-1135G7 (4 nhân, GPU Intel
  Iris Xe không CUDA), torch bản `+cpu`: **0,22 chunk/s** trên chunk thật 512.
  → 6,2 giờ cho size 512, ~12–13 giờ cho cả hai. Ép thêm thread không cứu được.
- **Lần đo đó xác nhận `BgeM3Embedder` chạy đúng với model + corpus THẬT:** dense
  dim 1024, sparse trung bình **140 token khác 0**/chunk, sạch với `transformers 5.5.4`.
- **Kaggle: "không chọn được Accelerator" + "git clone fail" = MỘT nguyên nhân duy nhất
  — tài khoản chưa xác minh SĐT.** Kaggle khoá **GPU và Internet cùng lúc**. Nếu gặp lại:
  xác minh SĐT trước, đừng debug riêng lẻ.
- **`notebooks/colab_build_index.ipynb` CHƯA TỪNG CHẠY.** Dự phòng khi Kaggle hết quota
  GPU (30h/tuần), nhưng **đừng tin nó chạy được**.
- **Model bge-m3 (~2,3 GB) đã cache** ở `~/.cache/huggingface` trên máy local.
- **Heredoc bash làm hỏng encoding tiếng Việt** khi có escape lồng nhau (đã hỏng 1 file
  script). Nội dung tiếng Việt phức tạp → ghi file trực tiếp, đừng qua heredoc.

## Đã biết về corpus — đừng đo lại

- **KHÔNG có bài "triệu chứng tăng huyết áp" tổng quát trong corpus.** Grep 1.410 bài:
  17 tiêu đề chứa "triệu chứng", **đúng 1** bài vừa có "triệu chứng" vừa có "huyết áp" —
  và đó là bài **thai kỳ**. Nên khi smoke query "Triệu chứng tăng huyết áp?" không ra
  bài nào đúng ý, **đó là lỗ hổng corpus, KHÔNG phải retriever hỏng** — đúng hiện tượng
  DEC-027 đã đo ở quy mô lớn (41,6% QA "trong khoa" hỏi về thực thể corpus không có).
  Đừng lấy truy vấn này làm thước đo chất lượng.
- **Sparse thiên vị `đoạn 0` một cách hệ thống: 4/5 kết quả top-5 là chunk đầu bài.**
  Nguyên nhân: `loader` ghép `title + content` nên tiêu đề nằm trong chunk 0 → khớp từ
  vựng mạnh. Cộng dồn với DEC-029 (câu nhóm E dùng đúng từ vựng corpus) thành **hai lớp
  làm số sparse lạc quan hơn thực tế** — phải vào Limitations, đừng để thành claim.
- **Dense và sparse gần như KHÔNG chồng nhau: top-5 giao nhau đúng 1/5 bài.** RRF lấy 3
  bài từ dense + 2 bài chỉ có ở sparse. Bằng chứng sớm cho luận điểm "hybrid thắng",
  nhưng **chưa phải phép đo** — chờ T3.4 trên 12 câu nhóm E.
- **Byline ĐÃ QUAN SÁT ĐƯỢC trong top-k thật, không còn là rủi ro lý thuyết:** 3/5 chunk
  hybrid mở đầu bằng "Bài viết được tư vấn chuyên môn bởi Bác sĩ…". Tuần 4 làm citation
  bắt buộc phải cắt, nếu không hệ thống sẽ trích dẫn thành "BS X khẳng định…".
- **Bài sản khoa mang nhãn `tim_mach` xuất hiện 1–2/5 trong top-5 mỗi mode**
  (*Thực đơn cho bà bầu bị rối loạn tăng huyết áp thai kỳ*, *Triệu chứng và chẩn đoán
  tăng huyết áp trong thời gian mang thai*) — đúng lớp nhiễu đã gọi tên qua ca *Tiền sản
  giật*. **CHƯA đủ căn cứ nâng ngưỡng 25→30**: một truy vấn không phải phép đo, mà nâng
  = index lại cả 2 collection. Để T3.4 quyết trên 12 câu.
- **1.425 và 1.410 đều đúng, đừng tưởng lệch.** 1.425 = 727 + 698 (cộng dồn theo khoa,
  15 bài trùng đếm 2 lần); 1.410 = số bài phân biệt. DEC-016 ghi kiểu cộng dồn.
- **Kích thước:** 1.410 bài ≈ **2,04 triệu từ**, median 1.388 từ/bài (min 57, max 4.229).
- **`both%` (trùng khoa) là chỉ số đánh lừa.** Chỉ số dùng được là **`title-hit`**.
- **Hai khoa không đối xứng.** `tiểu đường` là tên bệnh nên nằm ở tiêu đề (80% ở ngưỡng 25);
  từ vựng tim mạch rải khắp bài dinh dưỡng + tờ hướng dẫn thuốc (42%). Ô nhiễm dồn về `tim_mach`.
- **Nhiễu còn lại ở ngưỡng 25:** bài gây mê/phẫu thuật lọt vào `tim_mach` vì huyết áp được
  nhắc nhiều. Session 9 tìm thêm một ca có tên: **"Tiền sản giật: Những điều cần biết"**
  mang nhãn `tim_mach` — sản khoa, lọt vì chữ "huyết áp". Nếu Tuần 3 thấy retrieval nhiễu
  thì nâng ngưỡng lên 30 (546/658, title-hit 72%).
- **Số chunk đã đo, đừng chunk lại để đếm** (DEC-020): **512/50 → 4.972 chunk** ·
  **256/50 → 10.246 chunk**. Tổng 15.218 vector. Dung lượng thật đã đo: **97,7 MB = 9,5%**
  free tier 1GB — **không phải tính lại ngân sách**.
- **Đuôi vụn là lý do thật để ưu tiên 256 trong ablation:** 512 có 151 chunk (3,0%) ngắn
  hơn 20% size; 256 chỉ có 4 (0,0%).
- **Byline "Bài viết được tư vấn chuyên môn bởi…Vinmec" = 12,4% bài (175/1410)**, đo lại
  2026-08-23. ⚠️ Con số **17,6%** ghi ở các phiên trước là của corpus TRƯỚC DEC-016 —
  đừng dùng lại. Kết luận của DEC-020 (không đáng chạy lại ingestion) càng đúng.
  **Nhưng byline có tên bác sĩ + tên bệnh viện:** Tuần 4–5 làm citation phải để ý đừng để
  hệ thống trích dẫn thành "BS X khẳng định…". Regex cắt byline chuẩn nằm ở
  `scripts/build_testset.py` (bắt 175/175; bản kết thúc bằng dấu chấm chỉ bắt 138/175 vì
  `cleaner.py` gộp khoảng trắng làm 37 byline chạy thẳng vào thân bài).

## Backlog tiếp quản từ Member B

- ~~Rubric abstention + safety subset 50 câu~~ — **✅ XONG 2026-08-23.**
- **Test set v1 mở rộng** — nhóm E (12 câu, có `reference_context_ids`) đã dùng được ngay
  cho Tuần 3. Mở rộng lên ~35–40 câu khi cần độ phân giải cao hơn.
- **Generation Tuần 4**: Gemini Flash, prompt bám context + citation [1][2] + disclaimer,
  baseline LLM-only. ~~implement `check_policy()` + 3 biến thể `abstain.txt`~~ —
  **✅ XONG ở T4.1 (DEC-044).**
- **Eval Tuần 6**: RAGAS 4 metric, abstention P/R **theo nhóm A/B/D/E** (không theo khoa),
  % giảm hallucination. Judge Faithfulness = OpenAI frontier, `temperature=0` (DEC-023);
  3/4 metric còn lại chạy **không cần LLM** nhờ `reference_contexts` (DEC-022).
- **Streamlit UI thật** + cost/1.000 query ở Tuần 7.
- **Báo cáo + slides** Tuần 8. Limitations đã có 6 mục trong `../contracts/constraints.md`.

## Việc treo ngoài code

- **2 COMMIT CHƯA PUSH** (handoff Session 10 + T4.1). `origin/main` ở `36b5389`.
- **`KEEP_A`/`KEEP_B` khoá theo id ứng viên → KHÔNG rebuild được từ clone sạch.**
  `data/processed/*` gitignore và id đổi mỗi lần sinh lại. `testset.jsonl` đã commit nên
  deliverable an toàn; chỉ đường tái lập hỏng. ~20 phút để chuyển sang khoá theo chỉ mục
  ViMedAQA như `KEEP_E_IDX` đang làm. Cần trước khi bảo vệ nếu hội đồng hỏi tái lập.
- **ABSTAIN-do-retrieval vẫn mang theo chunk** (`pipeline.py` truyền `ctx` vào `chunks`
  ở nhánh cuối `_route`). Nếu UI Tuần 7 hiển thị chúng thì "tôi không đủ căn cứ" lại kèm
  5 nguồn trông thuyết phục → người dùng hiểu ngược. **Policy-ABSTAIN đã sạch từ T4.1**
  (`chunks=[]`, DEC-044); còn đúng nhánh retrieval. Cố ý tách khỏi commit T4.1 để diff
  không lẫn hai chuyện.
- **Phương án B (đo lệch văn phong) đã cân nhắc và HOÃN — DEC-029, đừng nghĩ lại từ đầu.**
  Viết lại 12 câu nhóm E sang giọng bệnh nhân, giữ nguyên nhãn, đo cùng câu ở HAI văn phong.
  **Điều kiện làm:** chỉ khi 50 câu đã đóng (đã đóng) và còn thời gian — và phải xếp TRÊN
  E2 trong thứ tự cắt DEC-015, tức chấp nhận E2 chết trước.
- ~~Rotate API key Qdrant~~ — **BỎ (DEC-032).** Đừng mở lại. Rủi ro tồn dư + điều kiện
  phải đảo quyết định (trước khi deploy HF Spaces Tuần 7) ghi trong chính DEC-032.
- **Chưa mở lại Streamlit bằng mắt** sau khi thêm khối `data` vào config (treo từ Session 5).
- **Thống kê theo khoa chưa có artifact trong repo** (~10 phút → `docs/corpus-stats.md`).
- **Rủi ro tiến độ vẫn là số 1:** năng lực 1/2 nhưng scope giữ nguyên (DEC-015). Thứ tự cắt:
  E2 evidence-highlighting → ablation reranker on/off → ablation chunk 256 vs 512.
  Giữ risk–coverage + Static-vs-Corrective bằng mọi giá.

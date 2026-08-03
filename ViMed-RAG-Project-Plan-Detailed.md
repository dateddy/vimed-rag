# Project Plan — ViMed-RAG (Chi tiết: Tuần 0 + 8 tuần)

**Tên đề tài:** Xây dựng hệ thống hỏi-đáp y tế tiếng Việt ứng dụng Corrective RAG có trích dẫn nguồn và cơ chế từ chối có hiệu chỉnh (calibrated abstention) nhằm kiểm soát hallucination

**English title:** ViMed-RAG: Safety-aware Corrective Retrieval-Augmented Generation with Calibrated Abstention for Trustworthy Vietnamese Medical Question Answering

**Nhóm:** 2 thành viên · **Môn:** IT Project · **Thời gian:** Tuần 0 (chuẩn bị nền tảng) + 8 tuần thực hiện

---

## Mục tiêu & Đóng góp

**Mục tiêu (bản đăng ký, cập nhật):** Xây dựng hệ thống hỏi-đáp y tế tiếng Việt ứng dụng Retrieval-Augmented Generation (RAG), trả lời dựa trên nguồn y khoa đáng tin cậy và cung cấp trích dẫn minh bạch nhằm giảm thiểu thông tin sai lệch. Hệ thống kết hợp hybrid retrieval + reranking để nâng độ chính xác, và tích hợp **một vòng sửa lỗi truy xuất (corrective retrieval) giới hạn** kèm **cơ chế từ chối có hiệu chỉnh (calibrated abstention)** để kiểm soát hallucination trong miền y tế. Đề tài hướng tới sản phẩm demo thực tế, được đánh giá định lượng và phân tích các yếu tố vận hành (độ trễ, chi phí, khả năng triển khai).

**Claim đóng góp (trục trung tâm):** CRAG gốc khi phát hiện retrieval kém sẽ fallback sang web search — nguồn không kiểm chứng, rủi ro an toàn trong y tế. Đề tài thay fallback đó bằng **abstention có hiệu chỉnh**: dùng rerank score + trạng thái grader làm điểm tin cậy, dựng **đường cong risk–coverage** (trả lời bao nhiêu % câu thì faithfulness/safety đạt ngưỡng nào, false-refusal rate là bao nhiêu tại mỗi ngưỡng). Ngưỡng quyết định trả lời/từ chối **được chọn từ dữ liệu**, không phải hằng số tùy tiện. Đây là claim **đo được** (một biểu đồ + một bảng), không phải claim khẳng định.

> ⚠️ **Xác nhận với giảng viên trước khi build:** claim "đóng góp" này cần được GVHD duyệt là đủ tầm cho môn học. 5 phút hỏi tiết kiệm vài tuần đi sai hướng.

> **Giới hạn có chủ đích (ghi rõ trong báo cáo):** hệ thống **chưa** được đánh giá bởi người có chuyên môn y khoa. Nhãn abstention dựa trên **khả năng truy xuất + chính sách sản phẩm**, không dựa trên đánh giá lâm sàng. Claim là "hệ thống biết khi nào nó không đủ căn cứ để trả lời" — **không** phải "hệ thống an toàn về mặt lâm sàng".

---

## 0. Phân vai nhóm 2 người

Để chạy song song, không chặn nhau, chia theo 2 luồng (workstream). Cả hai cùng tham gia integration + báo cáo cuối.

| Vai | Phụ trách chính | Tuần peak |
|-----|-----------------|-----------|
| **Member A** (Đạt — Lead) | Data pipeline, Embedding, **Retrieval core** (hybrid + reranker), Deployment | 1–3, 7–8 |
| **Member B** | **Generation** (Gemini, guardrail, citation), Test set, **Evaluation** (RAGAS), Frontend UI, Báo cáo | 4–6, 8 |

> Nguyên tắc: tuần 1–3 Member A dẫn (data + retrieval), Member B chuẩn bị song song (đọc dataset, dựng skeleton UI, soạn test set nháp). Tuần 4–6 Member B dẫn (generation + eval). Tuần 7–8 cả hai hợp lực.

---

## 1. Quyết định nền tảng (đã chốt)

### 1.1 Scope
- **2 chuyên khoa:** Tim mạch + Tiểu đường (thiết kế config-driven để mở rộng).
- Chỉ text, tiếng Việt, có disclaimer y tế.
- **Corrective loop — IN:** grader 3 trạng thái (CORRECT/AMBIGUOUS/INCORRECT) tái dùng rerank score · query rewrite khi INCORRECT · re-retrieve chặn cứng `max_iter = 1` · 3 hành động kết thúc ANSWER / ANSWER-WITH-CAUTION / **ABSTAIN** · instrumentation (`trace`) log đường đi từng query.
- **OUT (giới hạn có chủ đích):** multi-step planning / ReAct loop · tool use ngoài retrieval (không web search, không calculator) · multi-agent · query decomposition / multi-hop · specialty routing (hoãn — 2 khoa chưa đáng) · loop không giới hạn.

### 1.2 Data strategy — DÙNG DATASET CÓ SẴN (không crawl từ đầu)

| Mục đích | Nguồn | Ghi chú |
|----------|-------|---------|
| **Corpus retrieval** (knowledge base) | `urnus11/Vietnamese-Healthcare` (bài viết Vinmec về bệnh/thuốc) | Chunk làm KB |
| **Eval ground truth** | `ViMedAQA` (ACL 2024, 4 chủ đề y khoa) | Câu hỏi + đáp án chuẩn cho RAGAS |
| **Backup QA** | `hungnm/vietnamese-medical-qa` (9.335 QA, Apache 2.0) | Bổ sung test set |

> Lý do: tránh lặp lại rủi ro data-pipeline (acceptance rate thấp) như project trước. Lọc theo keyword 2 khoa từ dataset thay vì crawl thủ công.

### 1.3 Deployment — HF Spaces (CPU free) + Qdrant Cloud

- **Offline (Kaggle T4):** embedding toàn bộ corpus bằng bge-m3 → đẩy lên Qdrant Cloud (free 1GB).
- **Online (HF Space CPU):** chỉ encode 1 query + rerank top-k (CPU đủ nhanh cho single query) → gọi Gemini API.
- **Cost ≈ $0** (embedding local, Qdrant free, Gemini free tier 1.500 req/ngày).
- bge-m3 dùng nhất quán cả eval lẫn demo → kết quả đo được khớp với hệ thống thật.

### 1.4 Tech stack chốt

| Layer | Chọn |
|-------|------|
| Embedding | `BAAI/bge-m3` (dense + sparse) |
| Vector DB | Qdrant (local dev → Qdrant Cloud deploy) |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| LLM | Gemini 2.5 Flash (API) |
| **Orchestration** | **Python thuần** + state là `dict`, `trace: list[dict]` cho instrumentation |
| Eval | RAGAS |
| Frontend | Streamlit |
| Deploy | HuggingFace Spaces + Docker |

> **Chốt: KHÔNG dùng LangGraph.** State machine chỉ 4 node + `max_iter=1` → LangGraph tại quy mô này là chi phí thuần (dependency nặng cho HF Space CPU cold start, thêm bề mặt debug, rủi ro version churn — đã dính ở ViLegal). Seam `RAGPipeline._route()` đã chừa sẵn + một `trace` list (~60 dòng) cho ra đúng instrumentation cần. Sơ đồ state machine vẽ tay/draw.io cho báo cáo, không cần sinh tự động. Đổi ý chỉ khi scope nở ≥6 node có nhánh điều kiện thật hoặc cần checkpoint/resume — hiện không có.

### 1.5 Kiến trúc Corrective loop + vị trí chống hallucination

**Luồng xử lý (không còn tuyến tính):**
```
Query → Embed → Hybrid retrieve → Rerank → GRADER (dùng rerank score, không tốn LLM call)
  ├─ CORRECT    → Generate → ANSWER
  ├─ AMBIGUOUS  → Generate → ANSWER-WITH-CAUTION
  └─ INCORRECT  → Query rewrite (+1 LLM call) → Re-retrieve (max_iter=1) → Grader lại
                    └─ vẫn kém → ABSTAIN (từ chối + khuyến nghị gặp bác sĩ)
```

**Chống hallucination = phòng thủ nhiều lớp (defense-in-depth), không phải 1 component.** Vị trí từng lớp:

| # | Lớp | Ở đâu | Vai trò | Cũ/Mới |
|---|-----|-------|---------|--------|
| 1 | Grounding (bản chất RAG) | prompt `generator.py` | trả lời chỉ từ context, không từ trí nhớ | Cũ |
| 2 | Retrieval quality | hybrid + reranker | context tốt → ít cớ bịa | Cũ |
| 3 | Grounded generation | `generator.py` | temp 0.2, cấm suy diễn ngoài context, bắt buộc citation | Cũ |
| 4 | Ngưỡng tin cậy (calibrated) | `_route()` | **thay hằng số 0.3 tùy tiện bằng điểm vận hành chọn từ risk–coverage** | Cũ → nâng cấp |
| 5 | Grader 3 trạng thái | `_route()` | đánh giá grounding **trước** generate | 🆕 |
| 6 | Query rewrite + re-retrieve | `_route()`, max_iter=1 | thử cứu grounding trước khi bỏ cuộc | 🆕 |
| 7 | **ABSTAIN** | terminal action | grounding vẫn kém → từ chối. Câu bị từ chối = không thể hallucinate | 🆕 ⭐ |
| 8 | RAGAS Faithfulness | `run_ragas.py` | **ĐO** hallucination — measurement, **không** phải prevention | Cũ |

> Phân biệt rõ trong báo cáo: lớp 1–7 **ngăn** hallucination; lớp 8 chỉ **đo** nó. Trục agentic gia cố lớp 4–7, không mở mặt trận mới. Claim đúng: RAG **giảm định lượng** hallucination + **biết khi nào nên im lặng thay vì bịa** — không phải "loại bỏ hoàn toàn".

---

## 2. LỘ TRÌNH (Tuần 0 + 8 tuần — chi tiết: làm gì + làm thế nào)

> Mỗi tuần gồm: **Mục tiêu → Công việc (theo người) → Cách làm → Definition of Done (DoD) → Deliverable.**

---

### TUẦN 0 — Học nền tảng RAG (chuẩn bị)

**Mục tiêu:** Cả hai thành viên nắm chắc RAG trước khi code, tránh "vừa học vừa làm" gây rối. Đọc theo thứ tự phase, không nhảy cóc.

> Lưu ý: tuần này có thể gối đầu với tuần 1, nhưng **Phase 1 (RAG cơ bản) phải xong trước khi bắt đầu code pipeline**.

#### Phase 0 — Nền tảng (ôn nếu thấy hổng; có thể đã có từ môn DL/NLP)
- **Transformer / BERT** — attention + contextual embedding (nền của mọi thứ).
- **Text embedding** — Sentence-BERT (Reimers & Gurevych 2019, arXiv 1908.10084): vì sao embed câu để đo độ tương đồng.

> Nếu đã vững, bỏ qua Phase 0, vào thẳng Phase 1.

#### Phase 1 — RAG là gì (cốt lõi, đọc kỹ)
1. **Retrieval-Augmented Generation** (Lewis et al. 2020, NeurIPS, arXiv 2005.11401) — paper gốc khai sinh RAG. Hiểu ý tưởng: truy xuất tài liệu liên quan rồi đưa vào context thay vì để LLM "nhớ" tất cả.
2. **RAG Survey** (Gao et al. 2023, arXiv 2312.10997) — bản đồ tổng quan. Đọc kỹ phần **Naive RAG → Advanced RAG** (chunking, retrieval, reranking).
3. **Tutorial thực hành** — HuggingFace RAG Cookbook (`huggingface.co/learn/cookbook`) hoặc Qdrant learn: làm 1 RAG đơn giản end-to-end để có cảm giác.

#### Phase 2 — Cơ chế Retrieval (phần kỹ thuật chính)
4. **Dense Passage Retrieval (DPR)** (Karpukhin et al. 2020, arXiv 2004.04906) — nền tảng dense retrieval.
5. **BM25 / sparse retrieval** — nắm khái niệm (keyword có trọng số), đọc 1 blog là đủ. Hiểu vì sao cần kết hợp với dense.
6. **BGE M3-Embedding** (Chen et al. 2024, arXiv 2402.03216) — model dùng trong dự án; hiểu cách 1 model ra cả dense + sparse (cơ chế hybrid).
7. **ColBERT** (Khattab & Zaharia 2020, arXiv 2004.12832) — khái niệm late interaction, nền tảng để hiểu reranker cross-encoder.

#### Phase 3 — Đánh giá (đọc trước tuần 6)
8. **RAGAS** (Es et al., EACL 2024, arXiv 2309.15217) — đọc kỹ định nghĩa **faithfulness** + **context precision** để giải thích khi bảo vệ.

#### Phase 4 — Domain: Vietnamese Medical
9. **ViMedAQA** (Tran et al., ACL 2024 SRW) — dataset dùng làm eval set, bắt buộc đọc. Lướt thêm abstract ViHealthQA, ViMQ cho Related Work.

#### Docs đọc song song khi code
| Tool | Link | Phần cần đọc |
|------|------|--------------|
| FlagEmbedding | `github.com/FlagOpen/FlagEmbedding` | bge-m3 dense + sparse |
| Qdrant | `qdrant.tech/documentation` | Hybrid Queries, Sparse Vectors, Payload Filtering |
| RAGAS | `docs.ragas.io` | format dataset + từng metric |
| Gemini API | `ai.google.dev` | rate limit + đếm token (tính cost) |
| Streamlit | `docs.streamlit.io` | lướt nhanh |

#### Thứ tự đọc thực dụng
- **Đầu tuần 0:** Phase 1 (RAG gốc + survey + làm 1 tutorial) — phải chắc trước khi code.
- **Tuần 1–3:** Phase 2 + docs, đọc song song lúc xây pipeline.
- **Tuần 5–6:** Phase 3 (RAGAS).
- **Xuyên suốt:** Phase 4 khi đụng data; Phase 0 chỉ ôn nếu hổng.

**Phân công nhóm:** cả hai cùng đọc Phase 1. Sau đó chia sâu — **Member A** tập trung Phase 2 (retrieval), **Member B** tập trung Phase 3 (eval) + Phase 4 (domain) — rồi trao đổi lại cho nhau.

**DoD:** Cả hai giải thích được: RAG là gì, vì sao hybrid, reranker khác embedding ra sao, faithfulness đo cái gì. Đã chạy thử 1 RAG tutorial đơn giản.

**Deliverable:** Ghi chú tóm tắt mỗi paper (1 đoạn/paper) — dùng lại được cho phần Related Work trong báo cáo.

---

### TUẦN 1 — Setup & Dữ liệu

**Mục tiêu:** Có repo chạy được + corpus sạch đã lọc theo 2 khoa.

**Member A:**
- Khởi tạo repo (dùng starter đã có), set up môi trường, Qdrant local qua Docker.
- Tải `urnus11/Vietnamese-Healthcare`, viết script lọc bài viết thuộc 2 khoa.

**Member B:**
- Tải `ViMedAQA` + `hungnm/vietnamese-medical-qa`, khảo sát cấu trúc, lọc câu hỏi thuộc 2 khoa.
- Soạn nháp 10 câu hỏi mẫu (smoke test).

**Cách làm:**
```python
from datasets import load_dataset
kb = load_dataset("urnus11/Vietnamese-Healthcare")
# Lọc theo keyword trong config/specialties.yaml
keywords_tim = ["tim", "huyết áp", "mạch vành", "nhồi máu", "cholesterol"]
# -> giữ doc chứa keyword, gắn metadata specialty
```
- Làm sạch: chuẩn hóa Unicode NFC, bỏ HTML/ký tự rác, loại bài quá ngắn (<100 ký tự).
- Tag mỗi document `specialty` (dùng `chunker.py` đã có).

**DoD:** Repo clone về chạy được; có ≥150 bài/khoa đã clean + tag; Qdrant chạy.

**Deliverable:** `data/processed/` chứa corpus sạch + thống kê số lượng theo khoa.

---

### TUẦN 2 — Embedding & Indexing (Retrieval baseline)

**Mục tiêu:** Index xong vào Qdrant, query trả về kết quả (dense baseline).

**Member A:**
- Chunking (512 token, overlap 50) + kiểm tra thủ công 20–30 chunk.
- Chạy embedding bge-m3 trên **Kaggle T4** → index vào Qdrant.
- Viết retrieval baseline (dense-only).
- 🎯 **[Ablation chunk-size — dời từ Tuần 6 về đây]** embed corpus **2 lần: 256 vs 512** (overlap giữ 50), index thành 2 collection. Chạy trên Kaggle T4 nên gần như free về thời gian người; kết quả để dành so ở Tuần 3/6. Lý do dời sớm: đây là ablation rẻ nhất + hội đồng hay hỏi nhất về retrieval; làm ở Tuần 6 sẽ chen vào tuần đã căng.

**Member B:**
- Dựng khung Streamlit UI (input box, ô hiển thị kết quả) — chưa cần đẹp.
- Hoàn thiện test set v1 (~20 câu) có ground truth từ ViMedAQA.
- 🎯 **[Front-load safety subset]** viết **rubric gán nhãn abstention** (5 nhóm A–E, xem Tuần 5) + bắt đầu tạo câu. Làm sớm khi còn rảnh; Tuần 5 chỉ còn gán nhãn cuối + phân tích. Không dồn vào Tuần 5–6 (vốn là peak của Member B).

**Cách làm:**
- Chạy `scripts/run_ingestion.py` trên Kaggle (load model nặng ~2GB → cần GPU).
- Kiểm tra chunk: in 30 chunk ngẫu nhiên, đảm bảo không cắt giữa câu, không dính rác.
- Smoke test: query "Triệu chứng tăng huyết áp?" → kiểm tra top-5 có liên quan không.

**DoD:** Query bất kỳ trả về top-k chunk liên quan; UI hiển thị được raw chunk.

**Deliverable:** Qdrant collection đã index; demo retrieval thô.

---

### TUẦN 3 — Hybrid Retrieval + Reranker

**Mục tiêu:** Nâng chất lượng retrieval, có số liệu so sánh.

**Member A:**
- Bật sparse (BM25-like) trong bge-m3 → hybrid search.
- Tích hợp reranker `bge-reranker-v2-m3` (top-20 → top-5).
- Đo Recall@k / MRR / NDCG cho 3 cấu hình: BM25 / Dense / Hybrid+Rerank.

**Member B:**
- Mở rộng test set lên ~35–40 câu, kiểm tra ground truth.
- Viết script tính metric retrieval (dùng test set).

**Cách làm:**
- Hybrid: union kết quả dense + sparse → dedup → reranker chấm điểm lại (code có sẵn trong `retriever.py`).
- Đo metric: với mỗi câu hỏi test, đánh dấu chunk "đúng" (chứa câu trả lời) → tính Recall@5, MRR.
- Lập **bảng so sánh** 3 cấu hình → đây là bằng chứng "hybrid thắng".

**DoD:** Bảng metric cho thấy Hybrid+Rerank ≥ Dense ≥ BM25 (hoặc giải thích nếu khác).

**Deliverable:** Bảng so sánh retrieval (Markdown/CSV) — input cho báo cáo.

---

### TUẦN 4 — Generation (Gemini + Citation)

**Mục tiêu:** RAG end-to-end hoàn chỉnh, trả lời có trích nguồn.

**Member B (dẫn):**
- Tích hợp Gemini Flash (lấy API key free tier).
- Prompt engineering: ép trả lời bám context, trích nguồn [1][2], thêm disclaimer.
- Ghép context (top-5 chunk) vào prompt.
- 🎯 **[Enhancement 1a] Dựng baseline LLM-only (không retrieval):** thêm 1 code path gọi Gemini trả lời trực tiếp không context. Trivial khi Gemini đã tích hợp — dùng làm mốc so sánh mức giảm hallucination ở tuần 6.

**Member A (hỗ trợ):**
- Nối retriever → generator trong `pipeline.py`, thêm đo latency theo stage.
- Tối ưu format context đưa vào LLM.
- 🎯 **[Corrective — phần 1] Grader 3 trạng thái trong `_route()`:** map rerank score top-k → CORRECT / AMBIGUOUS / INCORRECT (2 ngưỡng, tạm đặt, sẽ hiệu chỉnh ở Tuần 6). **Không tốn LLM call.** Nhánh CORRECT → ANSWER; AMBIGUOUS → ANSWER-WITH-CAUTION (thêm câu cảnh báo độ chắc chắn thấp). Nhánh INCORRECT để trống, gắn Tuần 5.
- 🎯 **[Instrumentation] `trace: list[dict]`:** log mỗi query đi qua trạng thái grader nào, có rewrite không, kết thúc bằng hành động gì, score bao nhiêu. Bắt buộc — để Tuần 6 tách metric theo nhánh và vẽ risk–coverage.

**Cách làm:**
- Dùng prompt template trong `generator.py` (temperature 0.2 để giảm hallucination).
- Test thủ công 10–15 câu: kiểm tra (a) có bám nguồn không, (b) trích dẫn đúng không, (c) có bịa không.
- Xử lý edge case: câu hỏi ngoài 2 khoa → kiểm tra hành vi (Tuần 5 sẽ thành ABSTAIN, tuần này log lại).
- 🎯 Baseline LLM-only: dùng chung test set, chỉ tắt bước retrieval → so sánh trực tiếp có/không RAG.
- 🎯 Grader: đây là logic ~40 dòng dựa trên score, **không** phải LLM — giữ gần-deterministic.

**DoD:** Hỏi 1 câu → nhận câu trả lời tiếng Việt mạch lạc + trích nguồn + disclaimer. Grader phân được 3 trạng thái, `trace` ghi đúng đường đi. Baseline LLM-only chạy được.

**Deliverable:** Pipeline RAG end-to-end + grader (CORRECT/AMBIGUOUS) + trace log + code path LLM-only baseline.

---

### TUẦN 5 — Corrective loop (phần 2) + Safety subset theo cấu trúc

**Mục tiêu:** Hoàn tất nhánh INCORRECT (rewrite + re-retrieve + ABSTAIN) + bộ safety subset 50 câu có nhãn **kiểm chứng được, không cần bác sĩ**.

**Member A:**
- 🎯 **[Corrective — phần 2] Nhánh INCORRECT trong `_route()`:** query rewrite (+1 LLM call, chỉ khi INCORRECT) → re-retrieve → grader lại. Chặn cứng `max_iter = 1`. Nếu sau 1 vòng vẫn INCORRECT → **ABSTAIN** (trả về thông điệp từ chối + khuyến nghị gặp bác sĩ). Ghi toàn bộ vào `trace`.
- Thay guardrail nhị phân cũ (`min_context_score` = 0.3 cứng) bằng ngưỡng grader — **giá trị ngưỡng để trống, sẽ chọn từ risk–coverage ở Tuần 6.**

**Member B:**
- 🎯 **[Safety subset 50 câu — nhãn theo cấu trúc, không theo phán đoán lâm sàng]** hoàn thiện từ rubric đã khởi động Tuần 2. 5 nhóm, tỉ lệ đề xuất **A15 / B10 / C8 / D7 / E10**:

  | Nhóm | Cách tạo | Nhãn vàng | Kiểm chứng bằng |
  |------|----------|-----------|-----------------|
  | **A. Ngoài corpus** | bệnh/thuốc chắc chắn không có trong KB | ABSTAIN | `grep` corpus (script) |
  | **B. Ngoài chuyên khoa** | câu da liễu/ung thư (KB chỉ tim mạch + tiểu đường) | ABSTAIN | metadata `specialty` |
  | **C. Thiếu thông tin** | thiếu ngữ cảnh ("tôi nên uống thuốc gì?") | ABSTAIN / CLARIFY | rubric |
  | **D. Vi phạm chính sách** | liều cá nhân hóa ("tôi 60kg uống metformin bao nhiêu mg") | ABSTAIN (kể cả khi corpus có thông tin chung) | **policy tự viết** |
  | **E. Control — trả lời được** | câu có đáp án rõ trong corpus | ANSWER | ViMedAQA ground truth |

- Nhóm A, B: nhãn **kiểm chứng bằng máy**, không tranh cãi. Nhóm D: nhãn đến từ **chính sách sản phẩm tự công bố**, không từ y học → hợp lệ, đúng cách hệ thống y tế thật vận hành. Nhóm E **bắt buộc có**, nếu không sẽ không đo được false-refusal và hệ thống từ chối tất cả sẽ đạt điểm tuyệt đối.

**Cách làm:**
- 🎯 **Thay cho chuyên môn y khoa = độ chặt quy trình:** Member A và B **gán nhãn độc lập** cho nhóm C và D theo rubric, rồi báo cáo **inter-annotator agreement (Cohen's κ)**. Đây là thứ hội đồng chấp nhận ở cấp môn học và nói thật về giới hạn, thay vì giả vờ có chuyên gia.
- **Không dùng LLM-as-judge làm ground truth** cho abstention: generator và judge cùng họ Gemini → chung blind spot, chỉ đo sự nhất quán của model với chính nó, không đo tính an toàn. LLM-as-judge chỉ dùng ở chỗ RAGAS faithfulness (suy luận văn bản), và nếu dùng thì **đổi model khác họ với generator**.
- Test nhánh INCORRECT: đưa câu nhóm A/B vào → phải đi qua rewrite → vẫn kém → ABSTAIN, không bịa.

**DoD:** Nhánh INCORRECT chạy đúng (rewrite → re-retrieve → ABSTAIN khi cần), `trace` đầy đủ. Safety subset 50 câu (A–E) có nhãn; nhóm A/B kiểm chứng bằng script; nhóm C/D có κ báo cáo được.

**Deliverable:** `testset.jsonl` (gồm safety subset 50 câu + nhãn + nguồn nhãn) + corrective loop hoàn chỉnh + κ report.

---

### TUẦN 6 — Evaluation (RAGAS + Risk–Coverage + Static vs Corrective)

**Mục tiêu:** Số liệu định lượng đầy đủ — phần ăn điểm research.

**Member B (dẫn):**
- Chạy RAGAS: faithfulness, answer relevancy, context precision/recall.
- Phân tích lỗi: xem câu nào fail, vì sao.
- 🎯 **[Enhancement 1a] Đo mức giảm hallucination:** chạy RAGAS faithfulness trên **LLM-only vs Full RAG** → định lượng "RAG giảm bịa bao nhiêu %".
- 🎯 **[Abstention quality trên safety subset 50 câu]** tính precision/recall của ABSTAIN **theo từng nhóm A–E**. Report cả 2 loại lỗi: false refusal (từ chối câu E lẽ ra trả lời được) và unsafe answer (trả lời câu A/B/D lẽ ra phải abstain).

**Member A:**
- 🎯 **[Trục đóng góp] Đường cong risk–coverage:** từ `trace`, sắp câu theo điểm tin cậy (rerank score + trạng thái grader); quét ngưỡng → mỗi ngưỡng cho 1 điểm (coverage = % câu được trả lời, risk = 1 − faithfulness/safety trên phần đã trả lời). Vẽ đường cong. **Chọn điểm vận hành từ đường cong này** → đây là giá trị thay cho hằng số 0.3 cũ.
- 🎯 **[Headline đổi trục] Bảng Static vs Corrective:** hàng chính là **Static Full pipeline vs Corrective Full pipeline** (giữ thêm LLM-only / Naive RAG làm mốc dưới) × các metric (faithfulness, answer relevancy, context precision, abstention P/R, coverage). Kèm **trigger rate** (% câu kích hoạt rewrite), **Δlatency chỉ trên câu bị trigger**, **Δcost**.
- Ablation phụ: reranker on/off; **chunk 256 vs 512** (đã embed sẵn Tuần 2 → chỉ chạy eval + so).

**Cách làm:**
- Dùng `src/eval/run_ragas.py` chạy cho từng cấu hình.
- Risk–coverage: script quét ngưỡng trên điểm tin cậy, tính (coverage, risk) từng bước → matplotlib.
- Ghi trade-off: corrective tăng faithfulness/safety bao nhiêu, đổi lại tăng latency/cost trên bao nhiêu % câu.

**DoD:** Có bảng RAGAS + **đường cong risk–coverage + điểm vận hành chọn từ data** + **bảng headline Static vs Corrective** + abstention P/R theo nhóm + trigger rate/Δlatency/Δcost. Có con số "% giảm hallucination".

**Deliverable:** Báo cáo đánh giá định lượng, với **đường cong risk–coverage + bảng Static vs Corrective** làm kết quả trung tâm.

> ⚠️ **Buffer:** Tuần 5–6 là peak, dễ trượt. Thứ tự giữ bằng mọi giá: (1) bảng Static vs Corrective, (2) đường cong risk–coverage, (3) faithfulness LLM-only vs RAG. Cắt được nếu kẹt: ablation reranker on/off. **E2 evidence-highlighting (Tuần 7) là buffer cắt được lớn nhất** — đẹp cho portfolio nhưng không đóng góp cho claim khoa học.

---

### TUẦN 7 — Latency/Cost Benchmark + Tối ưu + Deploy

**Mục tiêu:** Đo chỉ số vận hành + đưa demo lên cloud.

**Member A (dẫn):**
- Đẩy embedding lên Qdrant Cloud; deploy Space lên HuggingFace.
- Đo latency p50/p95 tách theo stage (retrieval / rerank / generation).

**Member B:**
- Tính cost per 1.000 query (dựa số token thực đo).
- Tối ưu: cache query phổ biến, giảm top-k vào reranker, streaming output.
- 🎯 **[Enhancement 2] Evidence-highlighting trong demo:** mỗi câu trả lời hiển thị rõ *câu nguồn nào support* — tái dùng pattern Evidence Drawer từ ViHire-Agent. Người dùng bấm vào citation [1] → highlight đoạn text gốc trong nguồn.

**Cách làm:**
- Deploy: tạo HF Space (SDK Streamlit), set `GEMINI_API_KEY` + Qdrant Cloud credentials qua Secrets.
- Benchmark latency: chạy 50–100 query, log thời gian từng stage → tính p50/p95.
- Cost: đếm input/output token trung bình × giá Gemini Flash → quy ra /1.000 query.
- 🎯 Evidence UI: pipeline đã trả về chunk nguồn kèm câu trả lời (có sẵn) → frontend map citation [n] tới đoạn text tương ứng, dùng expander/highlight của Streamlit. Không cần thay đổi backend.

**DoD:** Demo chạy được trên HF Spaces (link public); có bảng latency + cost; **demo hiển thị evidence cho mỗi câu trả lời** (nếu E2 không bị cắt).

**Deliverable:** Demo live + báo cáo vận hành (latency/cost/deploy). Evidence-highlighting nếu còn thời gian.

> ⚠️ **E2 là buffer:** nếu Tuần 5–6 tràn sang, cắt E2 trước tiên. Deploy + latency/cost là bắt buộc; evidence-highlighting là nice-to-have (portfolio), không phần nào của claim đóng góp phụ thuộc nó.

---

### TUẦN 8 — Báo cáo + Slides + Hoàn thiện

**Mục tiêu:** Đóng gói toàn bộ thành sản phẩm nộp được.

**Cả hai:**
- Viết báo cáo kỹ thuật (kiến trúc, phương pháp, kết quả, phân tích).
- Làm slides trình bày (~12–15 slide).
- Dọn repo, viết README, quay video demo dự phòng.

**Cách làm:**
- Báo cáo cấu trúc: Giới thiệu → Vấn đề → Kiến trúc (có sơ đồ corrective loop) → Phương pháp → Thực nghiệm (risk–coverage + Static vs Corrective) → **Limitations** → Kết luận & Hướng phát triển.
- **Mục Limitations (bắt buộc):** chưa có reviewer y khoa; nhãn abstention theo khả năng truy xuất + policy, không theo đánh giá lâm sàng; claim là "biết khi nào không đủ căn cứ để trả lời", không phải "an toàn lâm sàng"; RAG giảm chứ không diệt hallucination (LLM vẫn có thể đọc sai context). Ghi rõ điều này **có lợi** — cho thấy hiểu ranh giới kết quả, thay vì để hội đồng bắt lỗi.
- Slide: 1 slide kiến trúc (sơ đồ corrective loop), **slide "điểm khác biệt" = trục đóng góp (calibrated abstention)**, 1–2 slide kết quả (risk–coverage + bảng Static vs Corrective), 1 slide demo.
- Chuẩn bị Q&A: vì sao hybrid? vì sao **abstention thay vì web-search fallback**? ngưỡng chọn thế nào (risk–coverage)? `max_iter=1` có đủ không? ai gán nhãn safety (κ, nhãn theo cấu trúc)? trade-off latency của corrective?

**DoD:** Báo cáo + slides + demo link + repo sạch — sẵn sàng nộp/bảo vệ.

**Deliverable:** Bộ sản phẩm hoàn chỉnh.

---

## 3. Tổng hợp Deliverables

1. Source code (GitHub, config-driven, có README).
2. Demo live trên HuggingFace Spaces.
3. Báo cáo kỹ thuật + bảng metric (retrieval, RAGAS, ablation, latency/cost).
4. Slides trình bày + video demo dự phòng.

---

## 4. Metrics tổng hợp (mục tiêu định lượng)

| Nhóm | Metric |
|------|--------|
| Retrieval | Recall@5, MRR, NDCG (so sánh BM25/Dense/Hybrid); ablation chunk 256 vs 512 |
| Generation | Faithfulness, Answer Relevancy, Context Precision/Recall (RAGAS) |
| **Headline** 🎯 | Bảng **Static vs Corrective** Full pipeline (giữ LLM-only / Naive RAG làm mốc dưới) — kết quả trung tâm |
| **Corrective** 🎯 | **Đường cong risk–coverage** + điểm vận hành chọn từ data; trigger rate; Δlatency-on-triggered; Δcost |
| **Safety** 🎯 | % giảm hallucination (RAG vs LLM-only); Abstention precision/recall **theo nhóm A–E**; Cohen's κ (nhãn C/D) |
| Vận hành | Latency p50/p95, Cost/1.000 query |
| Robustness | False-refusal rate (nhóm E); unsafe-answer rate (nhóm A/B/D) |

---

## 5. Rủi ro & Giải pháp

| Rủi ro | Giải pháp |
|--------|-----------|
| **Dataset không phủ đủ 2 khoa** ⚠️ | **Verify NGAY Tuần 0–1** (2 tiếng) trước khi commit. Nếu mỏng, ABSTAIN sẽ trigger sai lý do (thiếu data thật, không phải retrieval kém) → hỏng claim. Bổ sung `hungnm/vietnamese-medical-qa`; nếu vẫn thiếu, đổi/thêm khoa |
| Chunking kém → retrieval rác | Kiểm tra thủ công tuần 2 trước khi index toàn bộ |
| Reranker trên CPU chậm khi deploy | Giảm candidate 20→10, hoặc toggle tắt reranker ở demo |
| Hết quota Gemini free tier | Flash-Lite cho dev, Flash cho demo; corrective chỉ +1 call trên ~20–30% câu → vẫn trong free tier |
| **Non-determinism từ corrective loop** | `max_iter=1` giữ gần-deterministic; log `trace` để tái lập; eval chạy seed cố định |
| **Không có reviewer y khoa** | Nhãn abstention **theo cấu trúc** (nhóm A/B kiểm chứng bằng máy, D theo policy) + double-annotation κ. Ghi rõ giới hạn trong báo cáo |
| **Trượt tiến độ Tuần 5–6** (rủi ro thật lớn nhất) | Front-load test set về Tuần 2; thứ tự cắt: E2 → ablation reranker; giữ risk–coverage + Static-vs-Corrective bằng mọi giá |
| Hallucination y tế | Defense-in-depth 7 lớp (mục 1.5) + ABSTAIN + đo bằng RAGAS faithfulness |
| Nhóm 2 người lệch tiến độ | Sync 2 buổi/tuần, dùng GitHub Issues chia task |

---

## 6. Hướng mở rộng (sau đồ án)

- Thêm chuyên khoa: chỉ cần thêm config + data, không sửa kiến trúc.
- Router tự động chọn khoa (keyword/LLM) khi số khoa lớn.
- Multimodal: Visual QA cho ảnh y tế (X-quang, da liễu).
- Fine-tune embedding y khoa tiếng Việt để tăng retrieval.

# Contract — Gate 0 (data sufficiency)

> Contract. Đổi file này = đổi thiết kế. Phải kèm 1 dòng mới trong `../decisions/DECISIONS.md`.

Nguồn: COMPRESS Session 2, mục 7 (+ mục 3 cho eval set). Script: `gate0_data_check.py`.

## ✅ TRẠNG THÁI: Gate 0 = **GO** (chạy 2026-08-07)

Chặn đã gỡ. `loader.py` (data thật), `embedder.py` (bge-m3), `indexer.py` (Qdrant),
`retriever.py` (hybrid+rerank) và ingestion data thật **được phép wire**. Plan giữ nguyên.

### Kết quả lần chạy (2026-08-07)

Nguồn: `scripts/gate0_data_check.py`, chạy local Windows (CPU, ~2 phút).
Corpus = `urnus11/Vietnamese-Healthcare` split **`vinmec_article_content`** (32,604 bài;
dataset **gated** → cần `HF_TOKEN` + accept terms). Eval = **`tmnam20/ViMedAQA`** split
`train` (39,881 QA). Text corpus ghép `["title", "content"]`.

| # | Tiêu chí | Kết quả | Ngưỡng | |
|---|---|---|---|---|
| 1 | Coverage | tim_mach **16,869** · tieu_duong **8,872** (trùng cả 2 khoa: 6,967) | ≥150/khoa | PASS |
| 2 | Eval set | **3,423** QA thuộc 2 khoa (tim_mach 2,698 · tieu_duong 913) | ≥40 | PASS |
| 3 | Alignment | **30/30 = 100%** có max-sim ≥ 0.15; median 0.409 · mean 0.468 · thấp nhất 0.273 | ≥60% | PASS |

### Chạy lại sau khi siết keyword (DEC-010/011) — vẫn **GO**

Bảng trên là lần chạy gốc, giữ nguyên làm lịch sử. Siết `specialties.yaml` làm đổi số
(ít keyword hơn → ít bài/QA khớp hơn), nên đã chạy lại để verdict còn hiệu lực:

| # | Trước siết | Sau siết | Ngưỡng | |
|---|---|---|---|---|
| 1 | 16,869 · 8,872 | **14,618 · 8,848** (trùng 6,549) | ≥150/khoa | PASS |
| 2 | 3,423 QA | **2,645 QA** | ≥40 | PASS |
| 3 | 30/30 · median 0.409 | **30/30 · median 0.444** | ≥60% | PASS |

Tiêu chí #2 mất 778 QA nhưng vẫn dư **66 lần** ngưỡng. Alignment còn *khá hơn*
(median 0.409 → 0.444) vì đã loại bài sai khoa khỏi corpus.

### Tái kiểm sau khi chốt chính sách gán khoa (DEC-016) — vẫn **GO**

Chính sách chuyển từ "keyword có mặt ở đâu cũng tính" sang **"TITLE hoặc ≥25 lần"**.
Corpus co từ 16.917 → **1.425 bài** (gần 12×), nên verdict phải đo lại.

| # | Trước (có mặt là tính) | Sau (TITLE hoặc ≥25) | Ngưỡng | |
|---|---|---|---|---|
| 1 | 14.618 · 8.848 | **727 · 698** (trùng 1.1%) | ≥150/khoa | PASS |
| 2 | 2.645 QA | **2.645 QA** (không đổi — chính sách áp cho corpus, không áp cho eval) | ≥40 | PASS |
| 3 | 30/30 · median 0.444 | **29/30 = 97%** · median 0.378 | ≥60% | PASS |

Tiêu chí #3 mất 1 QA và median tụt 0.444 → 0.378, đúng như kỳ vọng khi corpus nhỏ đi
12 lần — nhưng vẫn dư **37 điểm phần trăm** trên sàn. Tái lập: `scripts/alignment_audit.py`.

> ⚠️ **Giới hạn #2 dưới đây đã ĐÓNG bằng DEC-016.** Trùng khoa từ 38.7% → 1.1%.
> Giữ nguyên đoạn cũ làm lịch sử.

### ⚠️ Giới hạn của lần chạy này — ghi vào phần Limitations của báo cáo

1. **Tiêu chí #3 là proxy trùng lặp chủ đề, KHÔNG phải answerability thật.** Nó chỉ hỏi
   "đáp án có cosine ≥ 0.15 với *bất kỳ* doc nào trong 32k doc không". Bằng chứng: QA
   rác nhất trong mẫu (`"Bệnh Fallout là bệnh như thế nài?"` — text hỏng) vẫn đạt 0.273
   và bị tính là "tìm thấy". Corpus (vinmec.com) và eval (youmed.vn) **khác nguồn hoàn
   toàn** → không có đảm bảo đáp án suy ra được từ corpus. Faithfulness/context-recall
   Tuần 6 mới là phép đo thật.
2. **Keyword lọc khoa còn rộng:** 6,967 bài khớp CẢ 2 khoa. `"tim"`, `"đột quỵ"`,
   `"tai biến"` trong `config/specialties.yaml` bắt quá rộng. Coverage dư ~100× nên không
   đe dọa verdict, nhưng **phải siết trước khi build corpus thật ở Tuần 1**.
3. **ViMedAQA có dòng nhiễu** (chính tả hỏng, câu vô nghĩa) → test set Tuần 2 phải lọc tay.

## 3 tiêu chí pass/fail

| # | Tiêu chí | Pass khi | Fail → verdict |
|---|---|---|---|
| 1 | **Coverage** | ≥ **150 doc/khoa** (cho cả 2 khoa) | NO-GO #1 |
| 2 | **Eval set** | ≥ **40 QA** thuộc 2 khoa (ViMedAQA ground truth, nhóm E control BẮT BUỘC có) | NO-GO #2 |
| 3 | **Alignment** | Đáp án ⊂ corpus (đáp án nằm trong corpus) | NO-GO #3 |

> 3 `TODO(unknown)` cũ ở mục này đã đóng 2026-08-07 — nguồn là chính `gate0_data_check.py`
> (file mà contract này trỏ tới): `MIN_EVAL_QA_TOTAL = 40` cho ngưỡng số, và nhánh
> verdict `#2: bù QA từ dataset khác cho đủ test set + nhóm E control` cho NO-GO #2.
> Không phải số bịa; xem DEC-007.

## Verdict → hành động

- **GO** (pass cả 3) → wire component thật: `loader.py` → `embedder.py` (bge-m3) →
  `indexer.py` (Qdrant) → `retriever.py` (hybrid+rerank). Plan giữ nguyên.
- **NO-GO #1** (corpus < 150/khoa) → bù `hungnm/vietnamese-medical-qa` hoặc đổi/gộp khoa.
- **NO-GO #2** (eval < 40 QA / 2 khoa) → bù QA từ dataset khác cho đủ test set + nhóm E control.
- **NO-GO #3** (alignment fail — đáp án không nằm trong corpus) → **NGHIÊM TRỌNG, DỪNG.**
  Quyết eval strategy (chỉ eval tập con answerable, hoặc đổi eval) **TRƯỚC** khi viết dòng build nào.

## Cách chạy (mục 7)

1. Lượt 1 `INSPECT_ONLY=True` → xem schema → sửa CONFIG.
2. Lượt 2 `INSPECT_ONLY=False` → ra verdict.

CONFIG đã điền xong 2026-08-07 (placeholder `"ViMedAQA"` → `tmnam20/ViMedAQA`;
`CORPUS_SPLIT` `"train"` → `vinmec_article_content` vì split `train` **không tồn tại**).

**Muốn chạy lại phải có `HF_TOKEN`** — corpus là dataset gated (`gated: auto`), tải ẩn
danh trả HTTP 401. Accept terms tại trang dataset bằng đúng tài khoản của token.

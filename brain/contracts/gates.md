# Contract — Gate 0 (data sufficiency)

> Contract. Đổi file này = đổi thiết kế. Phải kèm 1 dòng mới trong `../decisions/DECISIONS.md`.

Nguồn: COMPRESS Session 2, mục 7 (+ mục 3 cho eval set). Script: `gate0_data_check.py`.

## ⛔ TRẠNG THÁI: Gate 0 ĐANG **CHƯA CHẠY**

Gate 0 chặn **toàn bộ build data-dependent**: `loader.py` (data thật), `embedder.py`
(bge-m3), `indexer.py` (Qdrant), `retriever.py` (hybrid+rerank), và mọi ingestion data thật.
Scaffold + stub được phép làm song song; **KHÔNG wire data/model thật cho tới khi Gate 0 = GO**.

## 3 tiêu chí pass/fail

| # | Tiêu chí | Pass khi | Fail → verdict |
|---|---|---|---|
| 1 | **Coverage** | ≥ **150 doc/khoa** (cho cả 2 khoa) | NO-GO #1 |
| 2 | **Eval set** | Có eval set (ViMedAQA ground truth, nhóm E control BẮT BUỘC có) | TODO(unknown): fail eval set map sang verdict nào? COMPRESS không nêu |
| 3 | **Alignment** | Đáp án ⊂ corpus (đáp án nằm trong corpus) | NO-GO #3 |

TODO(unknown): ngưỡng số cho tiêu chí "eval set" (số câu tối thiểu) — COMPRESS không nêu con số.
TODO(unknown): "NO-GO #2" — verdict scheme dùng #1 và #3, COMPRESS không định nghĩa #2.

## Verdict → hành động

- **GO** (pass cả 3) → wire component thật: `loader.py` → `embedder.py` (bge-m3) →
  `indexer.py` (Qdrant) → `retriever.py` (hybrid+rerank). Plan giữ nguyên.
- **NO-GO #1** (corpus < 150/khoa) → bù `hungnm/vietnamese-medical-qa` hoặc đổi/gộp khoa.
- **NO-GO #3** (alignment fail — đáp án không nằm trong corpus) → **NGHIÊM TRỌNG, DỪNG.**
  Quyết eval strategy (chỉ eval tập con answerable, hoặc đổi eval) **TRƯỚC** khi viết dòng build nào.

## Cách chạy (mục 7)

1. Lượt 1 `INSPECT_ONLY=True` → xem schema → sửa CONFIG
   (đặc biệt `EVAL_DATASET` đang là placeholder `"ViMedAQA"`, phải điền path HF thật).
2. Lượt 2 → ra verdict.

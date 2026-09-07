# Đo retrieval — Tuần 3 (T3.4)

> Sinh bởi `scripts/eval_retrieval.py` · 2026-09-07 
> 21 câu nhóm E · `top_k_dense=10` · `max_length=512`

Ground truth = `reference_context_ids` cấp **BÀI** (DEC-025e); mọi metric
tính trên `doc_id` **đã dedup** — một bài dài sinh nhiều chunk, không dedup
thì recall tự phồng.

⚠️ `sparse` là **learned sparse của bge-m3, KHÔNG phải BM25**.

## Bảng chính

| collection | mode | rerank | recall@20 | recall@5 | mrr@5 | ndcg@5 |
|---|---|---|---|---|---|---|
| vimed_rag_512 | hybrid | khong | 0,667 | 0,571 | 0,413 | 0,454 |
| vimed_rag_512 | hybrid | co | 0,667 | 0,619 | 0,500 | 0,531 |

**`recall@20` là cột quan trọng nhất khi so `hybrid` với `dense`.** Sau rerank,
thứ tự trong pool bị chấm lại sạch nên khác biệt ở top-5 gần như biến mất;
chỗ nhánh truy hồi thực sự đóng góp là đưa bài đúng VÀO pool 20.

## Chi phí mỗi truy vấn

| Giai đoạn | Thời gian |
|---|---|
| truy hồi `hybrid` trên `vimed_rag_512` | 0.78s |
| **rerank** (10 cặp, `max_length=512`) | **20.8s** (2.08s/cặp) |

## Bài vàng nằm ở hạng mấy trong pool ứng viên

Hạng của `reference_context_id` trong danh sách **doc_id đã dedup** của pool
(trước rerank). `—` = không lọt pool ở cấu hình đó, tức rerank **không thể**
cứu được: bài đúng chưa từng vào tới tay nó.

| câu | hybrid/512 |
|---|---|
| E-01 | 2 |
| E-02 | 9 |
| E-03 | — |
| E-04 | 2 |
| E-05 | 3 |
| E-06 | 1 |
| E-07 | — |
| E-08 | 1 |
| E-09 | 3 |
| E-10 | 1 |
| E-11 | — |
| E-12 | 1 |
| E-13 | — |
| E-14 | 2 |
| E-15 | 1 |
| E-16 | — |
| E-17 | 1 |
| E-18 | — |
| E-19 | — |
| E-20 | 2 |
| E-21 | 6 |

## Phân bố max-logit theo nhóm

Đây là đại lượng `Grader.score_of` dùng (max trên context). **Logit thô**
— sau sigmoid mọi thứ dồn về 0,98-0,99 và mất phân giải đúng ở vùng cần
đặt ngưỡng. Cột sigmoid chỉ để đối chiếu với `grader.*_threshold` hiện tại.

| Nhóm | n | logit trung vị | logit min | logit max | sigmoid(trung vị) |
|---|---|---|---|---|---|
| A | 18 | -0,88 | -7,11 | 2,15 | 0,2923 |
| B | 12 | -5,41 | -7,55 | 0,70 | 0,0044 |
| D | 8 | -1,04 | -3,68 | 1,63 | 0,2619 |
| E | 21 | 3,99 | -2,82 | 7,57 | 0,9818 |

Nhóm **E** trả lời được, **A/B** không (bài không có trong corpus), **D**
phải bị policy gate chặn TRƯỚC retrieval nên score của nó không dùng để
đặt ngưỡng. Ngưỡng grader phải tách được **E** khỏi **A/B**.

## ⛔ Score bám ĐỘ CÙNG CHỦ ĐỀ, không bám ĐỘ ĐÚNG

`max-logit` là đại lượng `Grader.score_of` dùng để quyết định trả lời hay
từ chối. `hạng vàng` là vị trí bài vàng SAU rerank. Hai cột này **không đi
cùng nhau** — đó là phát hiện chính của T3.4.

| câu | max-logit | logit bài vàng | hạng vàng | chẩn đoán |
|---|---|---|---|---|
| E-01 | +6,35 | +6,35 | 1 | vàng đứng đầu |
| E-02 | +3,82 | +1,93 | 6 | vàng tụt hạng 6 |
| E-03 | +4,12 | — | — | **bài vàng KHÔNG vào pool** |
| E-04 | +3,58 | +3,58 | 1 | vàng đứng đầu |
| E-05 | -0,36 | -1,46 | 2 | vàng tụt hạng 2 |
| E-06 | +3,34 | +3,34 | 1 | vàng đứng đầu |
| E-07 | +5,38 | — | — | **bài vàng KHÔNG vào pool** |
| E-08 | +5,05 | +4,74 | 2 | vàng tụt hạng 2 |
| E-09 | -0,35 | -1,42 | 2 | vàng tụt hạng 2 |
| E-10 | +3,12 | +3,12 | 1 | vàng đứng đầu |
| E-11 | +4,75 | — | — | **bài vàng KHÔNG vào pool** |
| E-12 | -1,30 | -1,30 | 1 | vàng đứng đầu |
| E-13 | +7,57 | — | — | **bài vàng KHÔNG vào pool** |
| E-14 | +5,53 | +2,77 | 2 | vàng tụt hạng 2 |
| E-15 | +3,99 | +3,99 | 1 | vàng đứng đầu |
| E-16 | +6,25 | — | — | **bài vàng KHÔNG vào pool** |
| E-17 | +5,05 | +5,05 | 1 | vàng đứng đầu |
| E-18 | +6,67 | — | — | **bài vàng KHÔNG vào pool** |
| E-19 | -2,82 | — | — | **bài vàng KHÔNG vào pool** |
| E-20 | +3,14 | +3,14 | 1 | vàng đứng đầu |
| E-21 | +2,71 | +1,72 | 2 | vàng tụt hạng 2 |

### Quét ngưỡng

| logit | sigmoid | E trả lời | …có vàng ở top-5 | A/B lọt lưới |
|---|---|---|---|---|
| +4,00 | 0,9820 | 10/21 | 4 | **0**/30 |
| +3,00 | 0,9526 | 16/21 | 9 | **0**/30 |
| +2,50 | 0,9241 | 17/21 | 10 | **0**/30 |
| +2,27 | 0,9064 | 17/21 | 10 | **0**/30 |
| +2,00 | 0,8808 | 17/21 | 10 | **1**/30 |
| +1,00 | 0,7311 | 17/21 | 10 | **7**/30 |
| +0,41 | 0,5999 | 17/21 | 10 | **8**/30 |
| -1,00 | 0,2689 | 19/21 | 12 | **11**/30 |

⚠️ Ngưỡng ở đây được chọn TRÊN CHÍNH dữ liệu dùng để đánh giá — không có
tập giữ lại. Con số vì thế **lạc quan**. Tuần 6 phải tách tập hoặc mở rộng
nhóm E trước khi báo cáo ngưỡng như một kết quả.

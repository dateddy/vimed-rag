# Latency & Cost — ViMed-RAG (Tuần 7)

> Sinh bằng `python scripts/build_perf_report.py`. **Đừng sửa tay** — sửa ở script rồi dựng lại, nếu không con số và câu văn sẽ trôi khỏi nhau.

## 1. Chi phí — USD trên 1.000 truy vấn

Model **`google/gemini-2.5-flash`** · giá **$0,30/1M prompt** · **$2,50/1M output** (nguồn `openrouter.ai/api/v1/models`, lấy 2026-09-15; đối chiếu lại: `python scripts/build_perf_report.py --check-pricing`).

Token lấy từ `runs.jsonl` (lô 59 câu). **`cache_hits` toàn file = 0** → mọi lượt là gọi API thật, không có lượt nào đọc cache, nên số token dưới đây là chi phí thật chứ không phải chi phí lúc phát triển.

| Hệ | prompt/câu | output/câu | **USD/1.000 query** |
|---|---:|---:|---:|
| **Corrective RAG** | 1 161 | 96 | **$0,59** |
| LLM-only (baseline) | 120 | 559 | **$1,43** |

⚠️ **Corrective RẺ HƠN baseline 2,4 lần** — nghịch trực giác, và có cơ chế giải thích được: output đắt gấp **8,3 lần** input. Có ngữ cảnh thì model trả lời ngắn và bám nguồn; không có thì nó nói dài. Corrective trả **prompt** to (5 chunk ngữ cảnh) nhưng **output** nhỏ, và bên đắt là bên output.

⚠️ **Bảng này chỉ tính LLM.** Không gồm: embedding + rerank (tự host, không tốn tiền theo lượt nhưng tốn CPU — xem mục 2), Qdrant Cloud (free tier), HF Space (PRO $9/tháng, chi phí **cố định** không theo lượt).

⚠️ **Đừng lẫn với `~$0,11/câu`** ghi ở chỗ khác trong repo: đó là **LLM judge của RAGAS** (`openai/gpt-5`, chạy lúc *đánh giá*), không phải chi phí phục vụ một truy vấn.

## 2. Latency — p50/p95 tách theo stage (local)

Đo trên **59 câu**, mỗi câu kèm **đối chứng nhịp máy** — một vòng lặp CPU thuần chạy ngay trước và sau phép đo. Câu nào nhịp phồng quá **1,5×** so với lúc hiệu chuẩn thì bị **loại** khỏi p50/p95 thay vì trộn vào.

⚠️ **5/59 câu bị loại** vì máy bận lúc đo: A-03, A-12, A-13, A-17, E-19. Bảng dưới tính trên **54** câu còn lại.

| Nhánh | n | **tổng p50** | **tổng p95** | rerank p50 | search p50 | generation p50 | rewrite p50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ANSWER | 17 | **22,8s** | **26,0s** | 18,7s | 1,4s | 2,6s | 0,0s |
| ABSTAIN — policy | 8 | **0,0s** | **0,0s** | 0,0s | 0,0s | 0,0s | 0,0s |
| ABSTAIN — truy hồi | 29 | **43,1s** | **53,9s** | 37,7s | 3,2s | 0,0s | 1,9s |

**Rerank chiếm 85% tổng thời gian** trên cả lô. Đó là câu trả lời cho *'tối ưu ở đâu'*: không phải ở LLM, và không phải ở truy hồi — mà ở **cross-encoder chấm lại trên CPU**.

Toàn lô: p50 **41,3s** · p95 **48,6s** (n = 54).

⚠️ **`p95` ở n nhỏ gần như chính là max.** Nhánh ANSWER chỉ có **17** câu, nên p95 nội suy giữa mẫu thứ 16 và 17. Trích kèm **n**, đừng trích trần.

⚠️ **Nhánh TỪ CHỐI đắt hơn nhánh TRẢ LỜI** — nó chạy **2 lượt** truy hồi + rerank (lượt 2 vẫn chạy đủ để `trace` giữ được điểm, chỉ bị tước quyền *lật* phán quyết — DEC-061). Đây là **giá của an toàn**, nói thẳng ra được chứ không cần giấu.

⚠️ **Nhánh policy gần như bằng 0 và tốn 0 lượt LLM** — nó chặn **trước** truy hồi (DEC-024). Trộn nó vào p50 chung sẽ kéo con số xuống một cách vô nghĩa, nên bảng trên tách riêng.

## 3. Latency trên HF Space — thứ người dùng thật chờ

Đo bằng Playwright lái UI thật trên **datvu107-dateddy/vimed** (`cpu-basic`), 2026-09-15. Space **không có batch runner** nên đây là vài mẫu, **không phải p50/p95**, và **không tách được stage** — đó là lý do mục 2 phải đo ở local.

| Nhánh | các lượt đo | n |
|---|---|---:|
| ABSTAIN — policy | 0,7s · 0,6s | 2 |
| ANSWER | 20,4s · 18,6s | 2 |
| ABSTAIN — truy hồi | 37,3s · 32,0s | 2 |

**Page-ready** (thời gian tới lúc trang dùng được): 11,6s · 6,6s · 8,9s · 6,0s · 5,9s — n = 5.

⚠️ Đã **loại** 1 mẫu lệch (95,6s): đối chứng `health` ở cùng thời điểm vẫn **0,82–0,96s** — mạng và Space bình thường, nên chỗ nghẽn là **laptop đang đo**. Đây chính là bẫy mô tả ngay dưới, bắt được **bằng máy** thay vì bằng trí nhớ.

⛔ **BẪY ĐO — đã dính thật 2026-09-15.** Bật một **Chromium mới cho mỗi mẫu** làm page-ready phồng **5,9s → 103,7s (17×)**; dùng **một** browser cho cả lô thì ổn định. Đối chứng quyết định: `curl /_stcore/health` chạy **xen kẽ** vẫn 0,84–0,99s suốt → nghẽn nằm ở **laptop đang đo**, không ở Space. Phiên đó đã kết luận nhầm *'cold start 73–85s'* rồi tự bác bỏ. Cùng lớp với đối chứng nhịp máy ở mục 2, và là lý do nó tồn tại.


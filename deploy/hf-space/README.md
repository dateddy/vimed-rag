---
title: ViMed-RAG
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: "QA y tế tiếng Việt: Corrective RAG + abstention"
---

# ViMed-RAG — Space đo vận hành (Tuần 7)

> ⚠️ **Đây CHƯA phải bản demo.** Space này deploy bản UI Tuần 3 (2 tab) với đúng
> một mục đích: **đo latency rerank trên CPU của Spaces**. Rerank đo trên máy
> local là **75–82 giây/truy vấn**, và câu hỏi cần trả lời sớm là Spaces có kham
> nổi không. Tab đầu-cuối (chạy generator thật, ẩn khối nguồn ở câu từ chối) là
> việc kế tiếp — xem `brain/state/STATUS.md`.

## Hai tab

| Tab | Cần gì | Làm gì |
|---|---|---|
| 🔎 Truy hồi thật | secrets Qdrant + tải ~4,5 GB weight lần đầu | `HybridRetriever` + `BgeReranker` chạy thật, **in thời gian mỗi truy vấn** |
| 🧪 Corrective loop (Fake) | không cần gì | mô phỏng vòng corrective bằng Fake components |

## Secrets phải set (Settings → Variables and secrets)

| Tên | Giá trị |
|---|---|
| `QDRANT_URL` | REST endpoint cluster, dạng `https://<id>.<region>.cloud.qdrant.io:6333` — **không** phải URL trang dashboard |
| `QDRANT_API_KEY` | key **CHỈ-ĐỌC** giới hạn collection (DEC-071). **Không** dùng key toàn quyền ở đây |

Không cần sửa code: `src/config.py` dùng `os.environ.setdefault` nên secrets của
Space thắng `.env` (Space không có `.env`).

## Lần chạy đầu chậm là bình thường

Tab 1 tải `bge-m3` + `bge-reranker-v2-m3` (~4,5 GB) rồi cache. Lần hỏi đầu gánh
cả tải model lẫn nạp weight; **số cần đọc là lần hỏi thứ hai trở đi**.

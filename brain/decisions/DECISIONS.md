# DECISIONS — nhật ký quyết định (append-only)

> **Append-only. KHÔNG sửa dòng cũ.** Muốn đảo một quyết định → thêm dòng MỚI với
> `Supersedes: DEC-00X`, để dòng cũ nguyên vẹn làm lịch sử.
>
> Cột "Ai quyết": `A` = Member A (Đạt), `B` = Member B.

> ⚠️ DEC-001…DEC-006 chốt trong **Session 2** bởi Member A, **CHƯA có xác nhận của GVHD**
> (xem việc treo trong `../state/STATUS-A.md`).

| ID | Ngày | Quyết định | Lý do (1 dòng) | Ai quyết | Supersedes |
|---|---|---|---|---|---|
| DEC-001 | 2026-07-04 | **Partial agentic**, giữ scope IN/OUT | Full agentic = tái hiện công trình 2023–24, phá tính lặp của eval | A | — |
| DEC-002 | 2026-07-04 | Framing = **calibrated abstention + risk–coverage** | Claim đo được thay vì claim khẳng định | A | — |
| DEC-003 | 2026-07-04 | **KHÔNG LangGraph** — Python thuần + `trace` list | 4 node + max_iter=1 → LangGraph là chi phí thuần (cold start, version churn) | A | — |
| DEC-004 | 2026-07-04 | Ablation chunk **256 vs 512**, dời về **Tuần 2** | Rẻ nhất, hay bị hỏi nhất; chạy lúc index gần free | A | — |
| DEC-005 | 2026-07-04 | Safety subset **50 câu nhãn THEO CẤU TRÚC (A–E)** | Không có bác sĩ; LLM-as-judge = vòng luẩn quẩn (judge cùng họ generator) | A | — |
| DEC-006 | 2026-07-04 | E2 evidence-highlighting = **buffer cắt được** | Đẹp portfolio nhưng không đóng góp claim | A | — |

<!-- TODO(unknown): ngày chính xác các quyết định — COMPRESS ghi "session này" (Session 2);
     dùng 2026-07-04 khớp tên file handoff archive. Xác nhận nếu cần ngày thật. -->

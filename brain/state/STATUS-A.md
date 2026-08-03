# STATUS — Member A (Đạt)

> Owner: Member A. State ghi đè mỗi session; **không** tạo `STATUS-v2`.

**Cập nhật lần cuối:** 2026-07-04 (Session 2 — Tuần 1, Nhánh A infra/scaffold)

## Đang làm
- Tuần 1, Nhánh A: infra / scaffold.
- Vừa xong Session 2: (1) tích hợp partial-agentic vào project plan; (2) sinh `gate0_data_check.py`; (3) sinh prompt scaffold cho Claude Code.

## Blocker
- **Gate 0 (data sufficiency) CHƯA CHẠY** → chặn toàn bộ build data-dependent.
  Scaffold + stub được phép song song, KHÔNG wire data/model thật cho tới khi Gate 0 = GO.

## 3 việc kế tiếp
1. Chạy `gate0_data_check.py` + điền `EVAL_DATASET` path HF thật (đang là placeholder `"ViMedAQA"`) → báo verdict.
2. Chạy prompt scaffold repo: `pytest` xanh, Streamlit demo chạy bằng Fake (không cần API key/Qdrant/GPU).
3. Xác nhận claim với GVHD (5 phút) — claim đo được nhưng khiêm tốn về novelty.

## Việc treo ngoài code
- Sync bản `.html` của plan (gửi file để cập nhật).
- Sau scaffold: chạy `pytest` + mở Streamlit xác nhận DoD trước khi wire real.
- Rủi ro tiến độ: Tuần 5–6 peak của Member B; thứ tự cắt nếu kẹt: E2 → ablation reranker;
  giữ risk-coverage + Static-vs-Corrective bằng mọi giá.

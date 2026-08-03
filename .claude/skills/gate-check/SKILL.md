---
name: gate-check
description: >
  Dùng khi chạy hoặc diễn giải Gate 0/1/2, hoặc khi được hỏi "đã đủ điều kiện build
  chưa / can we start building / đã pass Gate chưa / gate check / kiểm tra gate /
  data sufficiency". Map kết quả sang verdict GO/NO-GO và cập nhật blocker của Member A.
  KHÔNG dùng để review diff (dùng contract-guard).
---

# gate-check

Chạy / diễn giải Gate, ánh xạ sang verdict cố định, cập nhật state.

## Khi nào chạy
- Chạy hoặc diễn giải Gate 0 (hoặc Gate 1/2 sau này).
- Câu hỏi "đã đủ điều kiện build chưa".

## Quy trình
1. Đọc `brain/contracts/gates.md` (tiêu chí + verdict scheme).
2. Nếu có script gate (`gate0_data_check.py`) → chạy; nếu không → yêu cầu người dùng
   chạy trên Kaggle/Colab rồi dán kết quả (script không chạy được lúc import/test theo constraint).
3. Map kết quả sang verdict **cố định**:
   - **GO** (pass cả 3) → được wire component thật; plan giữ nguyên.
   - **NO-GO #1** (corpus < 150/khoa) → bù `hungnm/vietnamese-medical-qa` hoặc đổi/gộp khoa.
   - **NO-GO #3** (alignment fail — đáp án không nằm trong corpus) → NGHIÊM TRỌNG, DỪNG;
     quyết eval strategy TRƯỚC khi viết dòng build nào.
4. Cập nhật dòng **Blocker** trong `brain/state/STATUS-A.md` theo verdict mới nhất.

## Output
- Verdict: `GO` | `NO-GO #1` | `NO-GO #3` + hành động kế tiếp tương ứng.
- Diff một dòng Blocker đã cập nhật trong `STATUS-A.md`.

## Cấm
- **Cấm tự quyết đổi dataset.** Đề xuất được, nhưng đổi corpus/eval là decision của người —
  ghi vào `DECISIONS.md` sau khi người chốt.

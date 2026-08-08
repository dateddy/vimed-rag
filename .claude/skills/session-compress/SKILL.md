---
name: session-compress
description: >
  Dùng ở cuối phiên, khi được yêu cầu "tổng kết session / tạo handoff / compress
  session / wrap up / summarize session / bàn giao / kết thúc phiên". Sinh handoff
  chỉ chứa state + việc treo, cập nhật DECISIONS/contracts/STATUS. KHÔNG dùng để review
  diff (contract-guard) hay chạy Gate (gate-check).
---

# session-compress

Nén cuối phiên thành handoff gọn + cập nhật đúng lớp.

## Khi nào chạy
- Cuối phiên; yêu cầu "tổng kết session", "tạo handoff", "bàn giao".

## Quy trình
1. Sinh `brain/handoff/YYYY-MM-DD-sessionNN.md` — **chỉ chứa state + việc treo**, ≤ 60 dòng:
   đang làm, blocker, việc kế tiếp, việc treo ngoài code. Không hơn.
2. Quyết định **mới** trong phiên → **append** vào `brain/decisions/DECISIONS.md`
   (dòng `DEC-00X` mới; không sửa dòng cũ).
3. Thay đổi **thiết kế** → sửa file tương ứng trong `brain/contracts/`.
4. Ghi đè `brain/state/STATUS.md` với trạng thái mới (file state DUY NHẤT — dự án 1 người, DEC-013).
5. Handoff cũ hơn 2 tuần → chuyển vào `brain/handoff/archive/`.

## Nguyên tắc bắt buộc
- **KHÔNG copy contract vào handoff.** Contract sống ở `brain/contracts/`; copy nó vào
  handoff tạo **hai nguồn sự thật** → drift. Handoff chỉ trỏ tới contract, không lặp lại.
- Handoff là ảnh chụp trạng thái, không phải tài liệu thiết kế.

## Output
- Đường dẫn file handoff mới.
- Danh sách file `brain/` đã cập nhật (DECISIONS / contracts / STATUS).

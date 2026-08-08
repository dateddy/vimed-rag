# brain/ — INDEX

Bản đồ lớp context. Tách theo **tốc độ thay đổi**, không theo chủ đề.

| File | Chứa gì | Đọc khi nào | Ai sở hữu | Vòng đời |
|---|---|---|---|---|
| `contracts/corrective-loop.md` | Pseudo-code corrective loop, 7 lớp defense-in-depth, DI, config-driven, stub discipline | Implement/review pipeline, hallucination | Đạt | Gần bất biến; đổi = đổi thiết kế |
| `contracts/constraints.md` | 6 ràng buộc Claude Code + trục đóng góp (claim được/bị cấm) | Trước khi commit, review diff | Đạt | Gần bất biến |
| `contracts/gates.md` | Gate 0 data-sufficiency: tiêu chí + verdict GO/NO-GO | Hỏi "đủ điều kiện build chưa" | Đạt | Gần bất biến |
| `decisions/DECISIONS.md` | Nhật ký quyết định append-only (DEC-00X) | Cần lý do một quyết định | Đạt | Append-only, không sửa dòng cũ |
| `state/STATUS.md` | Trạng thái hiện tại + backlog tiếp quản từ Member B | Đầu/cuối mỗi session | Đạt | Ghi đè mỗi session |
| `handoff/2026-08-07-session03.md` | Handoff Session 3 (Gate 0 GO + siết keyword) | Đầu phiên sau, cần biết dừng ở đâu | Đạt | Archive sau 2 tuần |
| `handoff/archive/2026-07-04-session02.md` | Handoff Session 2 (COMPRESS gốc) | Chỉ khi cần lịch sử | Đạt | Lưu trữ, đông cứng |

> **Dự án 1 người từ 2026-08-08** (DEC-013). `state/STATUS-B.md` đã xoá,
> `state/STATUS-A.md` → `state/STATUS.md`. Handoff cũ hơn ngày này còn nhắc "Member B" —
> đó là lịch sử, đừng làm theo.

## Quy tắc vận hành
- **State ghi đè**, không tạo `STATUS-v2`. **Một** file state duy nhất, không tách theo người.
- **Handoff** đặt tên `YYYY-MM-DD-sessionNN.md`; cũ hơn 2 tuần → chuyển vào `archive/`.
- File nào **2 tuần không mở → xóa**.

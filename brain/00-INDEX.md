# brain/ — INDEX

Bản đồ lớp context. Tách theo **tốc độ thay đổi**, không theo chủ đề.

| File | Chứa gì | Đọc khi nào | Ai sở hữu | Vòng đời |
|---|---|---|---|---|
| `contracts/corrective-loop.md` | Pseudo-code corrective loop, 7 lớp defense-in-depth, DI, config-driven, stub discipline | Implement/review pipeline, hallucination | Cả nhóm | Gần bất biến; đổi = đổi thiết kế |
| `contracts/constraints.md` | 6 ràng buộc Claude Code + trục đóng góp (claim được/bị cấm) | Trước khi commit, review diff | Cả nhóm | Gần bất biến |
| `contracts/gates.md` | Gate 0 data-sufficiency: tiêu chí + verdict GO/NO-GO | Hỏi "đủ điều kiện build chưa" | Cả nhóm | Gần bất biến |
| `decisions/DECISIONS.md` | Nhật ký quyết định append-only (DEC-00X) | Cần lý do một quyết định | Cả nhóm | Append-only, không sửa dòng cũ |
| `state/STATUS-A.md` | Trạng thái Member A (Đạt) | Đầu/cuối session của A | Member A | Ghi đè mỗi session |
| `state/STATUS-B.md` | Trạng thái Member B | Đầu/cuối session của B | Member B | Ghi đè mỗi session |
| `handoff/archive/2026-07-04-session02.md` | Handoff Session 2 (COMPRESS gốc) | Chỉ khi cần lịch sử | Cả nhóm | Lưu trữ, đông cứng |

## Quy tắc vận hành
- **State ghi đè**, không tạo `STATUS-v2`. Mỗi người 1 file, không sửa file của người kia.
- **Handoff** đặt tên `YYYY-MM-DD-sessionNN.md`; cũ hơn 2 tuần → chuyển vào `archive/`.
- File nào **2 tuần không mở → xóa**.

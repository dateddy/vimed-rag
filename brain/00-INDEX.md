# brain/ — INDEX

Bản đồ lớp context. Tách theo **tốc độ thay đổi**, không theo chủ đề.

| File | Chứa gì | Đọc khi nào | Ai sở hữu | Vòng đời |
|---|---|---|---|---|
| `contracts/corrective-loop.md` | Pseudo-code corrective loop, 7 lớp defense-in-depth, DI, config-driven, stub discipline | Implement/review pipeline, hallucination | Đạt | Gần bất biến; đổi = đổi thiết kế |
| `contracts/constraints.md` | 6 ràng buộc Claude Code + trục đóng góp (claim được/bị cấm) | Trước khi commit, review diff | Đạt | Gần bất biến |
| `contracts/gates.md` | Gate 0 data-sufficiency: tiêu chí + verdict GO/NO-GO | Hỏi "đủ điều kiện build chưa" | Đạt | Gần bất biến |
| `decisions/DECISIONS.md` | Nhật ký quyết định append-only (DEC-00X) | Cần lý do một quyết định | Đạt | Append-only, không sửa dòng cũ |
| `state/STATUS.md` | Trạng thái hiện tại + backlog tiếp quản từ Member B | Đầu/cuối mỗi session | Đạt | Ghi đè mỗi session |
| `../notebooks/kaggle_build_index.ipynb` | **Dây nối chạy embed+index trên Kaggle T4** — bản đã chạy thật, đã ra 2 collection | Khi chạy lại index | Đạt | Sống tới hết Tuần 3 |
| `../notebooks/colab_build_index.ipynb` | Bản Colab dự phòng — **CHƯA CHẠY THỬ BAO GIỜ**, phải soi lại trước khi tin | Chỉ khi Kaggle hết quota GPU | Đạt | Sống tới hết Tuần 3 |
| `handoff/2026-08-13-session07.md` | Handoff Session 7 (soi chunk xong · chunking chốt 512/50) | **Đầu phiên sau, cần biết dừng ở đâu** | Đạt | Archive sau 2 tuần |
| `handoff/2026-08-12-session06.md` | Handoff Session 6 (DoD Tuần 1 đóng · Qdrant Cloud · GVHD duyệt) | Chỉ khi cần lịch sử DEC-018/019 | Đạt | Archive sau 2 tuần |
| `handoff/2026-08-09-session05.md` | Handoff Session 5 (loader thật + corpus vào `data/processed/`) | Chỉ khi cần lịch sử DEC-017 | Đạt | Archive sau 2 tuần |
| `handoff/2026-08-08-session04.md` | Handoff Session 4 (solo + chốt chính sách gán khoa) | Chỉ khi cần lịch sử DEC-016 | Đạt | Archive sau 2 tuần |
| `handoff/2026-08-07-session03.md` | Handoff Session 3 (Gate 0 GO + siết keyword) — phần "Member B" đã hết hiệu lực | Chỉ khi cần lịch sử Gate 0 | Đạt | Archive sau 2 tuần |
| `handoff/archive/2026-07-04-session02.md` | Handoff Session 2 (COMPRESS gốc) | Chỉ khi cần lịch sử | Đạt | Lưu trữ, đông cứng |

> **Dự án 1 người từ 2026-08-08** (DEC-013). `state/STATUS-B.md` đã xoá,
> `state/STATUS-A.md` → `state/STATUS.md`. Handoff cũ hơn ngày này còn nhắc "Member B" —
> đó là lịch sử, đừng làm theo.

## Quy tắc vận hành
- **State ghi đè**, không tạo `STATUS-v2`. **Một** file state duy nhất, không tách theo người.
- **Handoff** đặt tên `YYYY-MM-DD-sessionNN.md`; cũ hơn 2 tuần → chuyển vào `archive/`.
- File nào **2 tuần không mở → xóa**.

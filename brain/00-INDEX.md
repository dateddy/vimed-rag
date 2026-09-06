# brain/ — INDEX

Bản đồ lớp context. Tách theo **tốc độ thay đổi**, không theo chủ đề.

| File | Chứa gì | Đọc khi nào | Ai sở hữu | Vòng đời |
|---|---|---|---|---|
| `contracts/corrective-loop.md` | Pseudo-code corrective loop, **8 lớp** defense-in-depth (policy gate — DEC-024), DI, config-driven, stub discipline | Implement/review pipeline, hallucination | Đạt | Gần bất biến; đổi = đổi thiết kế |
| `contracts/constraints.md` | 6 ràng buộc Claude Code + trục đóng góp (claim được/bị cấm) | Trước khi commit, review diff | Đạt | Gần bất biến |
| `contracts/gates.md` | Gate 0 data-sufficiency: tiêu chí + verdict GO/NO-GO | Hỏi "đủ điều kiện build chưa" | Đạt | Gần bất biến |
| `decisions/DECISIONS.md` | Nhật ký quyết định append-only (DEC-00X) | Cần lý do một quyết định | Đạt | Append-only, không sửa dòng cũ |
| `../config/abstention_policy.md` | **Chính sách từ chối v1.1** — 4 rule D-1…D-4, bản CÓ THẨM QUYỀN (nhãn nhóm D trỏ về nó) | Implement `check_policy()`, soạn thêm câu nhóm D | Đạt | Đổi = tăng version = soát lại nhãn D |
| `../config/abstention_policy.yaml` | Bản dịch regex của policy để chạy được (DEC-031) | Tuần 4–5 khi wire policy gate | Đạt | Phải cùng version với bản `.md` |
| `../data/testset.jsonl` | **Safety subset 50 câu** A18/B12/D8/E12 — deliverable Tuần 5 | Tuần 3 (recall@k) · Tuần 6 (abstention P/R) | Đạt | Đóng; đổi = chạy lại nghiệm thu |
| `state/STATUS.md` | Trạng thái hiện tại + 3 mục "đã biết, đừng làm lại" + backlog | Đầu/cuối mỗi session | Đạt | Ghi đè mỗi session |
| `../notebooks/kaggle_build_index.ipynb` | **Dây nối chạy embed+index trên Kaggle T4** — bản đã chạy thật, đã ra 2 collection | Khi chạy lại index | Đạt | Sống tới hết Tuần 3 |
| `../notebooks/colab_build_index.ipynb` | Bản Colab dự phòng — **CHƯA CHẠY THỬ BAO GIỜ**, phải soi lại trước khi tin | Chỉ khi Kaggle hết quota GPU | Đạt | Sống tới hết Tuần 3 |
| `handoff/2026-08-23-session09.md` | Handoff Session 9 (**safety subset đóng 50/50 · policy gate vào contract · việc 1.4 đóng**) | **Đầu phiên sau, cần biết dừng ở đâu** | Đạt | Archive sau 2 tuần |
| `handoff/2026-08-18-session08.md` | Handoff Session 8 (Tuần 2 đóng · 2 collection đã index + verify PASS) | Chỉ khi cần lịch sử DEC-021 | Đạt | Archive sau 2 tuần |
| `handoff/2026-08-13-session07.md` | Handoff Session 7 (soi chunk xong · chunking chốt 512/50) | Chỉ khi cần lịch sử DEC-020 | Đạt | Archive sau 2 tuần |
| `handoff/2026-08-12-session06.md` | Handoff Session 6 (DoD Tuần 1 đóng · Qdrant Cloud · GVHD duyệt) | Chỉ khi cần lịch sử DEC-018/019 | Đạt | Archive sau 2 tuần |
| `handoff/archive/` | Session 02–05 (COMPRESS gốc · Gate 0 GO · solo + chính sách gán khoa · loader thật) | Chỉ khi cần lịch sử DEC-016/017 | Đạt | Lưu trữ, đông cứng |

> **Dự án 1 người từ 2026-08-08** (DEC-013). `state/STATUS-B.md` đã xoá,
> `state/STATUS-A.md` → `state/STATUS.md`. Handoff cũ hơn ngày này còn nhắc "Member B" —
> đó là lịch sử, đừng làm theo.

## Quy tắc vận hành
- **State ghi đè**, không tạo `STATUS-v2`. **Một** file state duy nhất, không tách theo người.
- **Handoff** đặt tên `YYYY-MM-DD-sessionNN.md`; cũ hơn 2 tuần → chuyển vào `archive/`.
- File nào **2 tuần không mở → xóa**.

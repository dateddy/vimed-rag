---
name: contract-guard
description: >
  Dùng TRƯỚC khi commit, khi review diff, hoặc khi được hỏi "thay đổi này có vi phạm
  thiết kế không / does this change violate the contract / check contract / kiểm tra
  ràng buộc / contract guard". Đối chiếu diff với brain/contracts. KHÔNG dùng để viết
  code mới hay để chạy Gate 0 (dùng gate-check cho Gate).
---

# contract-guard

Read-only. Đối chiếu diff hiện tại với contract. **Không tự sửa code.**

## Khi nào chạy
- Trước khi commit.
- Khi review một diff.
- Khi có câu hỏi "thay đổi này có vi phạm thiết kế / contract không".

## Quy trình
1. Đọc `brain/contracts/constraints.md` và `brain/contracts/corrective-loop.md`.
2. Lấy diff (`git diff` nếu có git; nếu không, xem các file vừa sửa).
3. Đối chiếu từng thay đổi với các điều khoản. Đặc biệt soi:
   - LangGraph/LangChain xuất hiện trong orchestration → VIOLATION.
   - Gọi model/dataset thật lúc import hoặc test → VIOLATION.
   - Ingestion data thật khi Gate 0 chưa GO → VIOLATION.
   - Grader gọi LLM, hoặc `max_iter` ≠ 1 → VIOLATION.
   - Magic number ngưỡng thay vì đọc từ `config/` → VIOLATION.
   - Ghi đè file đã tồn tại mà không đọc trước → VIOLATION.
4. Nếu diff **chạm contract** (`brain/contracts/*`, orchestration, grader, gates)
   mà **không có decision ID** kèm theo trong `brain/decisions/DECISIONS.md`
   → **FAIL** và yêu cầu bổ sung một dòng `DEC-00X` trước khi commit.

## Output — bảng
```
PASS / VIOLATION | file:line | điều khoản bị vi phạm
```
Kết luận cuối: `ALL PASS` hoặc `BLOCK COMMIT — <n> violation(s)`.

## Cấm
- Không tự sửa code, không tự thêm dòng DECISIONS — chỉ báo cáo và yêu cầu.

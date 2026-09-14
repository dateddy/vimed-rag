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
| `../01_OPEN_ISSUES.md` | **Nhật ký audit** — ISSUE-069…075 kèm reproducer chạy được + risk_accepted + rollback point. **Hiện 0 issue còn mở** | Sau mỗi vòng review, hoặc khi nghi một con số | Đạt | Append; đóng issue thì ghi trạng thái, đừng xoá |
| `state/STATUS.md` | Trạng thái hiện tại + 3 mục "đã biết, đừng làm lại" + backlog | Đầu/cuối mỗi session | Đạt | Ghi đè mỗi session |
| `../notebooks/kaggle_build_index.ipynb` | **Dây nối chạy embed+index trên Kaggle T4** — bản đã chạy thật, đã ra 2 collection | Khi chạy lại index | Đạt | Sống tới hết Tuần 3 |
| `../notebooks/colab_build_index.ipynb` | Bản Colab dự phòng — **CHƯA CHẠY THỬ BAO GIỜ**, phải soi lại trước khi tin | Chỉ khi Kaggle hết quota GPU | Đạt | Sống tới hết Tuần 3 |
| `../deploy/hf-space/` | **Dây chuyền deploy HF Space** — `Dockerfile` (Streamlit không còn là SDK) · `README.md` (frontmatter `sdk: docker`, `app_port: 7860`) · `requirements.txt` (torch CPU, KHÁC bản gốc có chủ ý) · `DEPLOY.md` 7 bước đã chạy thật | Khi đẩy lại Space, hoặc dựng lại từ đầu | Đạt | Sống tới hết Tuần 8 |
| `handoff/2026-09-15-session17.md` | Handoff Session 17 (**rủi ro demo số 1 ĐÓNG · Space RUNNING cpu-basic 15,9 s · DEC-071 tách key theo quyền · DEC-072 · 5 bẫy nền tảng: HF bỏ SDK streamlit, PRO $9, BOM của PowerShell…**) | **Đầu phiên sau, cần biết dừng ở đâu** | Đạt | Archive sau 2 tuần |
| `handoff/2026-09-14-session16.md` | Handoff Session 16 (**TUẦN 6 ĐÓNG 3/3 · lô RAGAS xong, p = 0,0042 trên 16 cặp · ISSUE-069 đóng · audit ra ISSUE-073/074/075 vá cả 3**) | Cần lịch sử DEC-070 | Đạt | Archive sau 2 tuần |
| `handoff/2026-09-13-session15.md` | Handoff Session 15 (RAGAS code xong lô chấm dở 403 · Faithfulness phạt câu từ chối 0,0 · B1 Wilson · B4 hai tầng · audit B2 ra ISSUE-069) ⚠️ **số ghép cặp trong file này là của lô DỞ — lịch sử, đừng trích** | Cần lịch sử DEC-064…069 | Đạt | Archive sau 2 tuần |
| `handoff/2026-09-11-session14.md` | Handoff Session 14 (TUẦN 6 việc (2) đóng · risk–coverage đổi vai · vách 3,056 logit) | Cần lịch sử DEC-063 | Đạt | Archive sau 2 tuần |
| `handoff/2026-09-10-session13.md` | Handoff Session 13 (TUẦN 6 việc (1) đóng · guard lượt 2 đưa leakage 7%→0 · soi tay 30 câu A/B) | Cần lịch sử DEC-059…062 | Đạt | Archive sau 2 tuần |
| `handoff/2026-09-08-session12.md` | Handoff Session 12 (Tuần 5 đóng · leakage sau rewrite 2/30 · vòng corrective cứu 0 lọt 2) | Cần lịch sử DEC-056…058 | Đạt | Archive sau 2 tuần |
| `handoff/2026-09-08-session11.md` | Handoff Session 11 (Tuần 4 đóng · OpenRouter · phương án B đo xong) | Cần lịch sử DEC-044…055 | Đạt | Archive sau 2 tuần |
| `handoff/2026-09-07-session10.md` | Handoff Session 10 (**TUẦN 3 ĐÓNG · nhóm E 12→21 · 2 claim bị dữ liệu bác bỏ**) | Cần lịch sử DEC-033…043 | Đạt | Archive sau 2 tuần |
| `handoff/archive/` | Session 02–09 (COMPRESS gốc · Gate 0 · solo · loader · Tuần 1 · chunking 512/50 · Tuần 2 index · safety subset) | Chỉ khi cần lịch sử DEC-016…021, 022…031 | Đạt | Lưu trữ, đông cứng |

> **Dự án 1 người từ 2026-08-08** (DEC-013). `state/STATUS-B.md` đã xoá,
> `state/STATUS-A.md` → `state/STATUS.md`. Handoff cũ hơn ngày này còn nhắc "Member B" —
> đó là lịch sử, đừng làm theo.

## Quy tắc vận hành
- **State ghi đè**, không tạo `STATUS-v2`. **Một** file state duy nhất, không tách theo người.
- **Handoff** đặt tên `YYYY-MM-DD-sessionNN.md`; cũ hơn 2 tuần → chuyển vào `archive/`.
- File nào **2 tuần không mở → xóa**.

# DECISIONS — nhật ký quyết định (append-only)

> **Append-only. KHÔNG sửa dòng cũ.** Muốn đảo một quyết định → thêm dòng MỚI với
> `Supersedes: DEC-00X`, để dòng cũ nguyên vẹn làm lịch sử.
>
> Cột "Ai quyết": `A` = Đạt. (Trước 2026-08-08 `A` = Member A, `B` = Member B —
> từ DEC-013 dự án còn **1 người**, mọi dòng mới đều là `A`.)

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
| DEC-007 | 2026-08-07 | **Gate 0 = GO.** Chốt ngưỡng eval = **40 QA** và định nghĩa **NO-GO #2**; đóng 3 `TODO(unknown)` ở `gates.md` | Pass cả 3 tiêu chí, không cái nào ở biên (coverage dư ~100×, alignment 30/30). Ngưỡng 40 lấy từ `MIN_EVAL_QA_TOTAL` trong chính script mà contract trỏ tới, không phải số bịa | A | — |
| DEC-008 | 2026-08-07 | Corpus = split **`vinmec_article_content`** (32,604 bài), KHÔNG phải `train` | Split `train` **không tồn tại** trong `urnus11/Vietnamese-Healthcare`. Chọn `article_content` vì đúng nghĩa "bài" của tiêu chí #1 + đúng deliverable Tuần 1. Bỏ `vinmec_article_subtitle` (163k mục con — sát chunk hơn nhưng đếm sai đơn vị "bài") | A | — |
| DEC-009 | 2026-08-07 | Eval = **`tmnam20/ViMedAQA`** split `train`, config `all` | Giải placeholder `"ViMedAQA"` thành path HF thật đã verify (public, không gated). Nguồn youmed.vn — **khác nguồn corpus** (vinmec.com), xem giới hạn #1 trong `gates.md` | A | — |
| DEC-010 | 2026-08-07 | Siết `config/specialties.yaml`: bỏ từ đơn (`tim`, `động mạch`, `tai biến`, `nhồi máu`, `loạn nhịp`, `xơ vữa`, `đái tháo`), thay bằng cụm đặc hiệu; bỏ 6 keyword thừa (`solo=0`) | Audit trên 32,543 bài thật: `tai biến` bắt "tai biến gây mê/mổ lấy thai" (sản, gây mê), `động mạch` bắt "động mạch lách/phế quản", `đái tháo` bắt **`đái tháo nhạt`** (bệnh tuyến yên, khác hẳn), `tim` bắt **`tim thai`** (sản). Gate 0 alignment vẫn PASS sau khi siết | A | — |
| DEC-011 | 2026-08-07 | **Đột quỵ KHÔNG thuộc `tim_mach`** | Phân khoa VN xếp đột quỵ vào thần kinh; giữ scope 2 khoa sạch để hội đồng không hỏi "sao bài thần kinh nằm trong corpus tim mạch". Muốn theo CVD của WHO thì thêm lại 2 dòng đã ghi sẵn trong file | A | — |
| DEC-012 | 2026-08-07 | **Chạy lại Gate 0 sau mỗi lần đổi `specialties.yaml`**; verdict vẫn GO sau DEC-010/011 | Siết keyword làm eval tụt 3,423 → 2,645 QA và corpus 16,869 → 14,618 bài. Verdict cũ đo trên từ vựng cũ nên hết hiệu lực nếu không chạy lại. 3 script audit (`policy_audit` · `kw_audit` · `alignment_audit`) đưa vào `scripts/` để tái lập được | A | — |
| DEC-013 | 2026-08-08 | **Dự án còn 1 người (Đạt).** Toàn bộ workstream của Member B (generation · test set · eval/RAGAS · UI · báo cáo) chuyển về Đạt. Xoá `state/STATUS-B.md`, đổi `state/STATUS-A.md` → `state/STATUS.md`; bỏ vai "Member A/B" khỏi `CLAUDE.md`, `00-INDEX.md`, plan | Member B rời dự án. Giữ 2 file state cho 1 người là nợ context: mỗi session phải đọc 1 file trống rồi đoán "trống = chưa làm" hay "trống = không còn ai". Scope kỹ thuật **không đổi** — chỉ đổi ai làm và lịch | A | — |
| DEC-014 | 2026-08-08 | **Bỏ Cohen's κ. Bỏ nhóm C** khỏi safety subset; giữ 4 nhóm **A18 / B12 / D8 / E12 = 50 câu** | κ là *inter-annotator* agreement — cần 2 người gán độc lập, 1 người thì đại lượng này không tồn tại (test–retest tự gán chỉ đo trí nhớ của chính mình). Nhóm C ("thiếu thông tin") là nhóm DUY NHẤT mà nhãn đến từ phán đoán người, không kiểm chứng được bằng máy hay policy → bỏ C là mất ít nhất mà cứu được nguyên tắc "mọi nhãn đều kiểm chứng được": A/B bằng script, D bằng policy tự công bố, E bằng ViMedAQA ground truth. Giữ tổng 50 bằng cách dồn sang A/B/E (rẻ, sinh bằng script). **Limitations phải ghi: không có inter-annotator agreement** | A | DEC-005 (phần κ + nhóm C) |
| DEC-015 | 2026-08-08 | Giữ **nguyên scope**; thứ tự cắt khi kẹt vẫn là E2 evidence-highlighting → ablation reranker on/off → ablation chunk 256 vs 512. **Chưa cắt gì lúc này** | Năng lực giảm 1/2 nhưng thứ tự ưu tiên đã đúng từ trước (DEC-006), không cần quyết định mới. Cắt sớm khi chưa biết trượt bao nhiêu = vứt kết quả không cần thiết. Chốt điểm kiểm tra: **hết Tuần 5 mà safety subset chưa có nhãn → cắt E2 ngay**, không chờ tới Tuần 7 | A | — |

<!-- TODO(unknown): ngày chính xác các quyết định — COMPRESS ghi "session này" (Session 2);
     dùng 2026-07-04 khớp tên file handoff archive. Xác nhận nếu cần ngày thật. -->

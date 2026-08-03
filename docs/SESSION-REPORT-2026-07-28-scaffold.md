# Session Report — Scaffold External Brain + Skills (ViMed-RAG)

**Ngày:** 2026-07-28
**Task:** Dựng lớp context (external brain) + skills, migrate nội dung từ `COMPRESS-ViMed-RAG-Session2.md`.
**Loại:** Tổ chức tài liệu (KHÔNG viết code sản phẩm).

---

## 1. TL;DR

Đã dựng xong toàn bộ cây `CLAUDE.md` + `brain/**` + 3 skill mới + `docs/`, migrate nguyên vẹn
nội dung COMPRESS vào đúng lớp. **2 tiền đề ban đầu FAIL** (không phải git repo; thiếu skill
`git-commit`) → đã hỏi và làm theo lựa chọn của user (tạo file, không git; bỏ qua precommit scan).
Các bước git/scan cuối **chưa chạy**. Nội dung vẫn nằm nguyên trên đĩa, chưa commit.

---

## 2. ĐÃ THỰC HIỆN (Done)

### Tiền đề đã kiểm
| Tiền đề | Lúc chạy scaffold | Hiện tại (2026-07-28) |
|---|---|---|
| Repo root đúng | ✅ | ✅ |
| `COMPRESS-...md` tồn tại | ✅ | ✅ (đã move vào archive) |
| Là git repo (`.git`) | ❌ MISSING | ✅ ĐÃ CÓ (user thêm sau) |
| Skill `git-commit` | ❌ MISSING | ✅ ĐÃ CÓ (user thêm sau) |

### File đã tạo (13 mục)
- `CLAUDE.md` — entry point, **41 dòng** (cap ≤80).
- `brain/00-INDEX.md` — bản đồ + 3 quy tắc vận hành.
- `brain/contracts/corrective-loop.md` — migrate COMPRESS §4+§5 nguyên vẹn.
- `brain/contracts/constraints.md` — migrate §8 + §2 (claim được/bị cấm), dạng checklist.
- `brain/contracts/gates.md` — Gate 0 từ §7, đánh dấu **CHƯA CHẠY**.
- `brain/decisions/DECISIONS.md` — append-only, seed **DEC-001…DEC-006** từ §3.
- `brain/state/STATUS-A.md` — điền thật từ §1,6,7,9; blocker = Gate 0.
- `brain/state/STATUS-B.md` — template rỗng có cấu trúc + khóa owner.
- `.claude/skills/contract-guard/SKILL.md`
- `.claude/skills/gate-check/SKILL.md`
- `.claude/skills/session-compress/SKILL.md`
- `docs/.gitkeep`
- `brain/prompts/` — thư mục rỗng (xem mục MISS).

### Di chuyển
- `COMPRESS-ViMed-RAG-Session2.md` → `brain/handoff/archive/2026-07-04-session02.md`
  (bằng `mv`; prepend 2 dòng header; nội dung giữ nguyên; xóa bản gốc).

### Self-check (output thật)
| Check | Kết quả | Cap | Đạt? |
|---|---|---|---|
| `wc -l CLAUDE.md` | 41 | ≤80 | ✅ |
| `find brain -type f \| wc -l` | 8 | ≤8 | ✅ |
| `ls .claude/skills` (lúc đó) | 3 dir | =4 | ❌ (thiếu git-commit) |
| `grep TODO(unknown) brain/` | 4 hit | — | ✅ liệt kê đủ |
| `head -3` mỗi SKILL.md | frontmatter hợp lệ | — | ✅ |

---

## 3. CHƯA THỰC HIỆN / MISS

| # | Hạng mục | Lý do | Trạng thái để đóng |
|---|---|---|---|
| M1 | `brain/prompts/.gitkeep` | Tạo sẽ làm `find brain -type f` = 9, vỡ cap ≤8; lúc đó chưa có git nên `.gitkeep` vô nghĩa | Nay đã có git → có thể thêm `.gitkeep` nếu muốn track thư mục rỗng |
| M2 | `git add` + `git status --porcelain` (bước 5–6) | Lúc chạy chưa có `.git`; user chọn "tạo file, không git" | Nay đã có git → có thể stage lại |
| M3 | Precommit scan (`precommit_scan.py`) | Lúc chạy thiếu skill `git-commit`; user chọn bỏ qua | Nay skill đã có → chạy được |
| M4 | `git commit` | Constraint cấm tự commit; và chưa có git lúc đó | Chờ user xác nhận |
| M5 | Verdict "đúng 4 skill" | `git-commit` chưa cài lúc self-check | Nay đã đủ (5 skill: git-commit, contract-guard, gate-check, session-compress, code-review) |

### TODO(unknown) còn treo trong brain/ (thiếu dữ kiện trong COMPRESS)
1. `gates.md` — Tiêu chí "Eval set" fail thì map sang verdict nào? (COMPRESS không nêu)
2. `gates.md` — Ngưỡng số cho "eval set" (số câu tối thiểu). (Không có số)
3. `gates.md` — "NO-GO #2" chưa được định nghĩa (scheme chỉ có #1 và #3).
4. `DECISIONS.md` — Ngày chính xác DEC-001…006 (dùng tạm 2026-07-04 khớp tên file archive).

---

## 4. ĐỀ XUẤT BƯỚC KẾ TIẾP (Recommended next)

Vì `.git` và `git-commit` giờ đã có, có thể hoàn tất phần trước bị bỏ:
1. (Tùy chọn) Thêm `brain/prompts/.gitkeep` để track thư mục — nếu thêm, cap ≤8 không còn ràng buộc vì task đã xong.
2. `git add CLAUDE.md brain .claude/skills docs`
3. Chạy `git-commit` skill (gồm secret/conflict scan) rồi commit với message:
   `docs(brain): scaffold external-brain context layer + contract/gate/compress skills`
4. Giải quyết 4 TODO(unknown) ở gates.md/DECISIONS.md khi có dữ kiện.

## 5. RÀNG BUỘC ĐÃ TÔN TRỌNG
- Không động vào `src/ tests/ config/ scripts/`. ✅
- Không ghi đè file đã tồn tại (không file nào pre-existed). ✅
- Không bịa nội dung dự án — mọi fact trích từ COMPRESS; chỗ thiếu ghi TODO(unknown). ✅
- Không tạo quá 8 file brain / quá 4 skill. ✅
- Không commit, không push. ✅

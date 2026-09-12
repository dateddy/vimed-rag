
### ISSUE-069 · Dong provenance trong bao cao bao phu ca so lieu CHUA duoc duyet

- **Severity**: HIGH
- **Status**: DECISION_PENDING
- **Component**: eval
- **Description**:
  docs/static-vs-corrective.md:122 ghi '**Nguoi gan nhan:** dat (duyet 2026-09-12). Nhan o data/static_leak_review.jsonl.' Dong nay dung dau muc '### Da soi tay — ket qua tang noi dung'. Nhung bang DO NHAY o dong 150-153 (3/22 = 14%, 3/19 = 16%) KHONG lay tu file do — no lay tu data/concept_variants.jsonl, ma ca 30 ban ghi cua file do van co classified_by = 'claude-draft-pass'. Nguoi doc thay MOT dong 'nguoi gan nhan' o dau muc va hieu la moi con so duoi do da duoc duyet.
- **Impact**:
  DEC-014 dat provenance thanh MOT PHAN CUA KET QUA. Mot muc bao cao trinh so lieu dan xuat tu nhan chua duyet duoi mot dong 'da duyet' la mo ta SAI provenance — dung loai loi ma DEC-014 sinh ra de chan. So chinh 20% thi HOP LE; hai dong do nhay thi chua.
- **Reproducer**:
  ```bash
  python -c "import json,pathlib; doc=pathlib.Path('docs/static-vs-corrective.md').read_text(encoding='utf-8'); cv=[json.loads(l) for l in open('data/concept_variants.jsonl',encoding='utf-8') if l.strip()]; draft=[r['id'] for r in cv if 'draft' in str(r.get('classified_by',''))]; assert 'dat (duyet' in doc.replace(chr(7879),'e') or 'dat (' in doc; assert '3/22 = **14%**' in doc; assert len(draft)==30, draft; print('FAIL: doc ghi da duyet nhung bang do nhay dua tren', len(draft), 'nhan classified_by=claude-draft-pass')"
  ```
- **Hypothesized cause**:
  ISSUE-072: classified_by khong duoc bat ky doan code nao doc, nen --approve khong cham toi no va --tally khong to ra duoc

<!-- emitted 2026-09-13 -->

---

### ISSUE-070 · STATUS.md mo ta mot trang thai da khong con ton tai

- **Severity**: MEDIUM
- **Status**: OPEN
- **Component**: repro
- **Description**:
  brain/state/STATUS.md:621 van ghi 'data/static_leak_review.jsonl 30/30 dong van labeled_by: claude-draft-pass' va 'Con so 20% ... chua duoc phep trich cho toi khi Dat doc lai'. Ca hai deu SAI tu 2026-09-12. STATUS tu khai o dong 3-4 rang no la 'state DUY NHAT, ghi de moi session' — tuc file trang thai HIEN TAI, khong phai lich su. (DECISIONS.md:82 va hai file handoff cung chua chuoi do nhung DUNG: chung la lich su append-only, phai giu nguyen.)
- **Impact**:
  Phien sau doc STATUS se tuong B2 con treo va co the di duyet lai lan hai, hoac nguoc lai khong dam trich con so 20% da hop le. Day dung la loai no context ma brain/ sinh ra de tranh.
- **Reproducer**:
  ```bash
  grep -n 'van .labeled_by: claude-draft-pass' brain/state/STATUS.md
  ```

<!-- emitted 2026-09-13 -->

---

### ISSUE-071 · Bo sinh worksheet hard-code mot cau da tro thanh sai

- **Severity**: MEDIUM
- **Status**: OPEN
- **Component**: eval
- **Description**:
  scripts/review_static_leaks.py:321 hard-code chuoi 'Nhan hien tai do **Claude gan nhap** (labeled_by: claude-draft-pass) va vi the con so **20%** ... **chua duoc phep trich vao bao cao**'. Chuoi nay duoc in ra bat ke provenance THAT trong file nhan la gi. Chay lai --worksheet HOM NAY van sinh ra cau do, trong khi nhan da duoc duyet.
- **Impact**:
  Phieu la thu nguoi doc de quyet dinh co trich so hay khong. Mot phieu noi 'chua duoc phep trich' trong khi da duoc phep se hoac chan mot con so hop le, hoac day nguoi dung di duyet lai lan hai. Sinh ra sau moi lan chay, nen no se lap lai mai.
- **Reproducer**:
  ```bash
  python scripts/review_static_leaks.py --worksheet >/dev/null 2>&1 && grep -n 'chua duoc phep trich' data/processed/static_leak_worksheet.md
  ```
- **Hypothesized cause**:
  Van ban trang thai duoc viet thanh hang so thay vi doc tu truong labeled_by cua chinh file nhan

<!-- emitted 2026-09-13 -->

---

### ISSUE-072 · concept_variants.jsonl khong co duong nao de lo ra provenance cua no

- **Severity**: MEDIUM
- **Status**: OPEN
- **Component**: eval
- **Description**:
  grep -rn classified_by src/ scripts/ tra ve 0 ket qua. Truong provenance cua data/concept_variants.jsonl khong duoc doc boi bat ky doan code nao: --tally in 'Ai gan nhan' chi tu static_leak_review.jsonl (review_static_leaks.py:270), --approve chi dong dau len static_leak_review.jsonl, va build_arms_table/arms.py khong dung classified_by. Doi lai, static_leak_review.jsonl thi CO duong do.
- **Impact**:
  Day la NGUYEN NHAN GOC cua ISSUE-069. Co che duy nhat du an dung de lam provenance hien ra lai co dung mot diem mu — va diem mu do nam chinh xac o file con giu nhan chua duyet. Khong ai thay duoc dieu do tru khi mo file len doc tay.
- **Reproducer**:
  ```bash
  test 0 -eq $(grep -rn 'classified_by' --include='*.py' src/ scripts/ | wc -l) && echo 'FAIL: 0 cho code doc classified_by'
  ```

<!-- emitted 2026-09-13 -->

---

---

## Cập nhật sau vòng vá — 2026-09-13

**Rollback point:** `488e125` (commit nhãn đã duyệt của Đạt, trước mọi thay đổi code).

| ISSUE | Trạng thái | Cách đóng |
|---|---|---|
| **069** | `FIX_IN_PROGRESS` | Báo cáo nay gắn provenance với **từng con số** (`_dong_provenance()`), không gắn với cả mục. **Chờ Đạt duyệt `concept_variants.jsonl` mới chuyển RESOLVED** |
| **070** | `RESOLVED` | `STATUS.md` viết lại: nửa đầu B2 xong, nửa sau còn treo, kèm 2 bẫy |
| **071** | `RESOLVED` | `worksheet()` đọc provenance thật thay vì hard-code; chạy lại ra "✅ đã được duyệt" |
| **072** | `RESOLVED` | Thêm bảng `NHAN` + `doc_provenance()`; `--tally` nay tố ra file nào còn nháp; `--approve` phủ cả hai file |

**risk_accepted:**
- R1 (đè ngày duyệt cũ) → MITIGATE: `--approve` chỉ đóng dấu bản ghi còn nháp. Khoá bằng `test_chi_dong_dau_ban_ghi_con_nhap` + `test_chay_lai_khong_doi_gi`.
- R2 (hỏng khuôn JSONL) → MITIGATE: mọi đường ghi qua `ghi_jsonl()`. Verify sau khi chạy: 30/30 dòng cả hai file, `git status data/` sạch.
- R3 (đổi output docs) → ACCEPT có điều kiện, **đã verify: 0 con số đổi**, chỉ dòng provenance thành bảng.
- R4/R5 (phiếu dụ bỏ câu / gộp lớp) → MITIGATE: phiếu variants ghi rõ 2 bẫy ở đầu.

**Lỗi mới bắt được trong lúc vá:** `approve()` gọi `relative_to(ROOT)` → ném `ValueError` với path ngoài repo. Một hàm đang đóng dấu nhãn mà chết vì định dạng chuỗi là hỏng sai chỗ. Đã tách thành `ten_ngan()`. Bắt được nhờ `tests/test_provenance.py` ngay lượt chạy đầu.

**Còn lại để đóng ISSUE-069:** Đạt đọc `data/processed/concept_variants_worksheet.md` rồi chạy `python scripts/review_static_leaks.py --approve --reviewer dat`.

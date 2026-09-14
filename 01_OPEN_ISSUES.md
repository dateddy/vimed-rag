
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

### ISSUE-073 · Canh bao lo cham dung giua chung o 403 in vo dieu kien, nay da thanh sai

- **Severity**: HIGH
- **Status**: OPEN
- **Component**: eval
- **Description**:
  scripts/build_ragas_report.py:305-308 append cau canh bao DUNG so hai trung binh roi ... (lo cham dung giua chung o 403) ngay khi co bang ghep cap, khong gan voi bien trang thai nao. Sau khi lo chay xong (corrective 17/17, llm_only 16/16, unscored=0) va voi --pairable-only, hai trung binh roi 0.747 va 0.481 CHINH LA hai trung binh ghep cap tren cung 16 cau. Cau canh bao nay nay sai, va mau thuan voi bang Tinh trang cham ngay duoi no trong cung file — khoi Lo cham CHUA XONG o dong 361 co dieu kien if s_corr.unscored or s_base.unscored nen da tu tat dung thiet ke.
- **Impact**:
  docs/ragas.md la tai lieu dem ra hoi dong. No dang bao nguoi doc rang bang ket qua chinh KHONG doc duoc, va vien dan mot su co (403 het credit) da khong con ton tai. Nguoi doc hoac bo qua ket qua that (p=0.0042, n=16), hoac hieu nham rang lo cham van con do. Cung lop loi voi ISSUE-071: cau van hard-code song sot qua chinh su kien lam no sai.
- **Reproducer**:
  ```bash
  python -c "import io;d=io.open('docs/ragas.md',encoding='utf-8').read();stale='403),' in d;done=('17/17' in d) and ('16/16' in d);print(('FAIL' if (stale and done) else 'PASS'),'canh_bao_lo_do=',stale,'bang_noi_da_xong=',done)"
  ```
- **Hypothesized cause**:
  Cau canh bao hard-code trong nhanh if pc[n] ma khong kiem trang thai unscored, trong khi khoi ngay duoi no lam dung
- **Linked to**: ISSUE-071

<!-- emitted 2026-09-14 -->

---

### ISSUE-074 · Muc Tai lap cua docs/ragas.md ghi thieu co --pairable-only, chay theo no ra so khac va ton tien that

- **Severity**: HIGH
- **Status**: OPEN
- **Component**: repro
- **Description**:
  scripts/build_ragas_report.py in khoi Tai lap co dinh la python scripts/build_ragas_report.py, trong khi tai lieu hien tai duoc sinh boi lenh co --pairable-only. Chay dung lenh ghi trong doc thi nhanh llm_only mo rong tu 16 cau ghep cap len toan bo 51 cau: bang doi thanh 18/51 da cham va 33 chua cham, muc ghep cap doi mau, va script goi 33 luot API that.
- **Impact**:
  Tai lieu noi sai ve cach sinh ra chinh no. Nguoi lam theo huong dan se (a) khong tai lap duoc con so in trong file, (b) tieu khoang 3.6 USD o gia do duoc 0.11 USD moi cau, (c) ghi de docs/ragas.md thanh khung lo cham do trong khi lo da xong. Da xay ra that trong phien audit 2026-09-14.
- **Reproducer**:
  ```bash
  python -c "import io,re;d=io.open('docs/ragas.md',encoding='utf-8').read();m=re.search(r'\x60\x60\x60\n(python scripts/build_ragas_report\.py[^\n]*)\n\x60\x60\x60',d);cmd=m.group(1) if m else '';bad=('16/16' in d) and ('--pairable-only' not in cmd);print(('FAIL' if bad else 'PASS'),'| Tai_lap ghi:',repr(cmd))"
  ```
- **Hypothesized cause**:
  Khoi Tai lap hard-code chuoi lenh thay vi in lai tham so that su da dung de sinh bao cao

<!-- emitted 2026-09-14 -->

---

### ISSUE-075 · Bang 4 nhanh hua o nay do RAGAS lap — loi hua khong thuc hien duoc

- **Severity**: MEDIUM
- **Status**: OPEN
- **Component**: eval
- **Description**:
  scripts/build_arms_table.py sinh chu thich cho o trong cua nhanh llm_only: (can RAGAS) nghia la o nay do RAGAS faithfulness (viec 3 cua Tuan 6) lap. RAGAS da xong 2026-09-14 (corrective 17/17, llm_only 16/16) nhung hai o Leakage A/B va Coverage E cua nhanh llm_only VAN trong — va phai trong: faithfulness 0.481 do muc bam ngu canh, khong phai leakage cung khong phai coverage. Chinh docs/ragas.md canh bao DUNG de faithfulness ganh claim ve hallucination.
- **Impact**:
  Tuan 6 nhin nhu con thieu viec trong khi no da xong 3/3. Hoi dong doc bang se di tim o duoc lap va khong thay. Rui ro nang hon: ai do lap o bang con so faithfulness — dung cai tron metric ma docs/ragas.md cam bang mot canh bao rieng.
- **Reproducer**:
  ```bash
  python -c "import io;a=io.open('docs/static-vs-corrective.md',encoding='utf-8').read();r=io.open('docs/ragas.md',encoding='utf-8').read();promise=('RAGAS faithfulness' in a) and ('lấp' in a);done='16/16' in r;print(('FAIL' if (promise and done) else 'PASS'),'| bang_con_hua=',promise,'| ragas_da_xong=',done)"
  ```
- **Hypothesized cause**:
  Chu thich viet luc chua biet RAGAS se tra ve metric loai gi; DEC-065 sau do chot chi lay Faithfulness nhung chu thich khong duoc cap nhat theo
- **Linked to**: DEC-065

<!-- emitted 2026-09-14 -->

---

## Cập nhật sau vòng vá — 2026-09-14 (audit Tuần 6)

**Rollback point:** `271dd9a`. ⚠️ Lúc vá, working tree **đang dirty 3 file của Đạt**
(`data/concept_variants.jsonl` nhãn vừa duyệt · `docs/ragas.md` · `docs/static-vs-corrective.md`
lô chấm vừa xong). Rollback **chỉ** được nhắm vào file code:
`git checkout -- src/eval/arms.py scripts/build_ragas_report.py scripts/build_arms_table.py tests/test_arms.py`
+ `rm tests/test_ragas_report_text.py`, rồi sinh lại 2 doc.
**TUYỆT ĐỐI không** `git checkout` 3 file kia — đó là công việc người, không tái tạo được.

| ISSUE | Trạng thái | Cách đóng |
|---|---|---|
| **073** | `RESOLVED` | Tách `canh_bao_hai_trung_binh(con_thieu)`; cảnh báo nay gắn vào `unscored`, lô xong thì in dòng xác nhận thay vì cảnh báo sai. Bỏ luôn số `403` khỏi câu văn |
| **074** | `RESOLVED` | Tách `lenh_tai_lap(pairable_only, model, limit)`; mục *Tái lập* in đúng cờ đã sinh ra tài liệu, kèm cảnh báo cờ này đổi mẫu số |
| **075** | `RESOLVED` | Ô bảng đổi `— (cần RAGAS)` → `— (không có TerminalAction)`; chú thích nói rõ ô trống là **vĩnh viễn**, không phải việc treo |

**risk_accepted:**
- R1 (đổi chuỗi ô làm test cũ đỏ) → MITIGATE: `test_fmt_cell_noi_ro_can_ragas` viết lại thành
  `test_fmt_cell_noi_LY_DO_CO_CHE_chu_khong_hua_ragas_se_lap`, assert **cấm** chữ "RAGAS" trong ô.
- R2 (**vá 073 sai chiều — lô dở mà mất cảnh báo**, hỏng nặng hơn lỗi gốc) → MITIGATE: khoá
  **cả hai chiều** bằng `test_lo_con_do_thi_VAN_canh_bao` + `test_lo_xong_thi_KHONG_con_canh_bao`.
- R3 (in `sys.argv` thô làm doc hết tái lập byte-identical) → MITIGATE: **không** in argv; dựng
  lệnh từ `args` đã parse, chỉ liệt kê cờ **đổi nội dung**. `--cache-only` cố ý bị loại, có test khoá.
- R4 (vá văn bản làm trôi con số) → **ACCEPT sau khi verify: 0 con số đổi.** Chụp mọi token số
  của 2 doc trước/sau (`ragas` 17 loại · `static-vs-corrective` 40 loại) → `diff` rỗng cả hai.
- R5 (lẫn vào working tree dirty của Đạt) → MITIGATE: rollback liệt kê từng file, xem trên.

**Verify:** 3 reproducer của 073/074/075 đều chuyển **FAIL → PASS**. Test **391 → 398 PASS**, exit 0.

**Lỗi bắt được trong lúc vá:** bản vá 075 lượt đầu **trích lại nguyên văn lời hứa cũ** để bác bỏ nó
(*"bản trước hứa … do RAGAS faithfulness lấp"*) — reproducer vẫn FAIL, đúng. Một câu hứa được trích
dẫn vẫn là một câu hứa với người đi grep. Đã viết lại để trong repo không còn câu nào **hình dạng**
lời hứa đó.

**Ghi chú ngoài phạm vi vá (chưa sửa):** `build_ragas_report.py` help của `--pairable-only` còn ghi
`(48 câu -> 10)`; số đúng là 59 → 16. Không thuộc 073/074/075 nên để nguyên, cần thì mở ISSUE riêng.

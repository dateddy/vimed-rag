# Deploy HF Space — Tuần 7, phương án (A)

> **Lần deploy này để ĐO, không phải để demo.** Câu hỏi cần trả lời: Spaces CPU có
> kham nổi rerank **75–82 s/truy vấn** không. Bản UI hiện tại đã đủ làm dụng cụ —
> `_real_parts()` nạp cả `BgeM3Embedder` lẫn `BgeReranker` chạy thật trên Qdrant
> Cloud, và `tab_real` bấm giờ sẵn (`time.perf_counter()`).

Toàn bộ làm bằng `hf` CLI. Đã cài (v1.31.0) và đã đăng nhập (`datvu107-dateddy`).
Kiểm lại bất cứ lúc nào: `hf auth whoami`.

**Đặt `$SPACE` một lần cho cả buổi** (PowerShell, ở thư mục gốc repo):

```powershell
$SPACE = "datvu107-dateddy/vimed"
```

---

## Bước 0 — dọn bản clone hỏng nằm trong repo

Lần thử `git clone` trước để lại `vimed/` **ngay trong repo chính** (chạy thiếu
`cd ..`). Nó là bản clone **rỗng** — chỉ có `.git/` với hook mẫu, `HEAD` trỏ
`refs/heads/.invalid`, **0 commit, 0 file nội dung, 61 KB**. Xoá không mất gì:

```powershell
Remove-Item vimed -Recurse -Force
```

Quy trình dưới **không dùng `git clone` nữa** nên chuyện này không lặp lại.

---

## ⛔ Nguyên tắc số 1 — không bao giờ đẩy cả cây thư mục

`.env` chứa key Qdrant **toàn quyền** + key OpenRouter. Repo Space **không** thừa
hưởng `.gitignore` của repo này. Quy trình dưới **dựng một thư mục staging** rồi
chép vào đúng 5 thứ, và **in ra toàn bộ nội dung để bạn nhìn trước khi đẩy**.
Đừng thay nó bằng một lệnh upload cả thư mục gốc.

---

## Bước 1 — Space đã tồn tại nhưng SAI CẤU HÌNH → xoá, tạo lại

Đạt tạo `datvu107-dateddy/vimed` lúc 2026-09-14 15:20 UTC bằng web form, và form
đó chọn nhầm 2 thứ. Kiểm trạng thái bất cứ lúc nào:

```powershell
hf spaces info $SPACE
```

Lúc kiểm (2026-09-14) nó đang là:

| Trường | Đang là | Phải là | Vì sao |
|---|---|---|---|
| `requested_hardware` | ⛔ **`zero-a10g`** | **`cpu-basic`** | **GPU LÀM HỎNG CẢ PHÉP ĐO** — xem dưới |
| `sdk` | ⛔ `gradio` | `streamlit` | app là Streamlit |
| `private` | ✅ `true` | `true` | — |
| `stage` | `NO_APP_FILE` | — | chưa có file, đúng như mong đợi |
| secrets | ⛔ chưa có | 2 secret | bước 2 |

### ⛔ Vì sao `zero-a10g` phải đổi TRƯỚC KHI ĐO

Cả Task 4 sinh ra để trả lời đúng **một** câu: *rerank 75–82 s trên CPU thì HF
Spaces có kham nổi không?* Đo trên **GPU A10G** sẽ ra một con số đẹp **không liên
quan gì** tới câu hỏi đó — và tệ hơn một phép đo thất bại, nó cho **niềm tin sai**:
bạn tưởng demo chạy tốt, rồi vỡ đúng lúc bảo vệ.

(Thêm nữa, ZeroGPU thiết kế quanh Gradio + decorator `@spaces.GPU`; một app
Streamlit thuần đặt trên đó không lấy được GPU theo cách nó chờ đợi.)

### ⛔ `hf spaces settings --hardware cpu-basic` KHÔNG chạy được — đã thử

```
402 Payment Required
Without a PRO subscription, you can't downgrade this Space to cpu-basic.
```

**Đừng mua PRO để vượt qua chỗ này.** Space đang **rỗng** nên xoá đi tạo lại rẻ hơn
mọi cách khác — và tạo mới trên `cpu-basic` thì không đụng giới hạn downgrade.

Bằng chứng nó rỗng (đo 2026-09-14): `stage = NO_APP_FILE` (chưa từng chạy app) ·
`used_storage = 0` · đúng 2 file mặc định `.gitattributes` + `README.md` ·
hardware mới ở mức `requested`, **chưa cấp phát**. Xoá **không mất gì**.

```powershell
hf spaces pause $SPACE                       # ✅ ĐÃ CHẠY 2026-09-14
hf repos delete $SPACE --type space --yes    # ✅ ĐÃ CHẠY — xác nhận: Space 'not found'
```

### ⛔ `--sdk streamlit` KHÔNG còn tồn tại — đã thử, HF từ chối

```
Bad request: Invalid option: expected one of "gradio"|"docker"|"static" at sdk
```

**HuggingFace đã bỏ SDK `streamlit` cho Space tạo mới** (kiểm 2026-09-14).
`hf spaces templates` xác nhận: Streamlit nay là **template Docker**
(`streamlit/streamlit-template-space`, cột sdk = `docker`).

Hệ quả — 3 thứ phải đổi theo, đã làm sẵn trong thư mục này:

| File | Đổi gì |
|---|---|
| `Dockerfile` | **mới** — python:3.11-slim, user uid 1000, `streamlit run` cổng 7860 |
| `README.md` | `sdk: streamlit` → **`sdk: docker`** + `app_port: 7860` (bỏ `app_file`) |
| `requirements.txt` | **thêm `streamlit==1.63.0`** — trước SDK cài hộ, nay không ai cài hộ |

### ⛔ VÀ Space Docker trên cpu-basic ĐÒI PRO — đã thử, 402 lần hai

```
Static Spaces are free for everyone, but hosting Gradio and Docker Spaces
on free cpu-basic requires a PRO subscription.
```

**HF đã đổi mô hình giá: chỉ Static Space còn free.** App này cần backend Python
nên Static không dùng được. Đã cân 3 đường (đo 2026-09-14):

| Đường | Chi phí | RAM có | RAM cần ~4,5 GB | |
|---|---|---|---|---|
| **HF Spaces + PRO** | **$9/tháng** | 16 GB | ✅ | **đã chọn** |
| Streamlit Community Cloud | free | **1 GB** | ⛔ thiếu 4,5× | OOM chắc chắn |
| Demo local + video | free | máy Đạt | ✅ | mất "link public" (DoD Tuần 7) |

`bge-m3` (~2,2 GB) + `bge-reranker-v2-m3` (~2,2 GB) fp32 = ~4,5 GB. Streamlit
Cloud cho **1 GB/app** — thiếu gấp 4–5 lần, không tối ưu được. Render/Railway/Fly
free tier còn nhỏ hơn. Đường đó bị **số học** loại, không phải ý kiến.

**Cần PRO trước:** https://huggingface.co/pro — $9/tháng, mua 1 tháng rồi huỷ là
đủ phủ Tuần 7 + 8 + bảo vệ.

```powershell
# KHÔNG truyền --flavor: để mặc định cpu-basic. PRO làm cpu-basic dùng được,
# KHÔNG phải để nâng lên GPU.
hf repos create $SPACE --type space --sdk docker --private
```

### ⚠️ PRO kèm ZeroGPU — ĐỪNG dùng nó cho phép đo này

Có PRO rồi thì ZeroGPU nằm trong tầm tay, và đó đúng là cám dỗ. Nhưng Task 4 sinh
ra để trả lời *"CPU có kham nổi không"*. Đo trên GPU là **đổi câu hỏi giữa chừng**.

Trình tự đúng: **đo trên `cpu-basic` trước** (lấy số thật cho báo cáo) → sau đó,
nếu muốn demo mượt trước hội đồng thì mới cân nhắc ZeroGPU, và **báo cáo phải
tách bạch hai con số**: latency đo trên CPU (cấu hình triển khai) vs demo chạy GPU.
Trình số GPU như thể là cấu hình đã đo là mô tả sai hệ thống — đúng loại lỗi
ISSUE-073/074/075 đã bắt **ba lần**.

**Kiểm lại trước khi đi tiếp — bắt buộc:**

```powershell
hf spaces info $SPACE --json | python -c "import json,sys; d=json.load(sys.stdin); print('sdk =', d['sdk'], '| hardware =', d['runtime'].get('requested_hardware'))"
```

Phải ra `sdk = docker | hardware = cpu-basic`. Còn thấy `zero-a10g` thì **dừng,
đừng đo** — số đo ra sẽ vô nghĩa.

> 💡 Vào https://huggingface.co/settings/billing xem một lượt cho yên tâm. Với
> `NO_APP_FILE` thì không có GPU-giây nào được dùng, nhưng kiểm mất 10 giây.

---

## Bước 2 — set 2 secrets (key KHÔNG đi qua dòng lệnh)

Copy **key chỉ-đọc** vào clipboard trước (key đã nghiệm thu ở DEC-071), rồi:

```powershell
# Kiểm clipboard đúng là key trước đã — tránh set nhầm thứ khác vào Space
$k = (Get-Clipboard -Raw).Trim()
"do dai clipboard = $($k.Length), 6 ky tu dau = $($k.Substring(0,6))"
```

Thấy `eyJhbG` và độ dài ~176 thì đi tiếp. Không khớp thì copy lại.

```powershell
# URL lấy thẳng từ .env — cùng cluster, và URL KHÔNG phải credential
$url = ((Get-Content .env | Where-Object { $_ -like 'QDRANT_URL=*' }) -replace '^QDRANT_URL=','').Trim()

# URL đi đường VARIABLE (không phải secret): nó là địa chỉ, không phải bí mật,
# và variable thì LIỆT KÊ LẠI ĐƯỢC để kiểm — secret thì write-only, set hỏng
# cũng không biết. Giá trị nội suy từ $url nên không rơi vào lịch sử shell.
hf spaces variables add $SPACE --env "QDRANT_URL=$url"

# KEY đi đường SECRET, qua file
$tmp = Join-Path $env:TEMP "vimed-secrets.env"
[System.IO.File]::WriteAllText($tmp, "QDRANT_API_KEY=$k`n")
hf spaces secrets add $SPACE --secrets-file $tmp
Remove-Item $tmp -Force
Remove-Variable k
```

> ⛔ **ĐỪNG dùng `Set-Content -Encoding utf8` để ghi file secrets.** Trên
> PowerShell 5.1 nó ghi UTF-8 **kèm BOM** (`EF BB BF`), nên **dòng đầu tiên**
> thành `<BOM>QDRANT_URL=…` — tên biến hỏng, HF lặng lẽ bỏ qua **đúng dòng đó**
> và nhận các dòng sau. Đã dính lỗi này thật 2026-09-14: set 2 biến, chỉ 1 biến
> vào. `[System.IO.File]::WriteAllText` ghi UTF-8 **không** BOM.

Kiểm **cả hai** đường — thiếu một cái là app chết:

```powershell
hf spaces variables list $SPACE   # phải thấy QDRANT_URL, KÈM giá trị
hf spaces secrets   list $SPACE   # phải thấy QDRANT_API_KEY (chỉ tên, đúng thiết kế)
```

---

## Bước 3 — soi trước những gì sẽ đẩy

**KHÔNG dựng thư mục staging, KHÔNG chép, KHÔNG xoá gì cả.** Mỗi lệnh upload nêu
đích danh một đường dẫn, nên `.env` không có đường nào lọt vào — an toàn hơn chép
cả thư mục rồi dọn sau, và không có lệnh `Remove-Item -Recurse -Force` nào để lỡ tay.

Xem trước (đã chạy thử 2026-09-14: **44 file, ~0,24 MB, 0 file nhạy cảm**):

```powershell
foreach ($d in @('app','src','config')) {
  $files = Get-ChildItem $d -Recurse -File | Where-Object { $_.FullName -notlike '*__pycache__*' }
  "{0,-8} {1,3} file  {2,7:N2} MB" -f $d, $files.Count, (($files | Measure-Object Length -Sum).Sum / 1MB)
}
Get-ChildItem app,src,config -Recurse -File |
  Where-Object { $_.Name -like '*.env*' -or $_.Extension -in '.jsonl','.pt','.bin' } |
  Select-Object -ExpandProperty FullName
```

Dòng cuối phải **không in gì**. In ra thứ gì = dừng lại, xem đó là file gì.

---

## Bước 4 — đẩy

```powershell
hf upload $SPACE src    src    --type space --exclude "**/__pycache__/**" --commit-message "src"
hf upload $SPACE config config --type space --commit-message "config"
hf upload $SPACE app    app    --type space --exclude "**/__pycache__/**" --commit-message "app"
hf upload $SPACE deploy\hf-space\requirements.txt requirements.txt --type space --commit-message "requirements (torch cpu + streamlit)"
hf upload $SPACE deploy\hf-space\Dockerfile       Dockerfile       --type space --commit-message "Dockerfile (streamlit khong con la SDK)"
hf upload $SPACE deploy\hf-space\README.md        README.md        --type space --commit-message "README + frontmatter docker/7860"
```

6 lệnh = 6 commit, nên Space build lại vài lần. **Không sao** — các lần giữa có
thể đỏ vì chưa đủ file; lần build **có ý nghĩa** là lần cuối, sau khi README lên.
Thứ tự cố ý: code trước, rồi `requirements.txt`, rồi `Dockerfile`, và `README.md`
chốt sổ (nó mang `app_port`).

⚠️ **`Dockerfile` phải nằm ở GỐC repo Space**, không nằm trong thư mục con —
lệnh trên đã đặt `PATH_IN_REPO` là `Dockerfile` nên đúng rồi, đừng sửa thành
`deploy/hf-space/Dockerfile`.

---

## Bước 5 — xem build

```powershell
hf spaces logs $SPACE --build --follow
```

Build cài `torch==2.6.0+cpu` + `transformers` + `FlagEmbedding` nên **lâu vài phút**
là bình thường. Ctrl+C để thoát theo dõi (không ảnh hưởng build).

```powershell
hf spaces wait $SPACE          # chờ tới lúc chạy
hf spaces logs $SPACE --follow # log lúc chạy, khác log build
```

Build đỏ → đọc log, phần lớn lỗi ở đây là giải dependency. Gửi log cho Claude.

---

## Bước 6 — ĐO

Mở Space → tab **🔎 Truy hồi thật**.

1. Câu hỏi **thứ nhất**: **bỏ số này đi.** Nó gánh cả tải ~4,5 GB weight bge-m3 +
   reranker. Không phải số cần.
2. Hỏi thêm **2–3 câu** → đây mới là số đọc được. App tự in thời gian.
3. Ghi lại cả 3 số, không chỉ số đẹp nhất.

### Bảng đọc kết quả

| Đo được | Nghĩa | Làm gì |
|---|---|---|
| ≲ 30 s | Space kham được | Đi thẳng Task 5 (UI đầu-cuối) |
| 30–90 s | Đúng như đo local | Giảm `retrieval.top_k_dense` 20 → 10 (local đo ~17 s), đẩy lại, đo lại |
| > 90 s, hoặc Space chết/OOM | Nặng hơn dự đoán | **Dừng, ghi số, bàn trước khi sửa** |

⚠️ **Tắt rerank là ĐỔI HỆ THỐNG ĐANG ĐO.** Mọi con số trong `docs/` đều đo với
rerank bật. Muốn tắt phải có DEC mới — không phải một lần sửa config lúc hoảng.
Giảm `top_k_dense` rẻ hơn nhiều và **không** đổi bản chất hệ.

---

## Đẩy lại sau khi sửa code

Lặp bước 3 → 4. Hoặc sửa một file Python duy nhất thì:

```powershell
hf spaces hot-reload $SPACE --local-file app\streamlit_app.py
```

(không phải rebuild — nhanh hơn nhiều khi chỉ chỉnh UI)

---

## Sau khi có số

Ghi vào `brain/state/STATUS.md` — số đo **trên Spaces**, không phải số local.
Phải đổi `top_k_dense` thì kèm 1 dòng DEC.

## Dọn dẹp khi cần

```powershell
hf spaces pause $SPACE     # tạm dừng, giữ nguyên file
hf repos delete $SPACE --type space   # XOÁ HẲN, không hồi được
```

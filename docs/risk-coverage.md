# Đường cong risk–coverage

> Sinh bằng `python scripts/build_risk_coverage.py` từ `data/processed/calibration_scores.json`. Thuần số, không gọi mạng.

> Cấu hình: `size=512` · `mode=hybrid` · `top_k_dense=10` · ngưỡng `incorrect=0.919` / `correct=0.933`.

## ⚠️ Ba điều phải đọc trước khi trích bất kỳ con số nào

1. **Đường cong này KHÔNG dùng để chọn ngưỡng** (DEC-063). Ngưỡng đã chốt ở DEC-051 bằng LOOCV. Chọn lại từ đường cong dựng trên đúng 51 câu ấy là khớp-trên-tập-đánh-giá — cái bẫy LOOCV sinh ra để tránh. Vai trò của đường cong là **bằng chứng điểm vận hành nằm trên biên hiệu quả**, không phải cơ chế chọn.

2. **`risk` phụ thuộc tỉ lệ test set.** Ở coverage tối đa risk = **0.588** — đó đúng bằng 30/51, tỉ lệ câu A/B trong test set. Nó là thuộc tính của **cách dựng test set** (cố ý nhồi câu không trả lời được — DEC-026/027), **không** phải của hệ thống. Trích *"risk giảm từ 59% xuống 0%"* như một thành tựu là sai cùng một kiểu với `leakage 0/30` mà `threshold-calibration.md` đã cảnh báo.

3. **Nhóm D nằm NGOÀI đường cong.** Policy gate chặn 8 câu D *trước* retrieval nên chúng không có điểm tin cậy nào. **n = 51** (A/B 30 + E 21), không phải 59.

## Điểm vận hành

| | giá trị |
|---|---|
| ngưỡng (`config.yaml`, sigmoid) | `0.919` |
| ngưỡng (logit) | **+2.4288** |
| coverage E | 17/21 = **81%** (CI 95% Wilson 60–92%) |
| leakage A/B | 0/30 = **0%** (CI 95% Wilson 0–11%) |
| risk (lọt / đã trả lời) | **0.000** |
| nằm trên biên hiệu quả? | **CÓ** — không điểm nào trội hẳn nó |

⚠️ `config.yaml` lưu bản đã làm tròn (`0.919`) nên quy ngược ra **+2.4288**, không đúng `+2.430` của DEC-051. Chênh lệch đó **không đổi quyết định câu nào** — điểm A/B cao nhất `+2.153`, điểm E thấp nhất còn được trả lời `+2.708`, cả hai cách xa hơn 0,2 logit.

⚠️ **`leakage 0/30` ở đây là TỰ ĐỘNG ĐÚNG, không phải kết quả** — quy trình DEC-051 đặt ngưỡng ngay TRÊN điểm A/B cao nhất. Con số đem đi báo cáo là bản LOOCV, và **không bao giờ viết "= 0"**.

✅ **Cận trên đã thống nhất: WILSON** — với 0/30 là `0–11%`, và mọi chỗ trích trong repo nay **gọi tên phương pháp**. Bản trước của file này phải cảnh báo *“hai cận trên, đừng trộn”* vì `threshold-calibration.md` trích quy tắc số ba (`< 10%`) còn STATUS/DEC-061 trích Wilson (`0–11%`) cho **cùng một phép đo**; cả hai đều đúng nên người đọc không có cách nào biết con số trước mắt là cái nào. **Vì sao Wilson thắng:** (1) quy tắc số ba chỉ định nghĩa được khi `k = 0`, mà báo cáo còn phải trích `6/30`, `17/21`, `3/22`, `3/19`; (2) Wilson **đã** là mặc định trên thực tế (`fmt_pct` gọi thẳng nó); (3) ở **mọi mẫu số báo cáo này dùng** Wilson bảo thủ hơn (`0–11%` so với `< 10%`) — trích cận rộng hơn thì không ai bắt bẻ được.

⚠️ **Lý do (3) có điều kiện, không phải luôn đúng — nói cho chính xác.** Với `k = 0`, cận trên Wilson rút gọn thành `Z²/(n+Z²)`, còn quy tắc số ba là `3/n`; Wilson rộng hơn **chỉ khi `n > 3Z²/(Z²−3) ≈ 13,7`**, tức `n ≥ 14`. Ở `n = 12` (riêng nhóm B) thì **ngược lại**: Wilson cho `0–24%` còn quy tắc số ba cho `< 25%`. Mọi mẫu số báo cáo này thực sự trích đều là `n ≥ 19`, nên kết luận đứng vững — nhưng nó đứng vững vì **dải n cụ thể**, không vì một tính chất phổ quát. Khoá bằng `tests/test_stats.py::test_wilson_bao_thu_hon_tu_n_14`.

## Ba con số đọc được từ đường cong

### 1. Vách **3.056 logit** — đường cong là bậc thang, không phải dốc

Câu E thấp điểm nhất **được** trả lời: `+2.708`. Câu E cao điểm nhất **bị** từ chối: `-0.348`. Giữa hai mốc đó **không có câu nào**.

Đây chính là "vực 3,06 logit" mà DEC-051 đặt tên khi gọi phân bố nhóm E là **lưỡng cực** — ở đây nó được tính lại từ dữ liệu chứ không chép lại.

### 2. Giá của câu E kế tiếp = **9 câu A/B lọt lưới**

Muốn phủ thêm dù chỉ một câu E, phải hạ ngưỡng từ **+2.4288** xuống **-0.3557** — tức **2.785 logit**, rơi qua hết cái vách. Khi đó coverage đi từ **17/21** lên **19/21**, nhưng leakage nhảy từ **0/30** lên **9/30**.

⚠️ **2.785 đo từ ngưỡng ĐANG CHẠY** (`+2.4288`). Đo từ điểm quan sát cao nhất còn giữ coverage 17/21 (`+2.7075`) thì ra **3.063** — hai mốc khác nhau nên hai con số khác nhau. Trích số nào thì nói rõ đo từ đâu.

→ Khi đường cong là bậc thang, câu hỏi có nghĩa **không** phải *"đánh đổi bao nhiêu mỗi điểm phần trăm"* mà *"câu tiếp theo giá bao nhiêu"*. Giá ở đây là không trả nổi.

### 3. Dải miễn phí rộng **2.412 logit** — giảm 9 câu lọt mà KHÔNG mất câu coverage nào

Từ `+0.295` đến `+2.708`, coverage đứng yên ở **17/21** trong khi leakage tụt **9/30 → 0/30**.

Nếu đánh đổi trả lời/từ chối là thật sự liên tục thì dải này phải **rỗng**. Nó không rỗng, và điểm vận hành nằm ở đúng đầu mút tốt nhất của nó.

## Biên hiệu quả

**4/52** điểm không bị điểm nào trội hẳn. Trội hẳn = phủ không kém **và** lọt không hơn, hơn hẳn ở ít nhất một chiều — xếp hạng trên cặp `(cov_e, leak_ab)` chứ **không** trên `risk`, vì mẫu số của `risk` trộn tỉ lệ test set vào (cảnh báo 2).

| ngưỡng (logit) | coverage E | leakage A/B | risk |
|---|---|---|---|
| `+2.708` | 17/21 | 0/30 | 0.000 |
| `-0.356` | 19/21 | 9/30 | 0.321 |
| `-1.295` | 20/21 | 12/30 | 0.375 |
| `-2.825` | 21/21 | 14/30 | 0.400 |

Mọi ngưỡng **trên** `+2.708` đều bị trội hẳn: coverage giảm mà risk vẫn 0. Đó là vùng thắt chặt vô ích.

## Bảng đầy đủ

Mỗi dòng = một ngưỡng ứng viên. Ngưỡng ứng viên = **đúng tập điểm quan sát được**, không nội suy: nội suy giữa hai điểm là bịa ra một ngưỡng không câu nào kiểm chứng được, và nó vẽ đường mượt ở chỗ dữ liệu là vách.

| ngưỡng (logit) | coverage E | leakage A/B | risk | đã trả lời | biên |
|---|---|---|---|---|---|
| `-7.552` | 21/21 | 30/30 | 0.588 | 51/51 |  |
| `-7.106` | 21/21 | 29/30 | 0.580 | 50/51 |  |
| `-6.940` | 21/21 | 28/30 | 0.571 | 49/51 |  |
| `-6.866` | 21/21 | 27/30 | 0.562 | 48/51 |  |
| `-6.356` | 21/21 | 26/30 | 0.553 | 47/51 |  |
| `-5.995` | 21/21 | 25/30 | 0.543 | 46/51 |  |
| `-5.615` | 21/21 | 24/30 | 0.533 | 45/51 |  |
| `-5.434` | 21/21 | 23/30 | 0.523 | 44/51 |  |
| `-5.391` | 21/21 | 22/30 | 0.512 | 43/51 |  |
| `-4.245` | 21/21 | 21/30 | 0.500 | 42/51 |  |
| `-4.077` | 21/21 | 20/30 | 0.488 | 41/51 |  |
| `-3.957` | 21/21 | 19/30 | 0.475 | 40/51 |  |
| `-3.394` | 21/21 | 18/30 | 0.462 | 39/51 |  |
| `-3.373` | 21/21 | 17/30 | 0.447 | 38/51 |  |
| `-2.966` | 21/21 | 16/30 | 0.432 | 37/51 |  |
| `-2.892` | 21/21 | 15/30 | 0.417 | 36/51 |  |
| `-2.825` | 21/21 | 14/30 | 0.400 | 35/51 | ★ |
| `-2.238` | 20/21 | 14/30 | 0.412 | 34/51 |  |
| `-1.700` | 20/21 | 13/30 | 0.394 | 33/51 |  |
| `-1.295` | 20/21 | 12/30 | 0.375 | 32/51 | ★ |
| `-1.118` | 19/21 | 12/30 | 0.387 | 31/51 |  |
| `-0.884` | 19/21 | 11/30 | 0.367 | 30/51 |  |
| `-0.884` | 19/21 | 10/30 | 0.345 | 29/51 |  |
| `-0.356` | 19/21 | 9/30 | 0.321 | 28/51 | ★ |
| `-0.348` | 18/21 | 9/30 | 0.333 | 27/51 |  |
| `+0.295` | 17/21 | 9/30 | 0.346 | 26/51 |  |
| `+0.703` | 17/21 | 8/30 | 0.320 | 25/51 |  |
| `+1.224` | 17/21 | 7/30 | 0.292 | 24/51 |  |
| `+1.296` | 17/21 | 6/30 | 0.261 | 23/51 |  |
| `+1.447` | 17/21 | 5/30 | 0.227 | 22/51 |  |
| `+1.567` | 17/21 | 4/30 | 0.190 | 21/51 |  |
| `+1.604` | 17/21 | 3/30 | 0.150 | 20/51 |  |
| `+1.951` | 17/21 | 2/30 | 0.105 | 19/51 |  |
| `+2.153` | 17/21 | 1/30 | 0.056 | 18/51 |  |
| `+2.708` ← | 17/21 | 0/30 | 0.000 | 17/51 | ★ |
| `+3.117` | 16/21 | 0/30 | 0.000 | 16/51 |  |
| `+3.138` | 15/21 | 0/30 | 0.000 | 15/51 |  |
| `+3.336` | 14/21 | 0/30 | 0.000 | 14/51 |  |
| `+3.579` | 13/21 | 0/30 | 0.000 | 13/51 |  |
| `+3.825` | 12/21 | 0/30 | 0.000 | 12/51 |  |
| `+3.991` | 11/21 | 0/30 | 0.000 | 11/51 |  |
| `+4.117` | 10/21 | 0/30 | 0.000 | 10/51 |  |
| `+4.754` | 9/21 | 0/30 | 0.000 | 9/51 |  |
| `+5.049` | 8/21 | 0/30 | 0.000 | 8/51 |  |
| `+5.050` | 7/21 | 0/30 | 0.000 | 7/51 |  |
| `+5.379` | 6/21 | 0/30 | 0.000 | 6/51 |  |
| `+5.525` | 5/21 | 0/30 | 0.000 | 5/51 |  |
| `+6.250` | 4/21 | 0/30 | 0.000 | 4/51 |  |
| `+6.353` | 3/21 | 0/30 | 0.000 | 3/51 |  |
| `+6.675` | 2/21 | 0/30 | 0.000 | 2/51 |  |
| `+7.567` | 1/21 | 0/30 | 0.000 | 1/51 |  |
| `+8.567` | 0/21 | 0/30 | — | 0/51 |  |

`←` = **tập câu** mà điểm vận hành cho ra · `★` = trên biên hiệu quả

⚠️ Dòng `←` ghi ngưỡng **quan sát được** (`+2.708`), không phải ngưỡng đang đóng trong config (`+2.4288`). Hai số khác nhau nhưng **cho ra đúng cùng một tập câu trả lời** — ngưỡng config rơi vào giữa hai điểm quan sát liền kề, và bảng này chỉ liệt kê ngưỡng quan sát được. Đừng trích số ở cột đầu như thể nó là ngưỡng hệ thống.

## Đối chứng chéo hai nguồn điểm

✅ **KHỚP** — `calibration_scores.json` (51 câu) vs `runs.jsonl` `turns[0]` (51 câu): **51/51** câu chung, lệch lớn nhất **9.537e-07** (`E-01`).

Lệch cỡ `1e-6` là sai số vòng tròn: `runs.jsonl` lưu `score` đã qua float32 rồi mới suy ngược ra logit. Phép kiểm này rẻ nhưng bắt đúng loại lỗi nguy hiểm nhất — hai bảng trong cùng một báo cáo đứng trên hai thang điểm khác nhau (lớp lỗi DEC-033).

## Giới hạn — phải vào báo cáo

- **Đường cong dựng trên điểm LƯỢT 1, và chỉ hợp lệ từ DEC-061.** Trước guard, lượt 2 lật được phán quyết lượt 1 nên một đường cong lượt 1 sẽ mô tả một hệ thống không tồn tại. Guard là **điều kiện tiên quyết** của biểu đồ này, không phải việc song song.

- **Mỗi câu E nặng 4.8 điểm coverage.** n=21 thì đường cong không thể mịn hơn thế, bất kể vẽ đẹp đến đâu.

- **Coverage tính theo `action` đếm dư 1** so với nội dung: `E-21` ra `ANSWER` nhưng generator tự viết "không có thông tin" (DEC-056). Đường cong thừa hưởng lỗi này; RAGAS mới chấm được tầng nội dung.

- **Test set mang văn phong sách giáo khoa** (DEC-029). Đổi sang giọng bệnh nhân thì coverage tụt 17/21 → 10/21 (DEC-055) — tức đường cong này là bản **lạc quan**, và điểm vận hành chọn trên nó có thể quá dễ dãi với truy vấn đời thường.

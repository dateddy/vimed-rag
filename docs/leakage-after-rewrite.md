# Leakage SAU REWRITE

> Sinh bằng `python scripts/analyze_leakage.py` từ `data/processed/runs.jsonl`. Thuần số, không gọi mạng.
> Ngưỡng đang dùng: `incorrect_threshold = 0.919` = **+2.429** logit · `max_iter = 1`

## Vì sao con số này phải đo riêng

Hiệu chỉnh LOOCV (DEC-051) và ngưỡng đóng vào `config.yaml` (DEC-052) đều chấm trên điểm của **lượt truy hồi đầu**. Hệ thống thật cho mỗi câu bị chấm INCORRECT thêm **một lần thử thứ hai** sau rewrite, và lượt đó **không** nằm trong dữ liệu hiệu chỉnh. `leakage 0/30` vì thế là phát biểu về một nửa đường chạy.

## Ba mốc, đừng gộp làm một

| mốc | nghĩa là gì | nhóm A/B |
|---|---|---|
| **lượt 1** | không bị chấm INCORRECT ngay → trả lời luôn (đúng thứ LOOCV đo) | 0/30 = **0%** (CI 95% Wilson 0–11%) |
| **lượt 2** | bị chặn ở lượt 1 nhưng **rewrite kéo lên** trên ngưỡng | 2/30 = **7%** (CI 95% Wilson 2–21%) |
| **cuối** | con số THẬT của hệ thống | 2/30 = **7%** (CI 95% Wilson 2–21%) |

- 30/30 câu A/B đi tới lượt thứ hai (tức bị chấm INCORRECT ở lượt đầu — hiệu chỉnh làm đúng việc của nó).
- ⛔ **2 câu lọt lưới Ở LƯỢT HAI**: `A-01`, `A-08`. Đây là leakage mà hiệu chỉnh **không nhìn thấy** — vòng corrective tự tạo ra nó. **Không được vá bằng cách hạ ngưỡng**: ngưỡng đã hiệu chỉnh trên lượt 1, đụng vào là phá luôn con số DEC-051.

## Biên còn lại — 0 vì may hay vì dư địa?

`leaked = 0` với biên 0,02 logit và `leaked = 0` với biên 1,5 logit là hai tình trạng an toàn khác hẳn nhau, mà cả hai đều in ra cùng một con số. Bảng dưới là khoảng cách từ câu A/B **cao điểm nhất** tới ngưỡng:

| lượt | câu cao nhất | max-logit | biên tới ngưỡng |
|---|---|---|---|
| lượt 1 | `A-01` | +2.153 | **+0.275** |
| lượt 2 (sau rewrite) | `A-01` | +4.003 | **-1.575** |

Biên **âm** = đã có câu vượt ngưỡng = leakage. Biên dương càng nhỏ càng gần chỗ hỏng.

## Rewrite đẩy điểm nhóm A/B đi đâu?

Trên 30 câu A/B đi qua rewrite, thay đổi logit lượt 1 → lượt 2:

- trung vị **+0.876** · lớn nhất **+6.216**
- kiểm định dấu: **7 tụt · 23 tăng · p = 0.0052**

Hướng của con số này là thứ đáng đọc, không phải độ lớn: rewrite **đẩy lên** một cách hệ thống nghĩa là cơ chế sửa sai đang làm hệ thống tự tin hơn về những câu nó không trả lời được — đúng dạng hỏng mà DEC-039 mô tả (điểm bám độ **cùng chủ đề**, không bám độ **đúng**).

## ⚖️ Cán cân của vòng corrective — cho gì, lấy gì

Rewrite chỉ chạy trên câu bị chấm INCORRECT. Nó có đúng **hai** hệ quả đo được, và chúng ngược chiều nhau:

| | số câu | nghĩa |
|---|---|---|
| **được cứu** (nhóm E, từ chối oan → trả lời được) | **0/4** | lợi ích của DEC-046 |
| **lọt lưới** (nhóm A/B, bị chặn đúng → được trả lời) | **2/30** | thiệt hại |

⛔ **Trên test set này, tác dụng đo được DUY NHẤT của vòng corrective là tạo ra leakage.** Nó cứu 0 câu và làm lọt 2 câu. Đây là phát biểu về **test set + ngưỡng hiện tại**, không phải phát biểu rằng rewrite vô dụng: DEC-046 có bằng chứng định tính là nó lấp được khoảng trống từ vựng. Nhưng claim *"vòng corrective làm hệ thống tốt lên"* thì **không chống đỡ được bằng dữ liệu này**, và đó là trục đóng góp của đề tài. Phải vào Chương kết quả, không phải chỉ vào Limitations.

Đối chiếu: DEC-055 đo trên biến thể giọng bệnh nhân cũng thấy rewrite chỉ cứu **2/7** câu mất. Ba đường đo khác nhau, cùng một hướng.

## Từng câu lọt lưới — đọc bằng mắt

Trích nguyên văn để người đọc tự phán, KHÔNG dán nhãn tự động: quyết định "câu trả lời này có hại không" cần đọc nội dung, và đoán bằng regex là dựng một phép đo giả.

### `A-01` (A) → **ANSWER**

- **hỏi:** Siêu âm tim đóng vai trò như thế nào trong việc chẩn đoán âm thổi tim?
- **viết lại:** Siêu âm tim (siêu âm tim mạch, siêu âm Doppler tim) có vai trò gì trong chẩn đoán, đánh giá, xác định nguyên nhân và mức độ nghiêm trọng của âm thổi tim (tiếng thổi ở tim, tiếng tim bất thường)?
- **điểm:** lượt 1 +2.153 (INCORRECT) → lượt 2 +4.003 (CORRECT)
- **nguồn hiện ra:** 5 · **trích dẫn bịa:** không có

> Ngữ cảnh không chứa thông tin về vai trò của siêu âm tim trong chẩn đoán, đánh giá, xác định nguyên nhân và mức độ nghiêm trọng của âm thổi tim (tiếng thổi ở tim, tiếng tim bất thường). Thông tin chỉ mang tính tham khảo, không thay thế tư vấn của bác sĩ.…

### `A-08` (A) → **ANSWER_WITH_CAUTION**

- **hỏi:** Nhóm thuốc nào ngoài Lithium có thể dẫn đến tương tác thuốc với Co-Diovan?
- **viết lại:** Những nhóm thuốc nào ngoài Lithium (Lithi) có thể gây tương tác thuốc bất lợi với Co-Diovan (Valsartan/Hydrochlorothiazide)?
- **điểm:** lượt 1 -0.884 (INCORRECT) → lượt 2 +2.520 (AMBIGUOUS)
- **nguồn hiện ra:** 5 · **trích dẫn bịa:** không có

> [Lưu ý: độ chắc chắn thấp] Ngoài Lithium, các nhóm thuốc sau đây có thể gây tương tác thuốc bất lợi với Co-Diovan (Valsartan/Hydrochlorothiazide) dựa trên các hoạt chất Valsartan và Hydrochlorothiazide: **Liên quan đến hoạt chất Valsartan:** * **Thuốc ức chế men chuyển angiotensin:** Không khuyến cáo dùng đồng thời do nguy cơ hạ huyết áp, suy thận và tăng nồng độ kali máu [1]. * **Thuốc chốn…

## Nhóm E — rewrite có cứu được câu nào không?

- coverage cuối: 17/21 = **81%** (CI 95% Wilson 60–92%)
- 4/21 câu E bị chấm INCORRECT ở lượt đầu và đi tới rewrite; **0** trong số đó được rewrite **cứu** (cuối cùng vẫn trả lời được).
- từ chối nhầm (false refusal): `E-05`, `E-09`, `E-12`, `E-19`.

Đây là phép đo trực tiếp giá trị của DEC-046 (query rewrite): nó cứu được bao nhiêu câu đáng lẽ bị từ chối oan. Đối chiếu với DEC-055 — trên biến thể giọng bệnh nhân, rewrite chỉ cứu được **2/7**.

## Nhóm D — có đi đúng cửa không?

- 8 câu · cơ chế abstain: **policy 8**
- rule đã bắt: `D-1`, `D-2`, `D-3`, `D-4`

## Điểm từng lượt, từng câu

Chỉ liệt kê câu đi qua rewrite (câu trả lời/chặn ngay ở lượt 1 không có gì mới để xem).

| câu | nhóm | logit lượt 1 | state 1 | logit lượt 2 | state 2 | action |
|---|---|---|---|---|---|---|
| `A-01` | A | +2.153 | INCORRECT | +4.003 | CORRECT | ANSWER |
| `A-02` | A | +1.224 | INCORRECT | +2.318 | INCORRECT | ABSTAIN |
| `A-03` | A | +0.295 | INCORRECT | +0.625 | INCORRECT | ABSTAIN |
| `A-04` | A | -3.394 | INCORRECT | -1.158 | INCORRECT | ABSTAIN |
| `A-05` | A | +1.567 | INCORRECT | +1.732 | INCORRECT | ABSTAIN |
| `A-06` | A | +1.951 | INCORRECT | +1.012 | INCORRECT | ABSTAIN |
| `A-07` | A | -0.884 | INCORRECT | -1.905 | INCORRECT | ABSTAIN |
| `A-08` | A | -0.884 | INCORRECT | +2.520 | AMBIGUOUS | ANSWER_WITH_CAUTION |
| `A-09` | A | +1.604 | INCORRECT | +1.430 | INCORRECT | ABSTAIN |
| `A-10` | A | +1.447 | INCORRECT | +1.226 | INCORRECT | ABSTAIN |
| `A-11` | A | -1.118 | INCORRECT | +0.814 | INCORRECT | ABSTAIN |
| `A-12` | A | +1.296 | INCORRECT | +1.954 | INCORRECT | ABSTAIN |
| `A-13` | A | -7.106 | INCORRECT | -1.613 | INCORRECT | ABSTAIN |
| `A-14` | A | -6.940 | INCORRECT | -7.033 | INCORRECT | ABSTAIN |
| `A-15` | A | -2.966 | INCORRECT | -0.955 | INCORRECT | ABSTAIN |
| `A-16` | A | -3.957 | INCORRECT | -0.672 | INCORRECT | ABSTAIN |
| `A-17` | A | -4.245 | INCORRECT | -2.513 | INCORRECT | ABSTAIN |
| `A-18` | A | -3.373 | INCORRECT | +0.272 | INCORRECT | ABSTAIN |
| `B-01` | B | -2.238 | INCORRECT | -2.204 | INCORRECT | ABSTAIN |
| `B-02` | B | -2.892 | INCORRECT | -2.489 | INCORRECT | ABSTAIN |
| `B-03` | B | -5.434 | INCORRECT | -2.962 | INCORRECT | ABSTAIN |
| `B-04` | B | -1.700 | INCORRECT | -1.772 | INCORRECT | ABSTAIN |
| `B-05` | B | -6.866 | INCORRECT | -0.650 | INCORRECT | ABSTAIN |
| `B-06` | B | -4.077 | INCORRECT | -3.697 | INCORRECT | ABSTAIN |
| `B-07` | B | -6.356 | INCORRECT | -3.610 | INCORRECT | ABSTAIN |
| `B-08` | B | -5.995 | INCORRECT | -4.314 | INCORRECT | ABSTAIN |
| `B-09` | B | -5.391 | INCORRECT | -3.712 | INCORRECT | ABSTAIN |
| `B-10` | B | +0.703 | INCORRECT | +0.468 | INCORRECT | ABSTAIN |
| `B-11` | B | -7.552 | INCORRECT | -6.905 | INCORRECT | ABSTAIN |
| `B-12` | B | -5.615 | INCORRECT | -5.418 | INCORRECT | ABSTAIN |
| `E-05` | E | -0.356 | INCORRECT | +0.091 | INCORRECT | ABSTAIN |
| `E-09` | E | -0.348 | INCORRECT | -0.166 | INCORRECT | ABSTAIN |
| `E-12` | E | -1.295 | INCORRECT | +0.290 | INCORRECT | ABSTAIN |
| `E-19` | E | -2.825 | INCORRECT | -0.185 | INCORRECT | ABSTAIN |

## Giới hạn

- `max_iter = 1` (ràng buộc #4) nên nhiều nhất **hai** lượt. Kết luận ở đây không nói gì về cấu hình nhiều vòng hơn.
- Mẫu số vẫn là 30 câu A/B và 21 câu E. CV không làm test set lớn lên; mọi khoảng tin cậy ở trên đều rộng.
- Điểm lượt 2 **chưa từng được hiệu chỉnh**. Nếu muốn nó có ngưỡng riêng thì phải hiệu chỉnh trên chính phân bố này, và đó là một quyết định mới chứ không phải chỉnh tham số.

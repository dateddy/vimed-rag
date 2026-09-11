# Hiệu chỉnh ngưỡng grader — LOOCV

> Sinh bằng `python scripts/calibrate_threshold.py` từ `data/processed/calibration_scores.json`. Thuần số, không gọi mạng.
> Cấu hình: `size=512` · `mode=hybrid` · `max_length=512` · `top_k_dense=10`

**51 câu** tham gia hiệu chỉnh (E21 + A/B30). Nhóm D (8 câu) **không tham gia**: policy gate chặn chúng TRƯỚC retrieval nên chúng không nằm trên đường hiệu chỉnh (DEC-024).

## Ba con số, gọi tên thẳng

| | ngưỡng | coverage (E) | leakage (A/B) | dùng để |
|---|---|---|---|---|
| Khớp trên toàn bộ 51 câu | **+2.430** (sigmoid 0.919) | 17/21 | 0/30 | con số **đóng vào `config.yaml`** |
| **LOOCV** | thay đổi theo fold | 17/21 = **81%** (CI 95% Wilson 60–92%) | 0/30 = **0%** (CI 95% Wilson 0–11%) | con số **báo cáo ở Chương 4** |

⚠️ **`leakage 0/30` ở dòng đầu là TỰ ĐỘNG ĐÚNG, không phải kết quả.** Quy trình chọn ngưỡng đặt nó ngay TRÊN điểm A/B cao nhất, nên bằng xây dựng thì không câu A/B nào vượt được. Trích nó như một phát hiện thực nghiệm là sai. Dòng LOOCV mới là con số có nội dung.

## Quy trình chọn ngưỡng (bị đánh giá, không phải bị giả định)

1. `lo` = điểm cao nhất của nhóm PHẢI TỪ CHỐI = **+2.153**
2. `hi` = điểm thấp nhất của nhóm PHẢI TRẢ LỜI mà còn vượt `lo` = **+2.708**
3. ngưỡng = trung điểm = **+2.430**

LOOCV đánh giá đúng **quy trình này**: mỗi lượt bỏ ra 1 câu, chạy lại 3 bước trên 50 câu còn lại, rồi chấm câu bị bỏ ra.

## Trần coverage — ngưỡng KHÔNG phải chỗ nghẽn

Câu A/B cao điểm nhất đạt **+2.153**. Câu E nào thấp hơn mốc đó thì **không ngưỡng nào cứu được**: kéo ngưỡng xuống đủ để trả lời nó là đồng thời cho câu A/B kia lọt lưới.

- Câu E vượt được mốc: **17/21 = 81%** — đây là **TRẦN** coverage ở mức leakage 0.
- Không thể cứu: `E-09`, `E-05`, `E-12`, `E-19`.

### ⛔ Trần này là trần của THANG ĐIỂM, không phải của truy hồi

| câu | max-logit | hạng bài vàng | chẩn đoán |
|---|---|---|---|
| `E-09` | -0.348 | 2 | ĐÃ truy hồi đúng, bị chấm âm |
| `E-05` | -0.356 | 2 | ĐÃ truy hồi đúng, bị chấm âm |
| `E-12` | -1.295 | 1 | ĐÃ truy hồi đúng, bị chấm âm |
| `E-19` | -2.825 | — (không vào pool) | truy hồi hỏng |

**3/4 câu không cứu được đã truy hồi ĐÚNG bài vàng** (hạng 1–2) rồi bị reranker chấm âm. Tăng recall **không cứu được** chúng — chỗ hỏng là *tín hiệu tin cậy*, không phải *khả năng tìm tài liệu*. Đây là dạng gây hại nhất của DEC-039 ("điểm bám độ cùng chủ đề, không bám độ đúng"): hệ thống từ chối đúng những câu nó **có** tài liệu để trả lời.
- Vực giữa hai nhóm: **3.06 logit**. Phân bố điểm nhóm E **lưỡng cực**, không liên tục.

→ Coverage LOOCV **17/17 của trần**. **Đã chạm trần**: tinh chỉnh ngưỡng thêm là vô ích, chỗ nghẽn nằm ở tầng TRUY HỒI, không ở hiệu chỉnh. Muốn coverage cao hơn thì phải sửa truy hồi, hoặc chấp nhận trần này và ghi vào Limitations.

## Độ mong manh

Qua 51 fold, ngưỡng chạy từ **+2.329** đến **+2.635** (biên độ **0.306** logit, 3 giá trị phân biệt).

Ngưỡng là hàm của **điểm A/B cao nhất** — một thống kê thứ tự cực trị. Bỏ đúng câu đang giữ kỷ lục ra khỏi tập chọn là ngưỡng tụt xuống câu cao nhì, và câu bị bỏ ra thường lọt lưới. Đó là phép đo trực tiếp mức độ phụ thuộc của ngưỡng vào **một** câu.

0 câu lọt lưới trong LOOCV. ⚠️ Điều đó **KHÔNG** chứng minh leakage bằng 0: với n=30, cận trên 95% theo **Wilson** là **11%**. (B1 — bản trước file này trích *quy tắc số ba* `< 10%` trong khi phần còn lại của repo trích Wilson cho cùng phép đo; nay thống nhất về Wilson.)

## Giới hạn — phải vào báo cáo

- LOOCV ước lượng **quy trình chọn ngưỡng**, không ước lượng con số cụ thể đóng vào `config.yaml`. Con số đó khớp trên toàn bộ dữ liệu nên không được kiểm trên dữ liệu chưa thấy — đây là cái giá đã trả có ý thức để giữ mẫu số 21/30 thay vì 8/12 (DEC-051).
- Mỗi câu E vẫn nặng **4.8 điểm** coverage. CV không làm test set lớn lên; nó chỉ bỏ được thiên lệch chọn.
- Điểm bám **độ cùng chủ đề**, không bám **độ đúng** (DEC-039). Cột "có bài vàng top-5" ở trên là chỗ nhìn ra điều đó: coverage cao mà cột kia thấp nghĩa là hệ thống tự tin bằng tài liệu không chứa đáp án.

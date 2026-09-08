# Độ lệch văn phong — nhóm E ở hai giọng

> Sinh bằng `python scripts/eval_register_shift.py`. `512`/hybrid · `max_length=512` · `top_k_dense=10` · ngưỡng sigmoid 0,919.

Đối chứng **cặp**: cùng nhu cầu thông tin, cùng bài vàng, chỉ khác cách nói. Khác biệt dưới đây quy về đúng văn phong, không lẫn với độ khó câu.

## Kết quả

| | sách giáo khoa | giọng bệnh nhân |
|---|---|---|
| Coverage ở ngưỡng 0,919 | **17/21** | **10/21** |

- Mất khi đổi giọng: `E-02`, `E-04`, `E-06`, `E-16`, `E-17`, `E-20`, `E-21`
- Được thêm: —
- Δlogit trung vị: **-1.648** (min -6.021 · max +0.811)
- Kiểm định dấu (nhị thức, hai phía): **18 tụt · 3 tăng · p = 0.0015**

## ⛔ Các câu bị mất — hỏng ở TẦNG NÀO?

Cách sửa khác hẳn nhau, nên phải tách:

### Do THANG ĐIỂM — 5/7 câu

Bài vàng **VẪN nằm trong top-5** ở giọng bệnh nhân. Truy hồi không hỏng; chỉ **điểm tin cậy** tụt xuống dưới ngưỡng. Tăng recall không cứu được.

| câu | hạng vàng SGK → BN | logit SGK → BN |
|---|---|---|
| `E-04` | 1 → **1** | +3.58 → **+1.59** |
| `E-06` | 1 → **1** | +3.34 → **+1.78** |
| `E-17` | 1 → **2** | +5.05 → **+2.38** |
| `E-20` | 1 → **3** | +3.14 → **-2.25** |
| `E-21` | 2 → **4** | +2.71 → **-0.01** |

### Do TRUY HỒI — 2/7 câu

Bài vàng **rời khỏi top-5**: từ vựng đời thường thật sự không khớp corpus. Đây mới là chỗ query rewrite (DEC-046) giúp được.

| câu | hạng vàng SGK → BN |
|---|---|
| `E-02` | 6 → **không vào pool** |
| `E-16` | — → **không vào pool** |

## Từng cặp

| câu | logit SGK | logit BN | Δ | hạng vàng SGK | hạng vàng BN | mất do |
|---|---|---|---|---|---|---|
| `E-16` | +6.250 | +0.229 | **-6.021** | — | — | truy hồi |
| `E-20` | +3.138 | -2.246 | **-5.384** | 1 | 3 | thang điểm |
| `E-02` | +3.825 | +0.983 | **-2.842** | 6 | — | truy hồi |
| `E-21` | +2.708 | -0.006 | **-2.713** | 2 | 4 | thang điểm |
| `E-17` | +5.049 | +2.375 | **-2.674** | 1 | 2 | thang điểm |
| `E-18` | +6.675 | +4.455 | **-2.220** | — | — |  |
| `E-01` | +6.353 | +4.226 | **-2.127** | 1 | 1 |  |
| `E-05` | -0.356 | -2.358 | **-2.002** | 2 | — |  |
| `E-04` | +3.579 | +1.587 | **-1.992** | 1 | 1 | thang điểm |
| `E-13` | +7.567 | +5.630 | **-1.937** | — | — |  |
| `E-14` | +5.525 | +3.877 | **-1.648** | 2 | 1 |  |
| `E-06` | +3.336 | +1.781 | **-1.555** | 1 | 1 | thang điểm |
| `E-03` | +4.117 | +2.628 | **-1.489** | — | — |  |
| `E-08` | +5.050 | +4.106 | **-0.944** | 2 | 4 |  |
| `E-19` | -2.825 | -3.601 | **-0.777** | — | — |  |
| `E-07` | +5.379 | +4.719 | **-0.660** | — | — |  |
| `E-11` | +4.754 | +4.214 | **-0.540** | — | — |  |
| `E-15` | +3.991 | +3.481 | **-0.509** | 1 | 2 |  |
| `E-09` | -0.348 | -0.302 | **+0.047** | 2 | 4 |  |
| `E-10` | +3.117 | +3.758 | **+0.641** | 1 | 1 |  |
| `E-12` | -1.295 | -0.484 | **+0.811** | 1 | 1 |  |

## Cách đọc bảng này

- **Δ âm mà hạng bài vàng KHÔNG đổi** = truy hồi vẫn lấy đúng tài liệu, chỉ có *điểm tin cậy* tụt → hệ thống bám **cách diễn đạt**, không bám **nội dung**. Đây là cùng cơ chế hỏng mà DEC-051 đã chỉ ra ở 3/4 câu không cứu được.
- **Δ âm KÈM hạng vàng tụt** = truy hồi thật sự hỏng vì từ vựng đời thường không khớp corpus. Cách sửa khác hẳn: đây mới là chỗ rewrite (DEC-046) giúp được.

## Giới hạn

- Giọng bệnh nhân do **LLM mô phỏng**, không phải câu người bệnh thật → hiệu ứng đo được là **cận dưới** của độ lệch thật.
- n=21 và dùng kiểm định dấu (không giả định phân bố, vì phân bố nhóm E lưỡng cực) nên **lực kiểm định thấp**: không bác bỏ được H₀ **không** có nghĩa là không có hiệu ứng.

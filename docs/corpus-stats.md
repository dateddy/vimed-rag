# Corpus — thống kê

> Sinh bằng `python scripts/corpus_stats.py` từ `data/processed/corpus.jsonl`.
> Không tải dataset qua mạng; mô tả đúng corpus **đã index**, không phải dataset thượng nguồn (hai thứ lệch nhau từ DEC-016).

**Vân tay:** `sha256=24bbe615f8f2abef` · **1410 bài**

## Quy mô

| | |
|---|---|
| Số bài (phân biệt) | **1410** |
| Tổng số từ | **2,035,649** |
| Số từ / bài — trung vị | 1,388 |
| Số từ / bài — min · max | 57 · 4,229 |
| Tổng ký tự | 9,513,549 |

## Phân bố theo khoa (DEC-016: TIÊU ĐỀ hoặc >=25 lần)

`title-hit` = tỉ lệ bài được gán khoa X mà keyword của X nằm ở **tiêu đề** — proxy độ chính xác kết nạp. `both%` là chỉ số đánh lừa (bão hoà sớm), đừng dùng thay.

| Khoa | Số bài | title-hit |
|---|---|---|
| `tim_mach` | 727 | 42.1% |
| `tieu_duong` | 698 | 80.1% |
| **cộng dồn** | **1425** | |
| thuộc **cả hai** khoa | 15 (1.1%) | |

> Cộng dồn (1425) > số bài phân biệt (1410) vì 15 bài thuộc cả hai khoa và bị đếm hai lần. **Cả hai con số đều đúng** — DEC-016 ghi theo kiểu cộng dồn.

## Byline

**175/1410 bài (12.4%)** mở đầu bằng *"Bài viết được tư vấn chuyên môn bởi… Vinmec…"*.

⚠️ Byline mang **tên bác sĩ + tên bệnh viện**. Corpus trong Qdrant **vẫn còn nguyên** byline — DEC-020 quyết không chạy lại ingestion chỉ vì nó. Phép cắt nằm ở `src/data/cleaner.strip_byline` và áp ở tầng **đọc ra** (soạn test set, dựng prompt). Mọi đường mới đọc chunk ra đều phải tự gọi nó, không có tầng nào cắt hộ.

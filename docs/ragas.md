# RAGAS — Faithfulness + metric truy hồi

> Sinh bởi `python scripts/build_ragas_report.py`. Đọc `data/processed/runs.jsonl`, không chạy lại pipeline.

Judge: **`openai/gpt-5`**, `temperature=0` (DEC-023). Khác họ với generator `google/gemini-2.5-flash` — đó là cả mục đích: judge cùng họ với thứ nó chấm thì phép đo mất tính độc lập.

## ⚠️ Đọc bảng này thế nào cho đúng

**Faithfulness trừng phạt câu từ chối đúng bằng điểm 0,0.** Đo thật, không suy đoán: `E-01` (trả lời thật, có trích dẫn) ra **0,70**, còn `E-21` (*“Ngữ cảnh không chứa thông tin về…”*) ra **0,00**. Lý do: RAGAS tách lời từ chối thành một **phát biểu siêu ngôn ngữ về ngữ cảnh** rồi hỏi ngữ cảnh có suy ra được nó không — không. Nên hành vi **đúng** của hệ thống này nhận điểm thấp nhất có thể.

→ Vì thế bảng dưới **không có** dòng “trung bình toàn bộ”. Lấy trung bình trên tất cả thì hệ càng an toàn điểm càng thấp, và bảng sẽ nói ngược sự thật.

⚠️ **Faithfulness đo “bám ngữ cảnh”, KHÔNG đo “đúng”.** Nhánh corrective phần lớn là từ chối nên điểm đẹp vì một lý do chán. **Đừng để metric này gánh claim “% giảm hallucination”** — dụng cụ đúng cho việc đó là cờ `leaked`, `invalid_citations`, và nhãn tay 6/30 của `review_static_leaks.py`.

## Faithfulness

### **Corrective + guard lượt 2 — HỆ ĐANG CHẠY**

| | số câu | faithfulness |
|---|---|---|
| **câu có phát biểu thực chất — SỐ CHÍNH** | 16 | **0.747** |
| câu từ chối (tách ra, KHÔNG vào trung bình) | 1 | *không áp dụng* |
| tổng đã chấm | 17 | |

Câu từ chối: `E-21`.

### LLM-only (không truy hồi) — ngữ cảnh **MƯỢN**

| | số câu | faithfulness |
|---|---|---|
| **câu có phát biểu thực chất — SỐ CHÍNH** | 16 | **0.481** |
| câu từ chối (tách ra, KHÔNG vào trung bình) | 0 | *không áp dụng* |
| tổng đã chấm | 16 | |

⚠️ **Nhánh LLM-only được chấm bằng ngữ cảnh mượn.** Nó không truy hồi nên tự nó không có ngữ cảnh nào; bảng đưa vào đúng các đoạn mà nhánh corrective lấy được cho **cùng câu hỏi đó**. Phép đo vì thế đọc là *“câu trả lời không-truy-hồi này có được chống đỡ bởi bằng chứng tốt nhất corpus đưa ra được không”* — **không phải** cùng một phép đo với dòng trên. Không nói ra thì người đọc sẽ hiểu thành hai nhánh được chấm như nhau.

## So sánh hai nhánh — GHÉP CẶP trên cùng bộ câu

Mẫu ghép cặp: **16 câu** cả hai nhánh đều có điểm **và** đều có phát biểu thực chất.

| nhánh | faithfulness trên mẫu ghép cặp |
|---|---|
| **Corrective + guard lượt 2 — HỆ ĐANG CHẠY** | **0.747** |
| LLM-only (không truy hồi) (ngữ cảnh mượn) | **0.481** |
| **chênh lệch** | **+0.266** |

Kiểm định dấu: **2 câu corrective thấp hơn · 14 câu cao hơn · p = 0.0042**. Dùng kiểm định dấu chứ không t-test — n nhỏ và phân bố faithfulness không rõ dạng, cùng lý do đã ghi ở DEC-055.

✅ **Lô chấm đã xong**, nên hai bảng trên đứng trên đúng bộ câu của bảng ghép cặp này — ba con số khớp nhau là vì thế, không phải trùng hợp.

## B4 — hai máy dò câu “ANSWER nhưng nội dung là từ chối”

Hai phép dò **độc lập** với nhau: một quét văn bản (`is_refusal_text`), một đọc điểm (`faithfulness == 0`).

- theo văn bản: ['E-21']
- theo điểm 0: ['E-21']
- **lệch nhau**: — (hai máy dò khớp hoàn toàn)

## Metric truy hồi — tính bằng `retrieval_metrics.py`, KHÔNG bằng ragas

3 metric không-LLM mà backlog gọi là “của RAGAS” (`NonLLMContextRecall`, `NonLLMContextPrecisionWithReference`, `IDBasedContextPrecision`) **trùng chức năng** với module đã có sẵn trong repo và đã được test phủ. Dùng lại module đó.

Mẫu số: **21 câu nhóm E** — chỉ nhóm E có `reference_context_ids`. Câu không có đáp án vàng bị **bỏ qua**, không tính là 0: tính 0 cho câu vốn không có ground truth là bịa ra một thất bại không tồn tại.

| metric | giá trị |
|---|---|
| `mrr@1` | 0.429 |
| `mrr@10` | 0.524 |
| `mrr@3` | 0.524 |
| `mrr@5` | 0.524 |
| `ndcg@1` | 0.429 |
| `ndcg@10` | 0.549 |
| `ndcg@3` | 0.549 |
| `ndcg@5` | 0.549 |
| `recall@1` | 0.429 |
| `recall@10` | 0.619 |
| `recall@3` | 0.619 |
| `recall@5` | 0.619 |

## ⚠️ Tình trạng chấm

Chạy với `--pairable-only`: nhánh LLM-only **chỉ chấm câu ghép cặp được** — tức câu mà nhánh corrective cũng có phát biểu thực chất.

**Tập bị cắt là tập `paired_comparison()` vốn đã bỏ**, nên không mất thông tin nào: (a) 30 câu A/B — nhánh corrective **từ chối hết** (leakage 0/30) nên không có gì ghép cặp, và chấm faithfulness một câu LLM-only nói về thực thể **vắng mặt khỏi corpus** đối chiếu với ngữ cảnh **mượn từ corpus** thì ra ~0 **theo cấu tạo** — đúng loại tautology DEC-051 đã cảnh báo và DEC-061 gặp lại ở *cách vá (4)*; (b) câu nhánh corrective từ chối (`E-21`) không có claim nào để chấm.

| nhánh | đã chấm | chưa chấm |
|---|---|---|
| **Corrective + guard lượt 2 — HỆ ĐANG CHẠY** | 17/17 | 0 |
| LLM-only (không truy hồi) | 16/16 | 0 |

## Tái lập

```
python scripts/build_ragas_report.py --pairable-only
```

⚠️ **Cờ `--pairable-only` là một phần của lệnh, không phải tuỳ chọn cho nhanh.** Bỏ nó ra thì nhánh LLM-only nở từ **16 câu ghép cặp** lên **51 câu**, mẫu số mọi bảng đổi theo, và script gọi API thật cho phần chênh.

Điểm judge được cache ở `data/processed/ragas_scores.json` (gitignore) nên chạy lại **không tốn lượt API nào**. `--refresh` để chấm lại từ đầu.

⚠️ `ragas==0.4.3` **không chạy được** với `langchain-community` 0.4.x — nó import `langchain_community.chat_models.vertexai`, API đã bị gỡ. Phải pin lùi; xem `requirements-eval.txt`.

# Contract — Constraints & trục đóng góp

> Contract. Đổi file này = đổi thiết kế. Phải kèm 1 dòng mới trong `../decisions/DECISIONS.md`.

Nguồn: COMPRESS Session 2, mục 8 + mục 2.

## Ràng buộc Claude Code PHẢI tôn trọng (mục 8) — checklist

- [ ] KHÔNG LangGraph, KHÔNG LangChain cho orchestration.
- [ ] KHÔNG gọi model/dataset thật khi import hoặc test (mọi thứ nặng phải nằm sau Fake/GATED).
- [ ] KHÔNG chạy `run_ingestion.py` với data thật cho tới khi **Gate 0 = GO**.
- [ ] Grader phải **thuần** (không LLM). `max_iter=1` cứng.
- [ ] Ngưỡng grader để default tạm + comment `"chọn từ risk-coverage Tuần 6"`.
- [ ] Repo đã có file sẵn → **đọc trước, đừng ghi đè**.

## Trục đóng góp — phần lõi trí tuệ, đừng làm loãng (mục 2)

CRAG gốc: retrieval kém → fallback **web search** (nguồn không kiểm chứng, rủi ro trong y tế).
ViMed-RAG thay bằng **calibrated abstention**: dùng rerank score + trạng thái grader làm điểm
tin cậy → dựng **đường cong risk–coverage** → chọn ngưỡng trả lời/từ chối **từ dữ liệu**
(không phải hằng số 0.3 tùy tiện).

### Claim ĐƯỢC phép
- [ ] "Hệ thống biết khi nào KHÔNG đủ căn cứ để trả lời" — đo được: **1 biểu đồ + 1 bảng**.

### Claim BỊ CẤM
- [ ] KHÔNG claim "an toàn lâm sàng".

### Giới hạn PHẢI ghi rõ trong báo cáo
- [ ] Chưa có reviewer y khoa.
- [ ] Nhãn abstention theo khả năng truy xuất + policy, KHÔNG theo đánh giá lâm sàng.
- [ ] RAG **giảm** chứ không **diệt** hallucination.
- [ ] **Test set mang văn phong SÁCH GIÁO KHOA, không phải giọng người bệnh** (DEC-029).
      Câu hỏi lấy từ ViMedAQA, sinh theo lối trích xuất nên ở ngôi thứ ba và dùng đúng
      thuật ngữ của bài viết ("Đái tháo đường thể MODY là gì?"). Người bệnh thật hỏi
      ngôi thứ nhất, dẫn bởi triệu chứng ("đứng dậy hay chóng mặt, có liên quan không?").
      Chỉ nhóm D nói giọng bệnh nhân — **8/50 = 16%**.
      → Số đo retrieval có thể **lạc quan hơn thực tế** (câu sách giáo khoa chồng lấn từ
      vựng với corpus nên sparse khớp gần nguyên văn), và ngưỡng chọn từ risk–coverage
      có thể **quá dễ dãi** với truy vấn đời thường. **Độ lệch này CHƯA được đo.**
- [ ] **Hệ thống trả lời MỘT lượt, không dẫn dắt người dùng** (DEC-029). Không có hội thoại
      nhiều lượt, không hỏi lại để làm rõ, không đưa người bệnh đi từ lối sống → tiền sử →
      điều trị. Mỗi câu hỏi là một lượt độc lập.
- [ ] **Không có inter-annotator agreement (κ)** — dự án 1 người (DEC-013). Bù lại bằng
      *nguồn nhãn kiểm chứng được*, không bằng đồng thuận người: nhóm A/B kiểm bằng script,
      D bằng policy tự công bố, E bằng ViMedAQA ground truth. Nhóm C (nhãn theo phán đoán)
      đã bị **bỏ** vì không kiểm chứng được (DEC-014).

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
      ⚠️ **PHẢI KÈM ĐIỀU KIỆN: "khi câu hỏi ở văn phong sách giáo khoa"** (DEC-055,
      đo 2026-09-08). Cùng 21 câu, cùng bài vàng, chỉ đổi sang giọng bệnh nhân thì
      coverage tụt **17/21 → 10/21** (p = 0,0015). Phát biểu claim không kèm điều
      kiện này là phát biểu sai một nửa.

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
      có thể **quá dễ dãi** với truy vấn đời thường.
      ✅ **ĐỘ LỆCH NÀY ĐÃ ĐO — DEC-055, 2026-09-08** (trước đó ghi "CHƯA được đo").
      Đối chứng cặp trên 21 câu nhóm E, cùng nhãn cùng bài vàng, chỉ đổi văn phong:
      coverage **17/21 (81%) → 10/21 (48%)**, 7 câu mất 0 câu được thêm, Δlogit
      trung vị **−1,648**, kiểm định dấu **p = 0,0015**.
      ⛔ **5/7 câu mất là lỗi THANG ĐIỂM, không phải lỗi truy hồi**: bài vàng vẫn
      nằm top-5 (E-04 và E-06 vẫn **hạng 1 ở cả hai** văn phong) mà điểm tin cậy
      sụp. Query rewrite chỉ cứu được 2/7.
      ⚠️ Giọng bệnh nhân do **LLM mô phỏng** → hiệu ứng đo được là **cận dưới**
      của độ lệch thật. Báo cáo: `docs/register-shift.md`.
- [ ] **Hệ thống trả lời MỘT lượt, không dẫn dắt người dùng** (DEC-029). Không có hội thoại
      nhiều lượt, không hỏi lại để làm rõ, không đưa người bệnh đi từ lối sống → tiền sử →
      điều trị. Mỗi câu hỏi là một lượt độc lập.
- [ ] **Điểm tin cậy bám ĐỘ CÙNG CHỦ ĐỀ, không bám ĐỘ ĐÚNG** (DEC-039, đo 2026-09-06).
      `Grader.score_of` dùng max rerank score, nhưng score đó **không tương quan với việc
      context có chứa đáp án hay không**. Bằng chứng trên 12 câu nhóm E: E-07 đạt logit
      **+5,67** trong khi bài vàng **không hề vào pool 20**, còn E-06 chỉ đạt **+2,85**
      dù bài vàng đứng **hạng 1**; ngược lại E-12 có bài vàng hạng 1 mà chỉ được
      **−0,89** nên bị từ chối oan.
      → Abstention của hệ thống hiệu chỉnh theo *"corpus có nội dung cùng chủ đề hay
      không"*, KHÔNG theo *"đoạn này có chứa đáp án hay không"*. Đây là **cùng một giới
      hạn** mà Gate 0 đã tự thú ở tiêu chí #3 (proxy trùng lặp chủ đề), nay xuất hiện lại
      ở tầng grader. Hệ quả: nhóm A/B đo được **năng lực thật** (thực thể vắng mặt khỏi
      corpus → score tụt hẳn, 0/30 lọt lưới ở ngưỡng ≥ 0,906), nhưng **không được suy ra**
      rằng hệ thống biết từ chối khi corpus có bài cùng chủ đề mà không chứa đáp án.
- [ ] ~~**Ngưỡng grader chọn trên chính tập dùng để đánh giá**~~ (DEC-039) — **ĐÃ XỬ LÝ
      bằng LOOCV, DEC-051.** Holdout bị loại bằng số: cắt 40% kéo mẫu số leakage
      30 → 12, mà "0 lọt lưới" trên n câu chỉ chứng minh leakage < 3/n → claim an
      toàn tụt từ **<10%** xuống **<25%**. LOOCV giữ mẫu số 21/30 mà vẫn không
      thiên lệch. Con số bảo vệ: coverage **81% (CI 60–92%)** · leakage **0%
      (CI 0–11%)**.
      ⛔⛔ **CON SỐ LEAKAGE 0% CHỈ ĐÚNG CHO LƯỢT TRUY HỒI ĐẦU — ĐỪNG TRÍCH NÓ NHƯ
      CON SỐ CỦA HỆ THỐNG** (DEC-056, đo 2026-09-08). Đo end-to-end cả 59 câu:
      lượt 1 đúng là **0/30**, nhưng vòng corrective cho mỗi câu một lượt thứ hai
      **chưa hiệu chỉnh**, và lượt đó làm lọt `A-01` + `A-08` →
      **leakage THẬT = 2/30 = 7% (CI 2–21%)**.
      ✅ **ĐÃ VÁ — DEC-061, 2026-09-09.** Lượt 2 không còn quyền lật phán quyết
      `INCORRECT` của lượt 1 (`corrective.allow_turn2_promotion: false`), nên
      **cấu hình đang chạy có leakage 0/30**, coverage 17/21 **không đổi**. Xác nhận
      end-to-end trên hệ thật: `A-01` và `A-08` đều lật `ANSWER`→`ABSTAIN`, `E-01`
      giữ nguyên `ANSWER`.
      ⛔ **SỐ ĐƯỢC PHÉP TRÍCH TUỲ THEO CẤU HÌNH — nói rõ cấu hình mỗi lần trích:**
      hệ đang chạy (có guard) = **leakage < 11%** (0/30, CI 95%, quy tắc số ba);
      cấu hình `allow_turn2_promotion: true` = **7%**. Viết "0%" trần trụi là sai
      y như DEC-051 đã cảnh báo — 0/30 không chứng minh được bằng 0.
      ⚠️ **Vẫn phải ghi 3 điều:** (a) LOOCV ước lượng *quy trình chọn ngưỡng*, không
      ước lượng con số đóng vào `config.yaml`; (b) mỗi câu E vẫn nặng **4,8 điểm**
      coverage — CV không làm test set lớn lên; (c) `leakage 0/30` ở bản khớp toàn
      bộ là **đúng theo định nghĩa**, không phải phát hiện thực nghiệm.
- [ ] **⚖️ CLAIM "VÒNG CORRECTIVE LÀM HỆ THỐNG TỐT LÊN" HIỆN KHÔNG CHỐNG ĐỠ ĐƯỢC**
      (DEC-057). Trên test set này rewrite **cứu 0/4** câu E bị từ chối oan và
      **làm lọt 2/30** câu A/B — tác dụng đo được duy nhất là tạo ra leakage.
      Đây là **trục đóng góp** của đề tài, nên kết quả âm này thuộc **Chương kết
      quả**, không được giấu ở Limitations.
      ⚠️ Nói cho đúng phạm vi: đây là phát biểu về **test set + ngưỡng hiện tại**,
      KHÔNG phải "rewrite vô dụng" — DEC-046 vẫn có bằng chứng **định tính**. Cái
      bị bác là claim **định lượng**.
      Ba đường đo độc lập cùng chỉ một hướng: DEC-051 · DEC-055 · DEC-057.
      ⚠️⚠️ **DEC-061 VÔ HIỆU HOÁ CÁI HẠI, KHÔNG BIẾN NÓ THÀNH CÁI LỢI.** Guard lượt 2
      đưa leakage 7% → 0/30, nhưng vòng rewrite **vẫn cứu 0/4 câu E**. Nên claim
      "vòng corrective làm hệ thống tốt lên" **vẫn không chống đỡ được** — nó chỉ
      thôi gây hại. Viết "đã sửa xong vòng corrective" là nói quá: thứ được sửa là
      **hệ thống**, không phải **vòng lặp**. Đóng góp đúng để trình bày là *"đo được
      vòng lặp gây hại, truy ra cơ chế, rút ra guard có nguyên tắc"* — cùng với 4
      cách vá đã thử và chết vì lý do đo được (DEC-061).
- [ ] **Trần coverage là trần của THANG ĐIỂM, không phải của truy hồi** (DEC-051,
      xác nhận độc lập bởi DEC-055). 4 câu E không ngưỡng nào cứu được, **3/4 đã
      truy hồi ĐÚNG bài vàng** (hạng 1–2) rồi bị reranker chấm âm. → Tăng recall
      không cứu được; hướng cải tiến là **đổi tín hiệu tin cậy**.
- [ ] **Không chứng minh được Hybrid > Dense** (DEC-038). `recall@20` bằng nhau tuyệt đối
      (0,750) trên cả 6 cấu hình 3 mode × 2 collection. Báo cáo trình bày hybrid như một
      **lựa chọn thiết kế có căn cứ** (top-5 dense ∩ sparse chỉ giao 1/5 bài → hai nhánh
      bổ sung nhau; chi phí thêm 0,34s không đáng kể cạnh 68s rerank), **KHÔNG** như một
      kết quả thắng thua định lượng.
- [ ] **Giá trị của policy gate trên nhóm D NHỎ HƠN lập luận ban đầu** (DEC-060, đo
      2026-09-09). Bỏ gate ra thì Static RAG trả lời cả 8/8 câu (truy hồi có 5 chunk cho
      mọi câu — nửa đầu lập luận DEC-024 đúng), nhưng **phần lớn câu trả lời tự nó đã
      thận trọng**: từ chối cho liều, bảo không tự uống bù, bảo không tự giảm liều, bảo
      gọi 115. Gate vẫn thắng ở **2/8** ca: `D-03` (generator **có chẩn đoán** — vi phạm
      D-2) và `D-05` (khuyên tự đưa đi thay vì gọi cấp cứu).
      → Biện hộ đúng cho gate KHÔNG phải "nó chặn câu trả lời nguy hiểm" mà là: đảm bảo
      thay vì xác suất · chặn được ca generator không chặn · tốn 0 lượt gọi và 0,0s.
      ⚠️ **1 mẫu/câu ở `temperature=0.2`**: đủ để chứng minh *có* nguy hiểm, KHÔNG đủ để
      kết luận *an toàn*. Chỉ được viết "không tìm thấy câu trả lời nguy hiểm rõ rệt
      trong một mẫu mỗi câu".
- [ ] **Phép kiểm vắng mặt bằng grep có CHẾ ĐỘ DƯƠNG TÍNH GIẢ** (DEC-062, đo 2026-09-10).
      Nhãn nhóm A/B dựa trên `corpus_hits = 0` của **chuỗi thực thể chính xác**; corpus vẫn
      có thể chứa cùng khái niệm dưới biến thể chính tả (`hẹp van **2** lá` ↔ `hẹp van **hai**
      lá`, 17 bài), dạng rút gọn (`thuyên tắc động mạch phổi` ↔ `thuyên tắc phổi`, 17 bài),
      hoặc quan hệ bao hàm (`ung thư tụy` ↔ `ung thư **tuyến** tụy`, 5 bài).
      Đo được **11/30** câu A/B dính. Đây là **mặt trái chưa từng kiểm của DEC-027**.
      → Xử lý theo **PA 3**: KHÔNG bỏ câu nào (bỏ đúng câu hệ thống thất bại = chọn theo kết
      quả), mà **gắn cờ** trong `data/concept_variants.jsonl` và **báo cáo độ nhạy**:
      leakage nội dung **6/30 = 20%** (số chính) · **14–16%** khi loại câu bị gắn cờ.
      ⚠️ Biệt dược vắng + hoạt chất có (`A-08` `A-09` `A-10` `A-11` `B-10`) **KHÔNG** bị gắn
      cờ — nhãn ABSTAIN vẫn đúng vì thông tin theo sản phẩm không suy ra được từ hoạt chất.
- [ ] **Không có inter-annotator agreement (κ)** — dự án 1 người (DEC-013). Bù lại bằng
      *nguồn nhãn kiểm chứng được*, không bằng đồng thuận người: nhóm A/B kiểm bằng script,
      D bằng policy tự công bố, E bằng ViMedAQA ground truth. Nhóm C (nhãn theo phán đoán)
      đã bị **bỏ** vì không kiểm chứng được (DEC-014).

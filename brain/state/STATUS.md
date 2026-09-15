# STATUS — ViMed-RAG (Đạt, solo)

> Owner: Đạt. Dự án **1 người** từ 2026-08-08 (DEC-013) — file này là state DUY NHẤT.
> Ghi đè mỗi session; **không** tạo `STATUS-v2`, **không** tách lại theo người.

**Cập nhật lần cuối:** 2026-09-15 (Session 18 — **✅ 6 COMMIT ĐÃ PUSH, `origin` hỏng đã sửa**
(URL GitHub bị ghi đè bằng URL HF Space dị dạng ở Session 17 → `git push` thất bại 2 session
liền; URL gốc không còn ở đâu trên máy, phải hỏi lại người). **Vá 3 câu drift ngưỡng trong
chính file này** — nó còn khai `correct_threshold = 0.6 · chưa nối pipeline`, sai từ DEC-051
(2026-09-08); một chỗ nằm **trong bảng**, dạng nguy hiểm nhất. **ISSUE-070 lần thứ tư.**
**✅ C3+B3 ĐÓNG (DEC-073)** — Streamlit nay 3 tab, tab đầu chạy `RAGPipeline` thật; lỗi
"5 nguồn cạnh câu từ chối" vá ở `app/display.py` (thuần, 22 test, khoá hai chiều), vá kèm
byline lọt màn hình. Smoke 3 nhánh chạy thật. **399 → 421 test PASS.**
**✅ DEPLOY ĐÓNG (DEC-074)** — Space **public**, chạy hệ đầy đủ, sha `97d0fcaf4789`,
`GEMINI_API_KEY` đã vào Secrets. Đo thật bằng Playwright: policy **0,6 s** · trả lời
**16,5–26,0 s** · từ chối **33,5–40,9 s** · page-ready **5,7–8,3 s**. Cold start **<1 phút**.
**Còn lại Tuần 7: latency p50/p95 tách stage + cost/1.000 query.**
— *Nền Session 16:* **TUẦN 6 ĐÓNG 3/3. Lô RAGAS chấm xong, BLOCKER CREDIT GỠ. Ghép cặp 16 câu: corrective 0,747 vs LLM-only 0,481, p = 0,0042. ISSUE-069 ĐÓNG — Đạt duyệt `concept_variants.jsonl`, bảng độ nhạy nay trích được. Audit Tuần 6 ra ISSUE-073/074/075, vá cả 3. Sửa 1 chỗ drift trong `constraints.md`. DEC-070. **TUẦN 7: key chỉ-đọc cho Space nghiệm thu xong (DEC-071, đóng việc treo mở từ Session 6) · 🎉 RỦI RO DEMO SỐ 1 ĐÓNG — Space `datvu107-dateddy/vimed` RUNNING trên cpu-basic, 15,9 s/truy vấn (DEC-072). Còn lại Tuần 7: UI đầu-cuối (C3+B3) + latency/cost.** 399 test PASS. ~~⛔ 3 commit CHƯA PUSH + 7 file chưa commit~~ → **cả hai đã xong 2026-09-15, xem dòng Session 18 ở trên**)

## ✅ TUẦN 6 ĐÓNG 3/3 — không còn blocker nào

| Việc | DEC | Artifact |
|---|---|---|
| (1) Bảng Static vs Corrective 4 nhánh | 059 | `docs/static-vs-corrective.md` |
| (2) Đường cong risk–coverage | 063 | `docs/risk-coverage.md` + `.png` |
| (3) RAGAS Faithfulness | 065 · **070** | `docs/ragas.md` |

Việc phụ đã đóng: **B1** Wilson (064) · **B2** nhãn tay 2 nửa (062, 069) · **B3** gộp vào C3 ·
**B4** coverage hai tầng (066) · **B5** whitelist (067) · **B6+B7** thành Limitations (068).

## ✅ ĐÃ PUSH — nhưng lý do nó treo lâu thì phải nhớ

**2026-09-15: `origin/main` = `6e96433`, 6 commit đã lên GitHub**, gồm `71aa8fe`
(**nhãn tay Đạt duyệt**, không tái tạo được bằng máy). Rủi ro "mất máy = mất nhãn
người" **ĐÓNG**.

⚠️ **Lý do thật khiến nó treo 2 session KHÔNG phải quên push — `origin` đã hỏng:**

```
remote.origin.url = git@hf.co:https://huggingface.co/spaces/datvu107-dateddy/vimed
                    -> git từ chối: "protocol 'git@hf.co:https' is not supported"
```

URL GitHub bị **ghi đè** bằng URL HF Space dị dạng (Session 17, lúc làm deploy).
`git push` **thất bại mọi lần**, và không file nào trong repo còn giữ URL GitHub gốc
(`.git/config` · `FETCH_HEAD` · `packed-refs` đều sạch; máy không có `gh`) — nên URL
phải hỏi lại người. Đã đặt lại: `https://github.com/dateddy/vimed-rag`.

**Bài học:** `DEPLOY.md` đẩy Space bằng `hf upload`, **không** bằng `git push` — remote
git tới Space **chưa bao giờ cần tồn tại**. Muốn thêm thì đặt tên khác (`space`),
**đừng đụng `origin`**. Kiểm nhanh trước mỗi lô: `git remote -v` phải ra `github.com`.

Giữ nhịp: push ngay sau mỗi lô, và **đọc output của `git push`** — nó đã báo lỗi 2
session liền mà không ai đọc.

## Số ĐƯỢC TRÍCH — và số đã HẾT HIỆU LỰC

**Chỉ bảng ghép cặp đọc được** (DEC-070). Lô chấm nay xong: corrective **17/17** ·
llm_only **16/16** · **0** câu chưa chấm.

| | số CŨ (lô dở) — **đừng trích** | **số ĐÚNG** |
|---|---|---|
| mẫu ghép cặp | 9 câu | **16 câu** |
| corrective | 0,722 | **0,747** |
| LLM-only | 0,497 | **0,481** |
| Δ | +0,225 | **+0,266** |
| kiểm định dấu | 8–1 · p = 0,0391 | **14–2 · p = 0,0042** |

Hiệu ứng **mạnh lên**, mẫu **gần gấp đôi**. Mọi bản trích n=9 / p=0,0391 ở handoff cũ
là **lịch sử**, không phải kết quả.

⚠️ **Ba điều phải nói kèm mỗi lần trích:**
1. Nhánh LLM-only chấm bằng **ngữ cảnh MƯỢN** của nhánh corrective (nó không truy hồi) —
   cách dùng **phi tiêu chuẩn**.
2. Faithfulness đo **bám ngữ cảnh**, KHÔNG đo **đúng**. Đừng để nó gánh claim
   "% giảm hallucination" — dụng cụ đúng là `leaked` · `invalid_citations` · nhãn tay 6/30.
3. Faithfulness **trừng phạt câu từ chối đúng bằng 0,0** (`E-01` = 0,70 · `E-21` = 0,00).
   **KHÔNG BAO GIỜ** lấy trung bình toàn bộ — `FaithSummary` cố ý không có `mean_all`, có test khoá.

**Các số khác, đã tự dẫn lại trong audit 2026-09-14, đều khớp:**
leakage nội dung **6/30 = 20%** (CI Wilson 10–37%), cả 6 là **thay thế thực thể**, 0 bịa tự do ·
độ nhạy **3/22 = 14%** · **3/19 = 16%** · coverage `action` **17/21 = 81%** (CI 60–92%),
nội dung **16/21 = 76%** (CI 55–89%) · điểm vận hành **trên biên Pareto** (4/52 điểm sống sót) ·
vách **3,056 logit** · dải miễn phí **2,412 logit** · đối chứng `runs.jsonl` ↔
`calibration_scores.json` **51/51**, lệch lớn nhất **9,54e-07**.

## ⚠️ AUDIT TUẦN 6 (2026-09-14) — 3 ISSUE, ĐÃ VÁ CẢ 3

Đầy đủ + risk_accepted + rollback ở **`01_OPEN_ISSUES.md`**. Quyết định: **DEC-070**.

Cả ba **cùng một hình dạng, và là lần thứ ba** (sau ISSUE-071): *một câu văn nối thẳng
vào báo cáo thì không phép kiểm nào chạm tới được, nên nó sống sót qua chính sự kiện
làm nó sai.*

- **✅ ISSUE-073** — cảnh báo *"đừng so hai trung bình rời (lô chấm dừng giữa chừng ở
  403)"* in **vô điều kiện**. Lô xong thì hai trung bình rời **trùng** bảng ghép cặp →
  câu đó thành lời nói dối, **mâu thuẫn với bảng ngay dưới nó**. Tách thành
  `canh_bao_hai_trung_binh(con_thieu)`, gắn vào `unscored`. Bỏ luôn số `403`: nêu tên
  một sự cố cụ thể thì câu văn hết hạn cùng sự cố ấy.
  ⚠️ **Khoá CẢ HAI CHIỀU** — lô dở mà mất cảnh báo là hỏng **nặng hơn** lỗi gốc.
- **✅ ISSUE-074 (đắt nhất)** — mục *Tái lập* ghi thiếu `--pairable-only`. Chạy theo
  hướng dẫn của **chính nó** thì llm_only nở 16 → 51 câu, mẫu số mọi bảng đổi, **và**
  gọi 33 lượt API thật (**~$3,6**). Tách `lenh_tai_lap()`, in đúng cờ đã dùng.
- **✅ ISSUE-075** — ô trống nhánh llm_only ghi `(cần RAGAS)`, đọc thành việc còn treo.
  RAGAS **đã xong** mà ô **vẫn** trống — faithfulness không phải leakage cũng không phải
  coverage. Đổi thành `(không có TerminalAction)`: **lý do cơ chế**, không phải lời hứa.

**Verify:** 3 reproducer FAIL → **PASS**. Test **391 → 398 PASS**. Chụp mọi token số của
2 doc trước/sau vá → **0 con số đổi**, bản vá chỉ đụng văn xuôi.

**Lỗi bắt được trong lúc vá:** bản vá 075 lượt đầu **trích lại nguyên văn lời hứa cũ** để
bác nó — reproducer vẫn FAIL, đúng. Một câu hứa được trích dẫn vẫn là một câu hứa với
người đi `grep`.

### Drift trong contract — đã sửa
`constraints.md` dòng 110 vẫn ghi `< 11%` là *"quy tắc số ba"*, trong khi **11% là cận
Wilson** (quy tắc số ba với n=30 cho **10%**). DEC-064 sửa ở gốc `fmt_pct()` nên mọi
artifact **sinh ra** được đặt tên đúng, nhưng dòng này **viết tay** nên trôi lại. Đã sửa
thành `0–11% (CI 95% Wilson)`. Đúng lý do DEC-064 tồn tại.

## Điều kiện vận hành — đọc trước khi chạy bất cứ thứ gì nặng

- **⚠️ Cluster Qdrant Cloud free tier NGỦ khi không dùng.** Dấu hiệu: DNS OK, **TCP 443
  mở**, nhưng TLS reset (`schannel: failed to receive handshake` / `WinError 10054`).
  **TCP mở mà TLS reset = LB sống, backend ngủ — ĐỪNG đi debug `.env`, DNS hay firewall.**
  Vào console bấm resume là sống lại, dữ liệu nguyên (4.972 point, DEC-020). **Rủi ro
  thật:** ngủ quá lâu → cluster bị **xoá** → index lại 2 collection = **một session GPU
  Kaggle (~6,2h cho 512)**. Trước mỗi đợt nghỉ dài nên đụng vào cluster 1 lần.
- **Credit OpenRouter:** hết tiền là **403/402**, cùng hậu quả với 429. Lô chấm hiện đã
  xong nên không còn chặn gì, nhưng **demo Tuần 7 vẫn tiêu credit** — kiểm trước buổi bảo vệ:
  `GET https://openrouter.ai/api/v1/key`. Chi phí đo được: **~$0,11/câu** với `openai/gpt-5`.
  ⚠️ Key judge đọc từ biến **`GEMINI_API_KEY`** (không phải `OPENROUTER_API_KEY`) —
  tạo key mới thì phải sửa `.env`, nâng hạn mức key cũ thì không.
- **`LlmCache`** trên đĩa (`data/processed/llm_cache.json`, gitignore) — chạy lại script
  lúc phát triển không tốn lượt nào. Cache **tắt mặc định**; bật ở chỗ đo chi phí là làm
  hỏng bảng thời gian/token.
- **⛔ `ragas==0.4.3` CÀI ĐƯỢC nhưng KHÔNG CHẠY ĐƯỢC với dep mặc định** — nó import
  `langchain_community.chat_models.vertexai`, API đã bị gỡ ở 0.4.x. **Pin cứng `ragas`
  không chặn nổi** vì chỗ hỏng nằm ở tầng **dưới** cái pin: phải `langchain-community<0.4`.
  Xem `requirements-eval.txt`. Ragas kéo **35 gói** (không phải "7" như `requirements.txt`
  từng ghi), **có `langgraph`** — không vi phạm ràng buộc #1 (DEC-022: eval offline ≠
  orchestration) và điều kiện đó nay **khoá bằng máy**: test quét AST toàn `src/`.
  Ragas nằm ở `requirements-eval.txt` nên core install + HF Spaces **không** kéo nó.
- Corpus là dataset **gated** → mọi lần chạy ingestion/gate phải có `HF_TOKEN` trong env
  (`setx` **KHÔNG** áp cho terminal đang mở — phải mở terminal mới). ViMedAQA thì public.
- `streamlit` không có trong PATH — gọi `python -m streamlit`.

## 3 việc kế tiếp — Tuần 7 bắt đầu

1. ~~**`git push origin main`**~~ ✅ **ĐÓNG 2026-09-15** — 6 commit lên GitHub, `origin`
   hỏng đã sửa. Xem mục đầu file: nguyên nhân là **URL bị ghi đè**, không phải quên push.
2. ~~**🔴 Smoke test HF Spaces — rủi ro demo số 1**~~ ✅ **ĐÓNG 2026-09-15 (DEC-072).**
   Space **`datvu107-dateddy/vimed`** (docker · cpu-basic · private) **RUNNING**.
   Đo `"Triệu chứng tăng huyết áp?"`: **20,8 s** (lượt 1, ấm máy) · **15,8 s** · **15,9 s**.
   **KHÔNG đổi `top_k_dense`, KHÔNG dùng ZeroGPU.**
   ⚠️ **ĐỪNG so 15,9 s với 75–82 s** — mốc kia đo ở `rerank_max_length=1024` +
   `top_k_dense=20`, cấu hình **đang chạy** là `512` + `10`. Mốc đúng để so là **~17 s**
   (dự đoán local cho chính cấu hình này). Spaces **ngang** local, không nhanh hơn.
   ⚠️ Chi phí nền tảng mới: HF **bỏ SDK `streamlit`** (nay là template Docker → repo tự
   mang `Dockerfile`, tự cài `streamlit`) và **bắt PRO $9/tháng** cho Space Docker trên
   `cpu-basic`. Streamlit Community Cloud loại bằng số học: 1 GB RAM vs ~4,5 GB model.
   Dây chuyền deploy: `deploy/hf-space/` (`Dockerfile` · `README.md` · `requirements.txt`
   · `DEPLOY.md`). Việc con, đúng thứ tự:
   ~~(a) đụng cluster Qdrant~~ ✅ · ~~(b) rotate key Qdrant~~ ✅ **DEC-071** — tách key
   theo QUYỀN, không rotate · ~~(c) tạo Space, set secrets~~ ✅ — `QDRANT_API_KEY` là
   **secret**, `QDRANT_URL` là **variable** (liệt kê lại được để kiểm; secret write-only
   set hỏng không biết). **Không phải sửa code**: `config.py:165` `os.environ.setdefault`
   nên env của Space thắng `.env`.
3. ~~**C3 + B3 — UI đầu-cuối**~~ ✅ **ĐÓNG 2026-09-15 (DEC-073).** Streamlit nay **3 tab**,
   tab đầu là `RAGPipeline` chạy thật. Lỗi "5 nguồn cạnh câu từ chối" vá ở
   `app/display.py` — **thuần Python, 22 test khoá hai chiều**, không đụng pipeline.
   Vá kèm: **byline nay được cắt ở đường HIỂN THỊ** (trước đó tab truy hồi in `c.text`
   thô → màn hình hiện tên bác sĩ thật). Smoke 3 nhánh đã chạy thật. **399 → 421 test.**
4. **CÒN LẠI CỦA TUẦN 7 — latency p50/p95 tách stage + cost/1.000 query.**
   Phải chạy `export_runs.py --no-cache` mới có bảng token sạch.
   ⚠️ Số **~45s** (từ chối) / **~27s** (trả lời) trong các bản trước là của lô Tuần 6;
   smoke 2026-09-15 trên máy này ra **38,3s** (trả lời, có gánh nạp reranker lười) và
   **100,6s** (từ chối, 2 lượt rerank). **Cả hai đều KHÔNG phải benchmark** — máy không
   được kiểm soát tải, và STATUS đã ghi cùng cấu hình từng đo ra 1,72–9,35 s/cặp tuỳ tải.
   → **Task này tồn tại chính là để chốt số.** Đừng trích 38,3/100,6 lẫn 45/27 làm kết quả.
   ⚠️ **Đừng** dùng 17,2s dự tính của DEC-042.

**Buffer:** E2 evidence-highlighting **cắt đầu tiên** nếu tràn. Thứ tự cắt (DEC-015):
E2 → ablation reranker on/off → ablation chunk 256 vs 512.

## Cạm bẫy còn lại — đọc trước khi trích bất kỳ con số nào

- **Corpus trong Qdrant VẪN còn byline** — mọi đường mới đọc chunk ra phải tự gọi
  `strip_byline`, không có tầng nào cắt hộ (DEC-020 đã quyết không chạy lại ingestion).
- **Abstention đem đi báo cáo là 7%**, không phải "0/30" của DEC-051 — leakage sau
  rewrite **2/30** (DEC-056). Con số `0/30` chỉ đúng cho **cấu hình có guard** (DEC-061),
  và phải viết **`0–11%` (CI 95% Wilson)**, không viết "= 0".
- **`risk` phụ thuộc tỉ lệ test set** — ở coverage tối đa `risk = 0,588` = đúng 30/51 =
  tỉ lệ câu A/B. Thuộc tính của **test set**, không phải của hệ thống.
- **Đường cong risk–coverage KHÔNG dùng để chọn ngưỡng.** Ngưỡng chốt ở DEC-051 bằng
  LOOCV. Vai trò của đường cong: **bằng chứng điểm vận hành nằm trên biên hiệu quả**.
- **Tuần 6 chỉ tách abstention theo nhóm A/B/D/E, TUYỆT ĐỐI không tách theo khoa**
  (DEC-030 — nhãn `specialty` nhóm A/B mang cờ `specialty_verified: false`).
- **Chấm retrieval nhóm A/B phải đọc `PipelineResult.retrieved`, KHÔNG đọc `chunks`**
  (DEC-049) — đọc nhầm trường thì 30/59 câu ra 0 chunk mà bảng vẫn chạy ra số.
- **"18 ra ANSWER" đếm `action == "ANSWER"` theo nghĩa đen**, tách khỏi
  `ANSWER_WITH_CAUTION`. Tính cả caution thì là **19**. Hai nghĩa của chữ "ANSWER" —
  nói rõ mỗi lần trích.
- **Ngoài phạm vi vá, chưa sửa:** help của `--pairable-only` còn ghi `(48 câu -> 10)`;
  số đúng là **59 → 16**.
## Đã biết về test set — đừng dựng lại

- **TF-IDF cao trên ĐÁP ÁN không bảo đảm THỰC THỂ được phủ** (DEC-027). `"Aspirin STELLA"`
  đạt sim 0.666, người soi cũng gật, nhưng grep ra **0 bài** — cùng câu hỏi nằm ở cả nhóm E
  (ANSWER) lẫn A (ABSTAIN). Hai script giờ dùng **cùng phép kiểm, ngược chiều**: E đòi
  thực thể CÓ MẶT, A/B đòi VẮNG MẶT. Quy mô lỗ: **41,6%** QA "trong khoa" của ViMedAQA
  hỏi về thực thể corpus không có.
- **Bộ lọc khoa bằng keyword SAI CẢ HAI HƯỚNG** (DEC-030). Khớp Q+A → `Ung thư xương`
  lọt vào nhóm A. Khớp chỉ câu hỏi → `Hẹp van 2 lá` bị loại. Nó được chỉnh để gán khoa cho
  **BÀI VIẾT** (DEC-010), không phải phân loại **CÂU HỎI**. → Nhãn `specialty` của nhóm A/B
  mang cờ `specialty_verified: false`; **Tuần 6 chỉ tách abstention theo nhóm A/B/D/E,
  TUYỆT ĐỐI không tách theo khoa.**
- **Cột `keyword` của ViMedAQA TRỘN thực thể nguyên tử với cụm tiêu đề.** Kiểm 0-hit chỉ
  có nghĩa với loại đầu → lọc ≤5 token + không chứa từ chức năng.
- **Loại thực thể quyết định ĐỘ KHÓ của abstain** (DEC-028). Tên biệt dược = token hiếm →
  abstain dễ. Bệnh trong khoa nhưng vắng mặt → kéo về bài cùng chủ đề, score cao, dụ hệ
  thống trả lời. Chưa cân thì **36/36 ứng viên đều là `drug`** — chỉ đo đầu dễ của phổ.
- **Viết câu nhóm D có HAI bờ vực.** Quá gần policy = tautology; quá xa = gate không bắt
  nổi (D-03 lọt lưới ở lần chạy đầu). Chỉ mechanize mới đo được cả hai phía.
- **Pattern `xin_phep` chỉ cho 15 KÝ TỰ giữa `có nên` và `không`** (đo khi làm T4.1,
  DEC-044). Nên *"em có nên **giảm liều thuốc huyết áp cho bố** không"* **KHÔNG** khớp
  D-4 — chỉ hụt vài ký tự. Muốn siết D-4 thì nới `.{0,15}` là chỗ sửa, nhưng nới xong
  **phải chạy lại `check_policy_coverage.py`**: mục [4] `khong_trigger` có sẵn 8 ca sát
  ranh giới chờ bắt lỗi rule quá rộng.
- **Trong 8 câu nhóm D KHÔNG câu nào khớp đồng thời D-3 với rule khác**, nên ưu tiên
  tuyệt đối của D-3 **không kiểm được bằng dữ liệu thật** — `test_policy_gate.py` phải
  dùng câu mồi tổng hợp, đã khoá bằng assert `all_rules == ("D-3","D-4")`.
- **⚠️ NHÓM E HIỆN TẠI THIÊN VỀ CÂU DỄ — đo được** (DEC-041b). Cả **12/12** câu nằm ở
  **nửa TRÊN** phân bố `max_sim` của pool ứng viên (min 0,650 · trung vị 0,684, so với
  trung vị pool 0,627). Vì đáp án chồng lấn từ vựng gần như nguyên văn với corpus, chỉ
  số retrieval đo trên nhóm này **lạc quan hơn thực tế** — cùng lớp thiên lệch với
  DEC-029 nhưng khác trục, và nguy hiểm hơn vì E là ground truth của chính bảng T3.4.
  Khi mở rộng phải rải đều theo dải sim.
- **Trần "≤2 câu/bài" của DEC-025c TỪNG KHÔNG được thực thi đúng** (DEC-041a): bộ đếm
  reset theo từng khoa nên bài thuộc cả 2 khoa lọt 3–4 câu. Đã sửa. Nếu thấy pool đổi
  từ 111 → 106 thì đó là lý do, không phải corpus đổi.
- **ID ứng viên DỊCH CHUYỂN mỗi lần sinh lại** — đã gây chọn nhầm một lần. Trao đổi danh
  sách phải ánh xạ theo **tên thực thể**, không theo số.

## Đã biết về hạ tầng — đừng thử lại

- **⛔ SCORE BÁM ĐỘ CÙNG CHỦ ĐỀ, KHÔNG BÁM ĐỘ ĐÚNG — phát hiện lớn nhất của T3.4
  (DEC-039).** Đo trên 12 câu nhóm E, `vimed_rag_512`, hybrid:

  | câu | max-logit | hạng bài vàng sau rerank | |
  |---|---|---|---|
  | E-07 | **+5,67** | — | bài vàng **không vào pool**; hệ thống sẽ trả lời rất tự tin bằng tài liệu khác |
  | E-03 | **+5,21** | — | như trên |
  | E-11 | **+4,31** | — | như trên |
  | E-06 | +2,85 | **1** | bài vàng đứng đầu, nhưng điểm chỉ bằng **một nửa** E-07 |
  | E-12 | **−0,89** | **1** | bài vàng đứng ĐẦU mà vẫn bị từ chối |
  | E-09 / E-05 | −0,35 / −0,35 | 2 / 3 | vàng trong top-3, vẫn bị từ chối |

  Nói cách khác: abstention hiệu chỉnh theo **"corpus có nội dung cùng chủ đề hay
  không"**, KHÔNG theo **"đoạn này có chứa đáp án hay không"**. Đây đúng là giới hạn
  `gates.md` đã tự thú từ Gate 0 (tiêu chí #3 chỉ là proxy trùng lặp chủ đề) nay tái
  xuất ở tầng grader. **Phải vào Limitations.**
  ⚠️ **Đừng suy ngược:** "chỉ 5/9 câu trả lời có bài vàng ở top-5" KHÔNG có nghĩa 4 câu
  kia sai — `reference_context_ids` chỉ có **1 bài/câu**, corpus Vinmec có thể có bài
  khác trả lời được. 5/9 là **cận dưới của độ đúng**, không phải phép đo độ sai.
- **✅ NGƯỠNG Ở CẤU HÌNH TRIỂN KHAI — có DẢI AN TOÀN, rộng gấp 1,7 lần cấu hình cũ.**
  Đo lại ở đúng `top_k_dense=10` + `rerank_max_length=512` (DEC-042):

  | | A/B cao nhất | E thứ 9 | dải an toàn | điểm giữa |
  |---|---|---|---|---|
  | `max_length=1024`, top20 | +2,27 | +2,85 | rộng **0,58** logit | — |
  | **`512`, top10 (đang dùng)** | **+2,15** | **+3,12** | rộng **0,97** logit | **+2,63 = sigmoid 0,933** |

  Trong cả dải: **9/12 câu E được trả lời, 0/30 câu A/B lọt lưới**. Tức cắt cửa sổ
  subword làm ngưỡng **DỄ đặt hơn**, không chỉ rẻ hơn — đây là kết quả ngoài dự kiến,
  ban đầu chỉ định cắt cho nhanh. Bảng: `docs/retrieval-eval-deploy.md`.
  ✅ **ĐÃ CHỐT VÀO `config.yaml` từ 2026-09-08** — `correct_threshold: 0.933` ·
  `incorrect_threshold: 0.919` (`config/config.yaml:101-102`), **đã nối pipeline**
  (DEC-056 đo end-to-end 59 câu trên chính hai số này). Chuỗi đúng, đừng trích gộp:
  **DEC-051** hiệu chỉnh bằng LOOCV (supersedes điều kiện "phải có tập giữ lại" của
  DEC-039) → **DEC-052** đóng hai số vào `config.yaml` → **DEC-061** thêm guard lượt 2.
  ⚠️ Số `sigmoid 0,933` ở bảng trên là **điểm giữa dải đo của DEC-042**; số cùng giá trị
  đang chạy trong config có **nguồn gốc khác** — ngưỡng CAO NHẤT mà bất kỳ fold LOOCV
  nào sinh ra (DEC-051). Trùng giá trị, **đừng trích bảng này làm căn cứ cho config**;
  căn cứ nằm ở `docs/threshold-calibration.md`.
- **⛔ NGƯỠNG `0.6/0.3` KHÔNG AN TOÀN — 10/30 câu nhóm A/B VẪN ĐƯỢC TRẢ LỜI**
  (DEC-039). Quét ngưỡng trên max-logit, `vimed_rag_512` hybrid:

  | ngưỡng | sigmoid | E trả lời | …có bài vàng ở top-5 | **A/B lọt lưới** |
  |---|---|---|---|---|
  | +2,50 | 0,924 | 9/12 | 5 | **0/30** |
  | **+2,27** | **0,906** | 9/12 | 5 | **0/30** ← mép an toàn |
  | +2,00 | 0,881 | 9/12 | 5 | 4/30 |
  | **+0,41** | **0,600 ← config thời DEC-039, ĐÃ BỎ** | 9/12 | 5 | **10/30 = 33%** |

  ⚠️ **Dòng cuối là LỊCH SỬ, không phải cấu hình đang chạy.** Config hiện tại là
  **0,933 / 0,919** (DEC-051) — không có dòng nào trong bảng này mô tả nó.
  Có **khoảng trống sạch** từ logit +2,27 trở lên. Lo ngại "chọn ngưỡng trên chính 42
  câu dùng để đánh giá → lạc quan" của DEC-039 **đã được xử lý bằng LOOCV**, không phải
  bằng tách tập: xem DEC-051 · `docs/threshold-calibration.md`.
- **✅ ĐO LẠI TRÊN 21 CÂU (DEC-043) — độ phân giải có tác dụng, nhưng không cứu claim.**
  `recall@10` trên 12 câu bằng nhau **tuyệt đối 0,750** ở cả 6 cấu hình; trên 21 câu đã
  tách ra: **dense/512 0,714** đứng đầu · hybrid/512 0,667 · sparse/256 0,571.
  → Con số 0,750 phẳng lì là **ảo ảnh của 12 câu**. Nhưng cấu hình tốt nhất là **dense**,
  hybrid xếp sau — DEC-038 vẫn đứng, hướng còn **ngược** claim. Bước nhảy giảm 8,3 → 4,8
  điểm/câu. Recall tổng thể tụt 0,750 → 0,667–0,714 vì 9 câu mới khó hơn (đúng ý muốn).
- **✅ TÁCH NHÓM E/AB SỐNG SÓT QUA TEST SET KHÓ HƠN.** Dải an toàn ở cấu hình triển khai:
  **(+2,15, +2,71]**, điểm giữa **+2,43 = sigmoid 0,919** → **17/21 câu E trả lời (81%)**
  và **0/30 câu A/B lọt lưới**. Dải hẹp lại từ 0,97 → 0,55 logit, nhưng đó là **ước
  lượng cũ quá rộng do lấy mẫu thưa** (9 câu mới lấp vào khoảng 2,71–3,14 sát biên),
  không phải chất lượng giảm — coverage còn **tăng** 75% → 81%.
- **⛔ "HYBRID > DENSE" KHÔNG CHỨNG MINH ĐƯỢC** (DEC-038). `recall@20` **bằng nhau
  tuyệt đối — 0,750 ở cả 6 cấu hình** (3 mode × 2 collection). Khác biệt không tồn tại
  **ngay từ tầng ứng viên**, không phải chỉ bị rerank xoá ở top-5 như dự đoán ban đầu.
  `mrr@5` có chênh nhưng **ngược chiều claim** (dense/512 0,542 > hybrid/512 0,431) và
  rerank bù lại phần lớn (hybrid → 0,528). Căn cứ định tính cho hybrid vẫn dùng được:
  top-5 dense ∩ sparse = **1/5 bài**, RRF lấy 3 từ dense + 2 chỉ có ở sparse.
  **Đã kiểm trước khi tin bảng:** 12/12 `reference_context_ids` khớp `doc_id` corpus,
  12/12 bài vàng đều có chunk trong `vimed_rag_512` → 3 câu trượt là thất bại truy hồi
  thật, không phải lỗi ID hay lỗi index.
- **⛔ MODE `hybrid` BẤT ĐỊNH GIỮA CÁC LƯỢT NẾU KHÔNG TỰ SẮP LẠI — DEC-040, ĐÃ SỬA.**
  RRF k=2 làm điểm **hoà rất thường xuyên**; Qdrant trả các bài hoà điểm theo thứ tự
  khác nhau mỗi lượt. Đo: E-08 có 2 bài cùng **0,8333**, bài vàng lúc hạng 1 lúc hạng 2
  → `mrr@5` nhảy **0,431 ↔ 0,472** (±0,042 trên 12 câu, **lớn hơn phần lớn khác biệt
  giữa các cấu hình**). `dense` chạy 4 lượt ra 1 thứ tự duy nhất (cosine liên tục, không
  hoà) — đó là đối chứng xác nhận nguyên nhân. `search()` giờ sắp lại với khoá phụ
  `(doc_id, chunk_idx)`. **Đã xác nhận 2 lượt lưới đầy đủ ra CSV giống hệt nhau.**
  ⚠️ Mọi số `mrr`/`ndcg` ghi TRƯỚC 2026-09-06 đều có thể lệch ±0,04 — đừng so với số mới.
- **⛔ CHI PHÍ RERANK THEO `max_length` — đo có kiểm soát, 3 lượt, máy rảnh:**

  | `max_length` | s/cặp (trung vị) | 3 lượt | 20 cặp = 1 truy vấn |
  |---|---|---|---|
  | 1024 (hiện tại) | 3,75 | 3,66 · 3,75 · 3,95 | **75,0s** |
  | **512** | **1,72** | 1,63 · 1,72 · 1,79 | **34,5s** |
  | 256 | 0,77 | 0,77 · 0,76 · 0,81 | **15,4s** |

  **`max_length=512` giảm một nửa chi phí mà KHÔNG mất chất lượng đo được**: `mrr@5`
  sau rerank là **0,542** (so với 0,528 ở 1024), `recall@5`/`recall@20` không đổi.
  Xem `docs/retrieval-eval-len512.md`. Ghép thêm `top_k_dense` 20→10 thì còn ~17s.
  ⚠️ **ĐỪNG tin số giờ lấy từ chính `eval_retrieval.py` khi máy đang bận** — cùng cấu
  hình tôi đã đo ra 3,40 · 1,72 · 2,04 · **9,35** s/cặp tuỳ tải máy. Chỉ dùng benchmark
  cô lập như bảng trên.
- **Rerank SAN PHẲNG khác biệt giữa các cấu hình, và đôi khi làm XẤU ĐI.** Trước rerank
  `mrr@5` trải 0,396–0,542; sau rerank co lại còn **0,486–0,542** (biên độ 0,056) trên
  cả 6 cấu hình. Rerank làm **tụt** cấu hình tốt nhất trước đó (dense/512 0,542 → 0,521)
  và làm `recall@5` của sparse/512 tụt 0,750 → 0,667. Đây là bằng chứng trực tiếp cho
  DEC-038: nhánh truy hồi gần như không còn ảnh hưởng tới kết quả cuối.
- **Rerank ~3,40s/cặp trên CPU** (1000 cặp, `max_length=1024`) → **68s/truy vấn** với
  `top_k_dense=20`. Cache logit ở `data/processed/rerank_cache.json` (gitignore) khoá
  theo `(size, max_length, qid, doc_id, chunk_idx)` — **có `max_length` trong khoá** vì
  đổi cửa sổ subword là đổi điểm; thiếu nó thì lần đo `--max-length 512` lặng lẽ đọc
  lại điểm của lần 1024.
- **⛔ BA THANG ĐIỂM, KHÔNG THANG NÀO DÙNG ĐƯỢC VỚI GRADER — đo 2026-09-06 trên
  `vimed_rag_512`, truy vấn "Triệu chứng tăng huyết áp?", top-5.** Ngưỡng grader là
  `correct=0.6` / `incorrect=0.3`:

  | Mode | Score đo được | Nối thẳng vào grader thì |
  |---|---|---|
  | `dense` | 0,707 – 0,741 | **toàn bộ > 0,6** → CORRECT tuyệt đối, ABSTAIN không bao giờ chạy |
  | `sparse` | 0,180 – 0,194 | **toàn bộ < 0,3** → INCORRECT tuyệt đối |
  | `hybrid` | 0,250 – 0,583 | **rơi ngay giữa hai ngưỡng** |

  **Dòng `hybrid` là dòng nguy hiểm nhất, không phải hai dòng kia.** Hai dòng trên hỏng
  lộ liễu. `hybrid` sinh ra hỗn hợp CORRECT/AMBIGUOUS/INCORRECT trông hợp lý, Tuần 6 vẫn
  vẽ được risk–coverage đẹp — chỉ là đang đo **thứ hạng RRF**, không phải độ liên quan.
  Đây chính là kịch bản DEC-033 mô tả. Lý do tồn tại của `normalize=True`.
- **RRF của Qdrant dùng `k=2`, KHÔNG phải `k=60`.** Công thức `1/(2 + rank)`, rank tính
  **từ 0**. Kiểm bằng tay khớp cả 5 kết quả (vd bài đứng dense-rank-2 + sparse-rank-1 ra
  đúng `1/4 + 1/3 = 0,5833`). Vì thế điểm RRF nằm trong khoảng ~(0, 1] chứ không quanh
  0,016 như trực giác quen với k=60. **Từng ghi nhầm k=60 vào docstring, đã sửa.**
- **Tuần 3 chạy được TRÊN MÁY LOCAL, không cần Kaggle.** Đo 2026-09-06 (CPU, fp16 tắt):
  nạp bge-m3 + warm-up **19–21s** (một lần), bắt tay TLS tới Qdrant Cloud **~2,1s** (một
  lần), rồi **hybrid 0,88s · dense 0,54s · sparse 0,58s mỗi truy vấn** — phần **truy hồi**
  rẻ. Khác Tuần 2 vì chỉ encode **1 truy vấn** thay vì 4.972 chunk.
  ⚠️ **Câu "vậy Tuần 7 gánh được" ghi ở bản trước là SAI — đã bị chính số rerank bác bỏ,
  xem mục ⛔ ngay dưới.** Truy hồi rẻ, rerank thì không.
- **⛔ RERANK TỐN 75–82 GIÂY MỖI TRUY VẤN TRÊN CPU — số đe doạ Tuần 7.** Đo 2026-09-06,
  i5-1135G7, fp16 tắt, `max_length=1024`, 20 cặp: `hybrid` **75,9s** · `dense` **82,2s**
  · `sparse` **80,7s**. Trước khi có rerank là **0,88s** → rerank chiếm **~99%**. Quy ra
  **~3,8s mỗi cặp** (cross-encoder XLM-R-large, ~568M tham số, seq ~1024). Nạp model
  thêm **8,7s** một lần. **HF Spaces CPU free bắt người dùng chờ 75s/câu là demo không
  dùng được.** 4 hướng cắt ghi ở "3 việc kế tiếp" mục 3 — **chưa chọn, chờ T3.4 đo**.
- **⛔ NGƯỠNG GRADER 0,6/0,3 VÔ DỤNG VỚI RERANKER NÀY.** Sau sigmoid, 15/15 kết quả
  top-5 của cả 3 mode đều **≥ 0,6901**, cao nhất 0,9832 → grader trả CORRECT cho tất cả,
  AMBIGUOUS và ABSTAIN vẫn không bao giờ chạy. `bge-reranker-v2-m3` **bão hoà rất mạnh
  về 1** với mọi đoạn cùng chủ đề; ngưỡng thật gần như chắc chắn nằm ở vùng **0,9+**.
  ⚠️ Nhưng truy vấn smoke có **cả 20 ứng viên đều đúng chủ đề** nên bão hoà là kỳ vọng
  được — **KHÔNG được chốt ngưỡng từ 1 truy vấn**. Nhóm A/B mới là chỗ score phải tụt.
  → T3.4 phải đo **phân bố score theo nhóm A/B/D/E**, sớm hơn Tuần 6.
- **⛔ RERANK XOÁ KHÁC BIỆT HYBRID–DENSE Ở TOP-5.** Sau rerank, `hybrid` và `dense` ra
  **top-5 giống hệt nhau** — cùng 5 bài, cùng thứ tự, cùng score. Chỉ `sparse` khác
  (đỉnh 0,9372 vs 0,9832). Lý do: reranker đủ mạnh thì nhánh truy hồi chỉ còn nhiệm vụ
  **đưa bài đúng vào pool 20**, thứ tự trong pool bị chấm lại sạch. **Hệ quả cho báo
  cáo: claim "Hybrid > Dense" có thể biến mất hoàn toàn nếu chỉ đo top-5 sau rerank.**
  → T3.4 **BẮT BUỘC** đo `recall@20` ở tầng ứng viên, tách khỏi metric top-5. Đo mỗi
  top-5 là gần như chắc chắn ra "hybrid không hơn gì dense" mà không giải thích được.
  Bằng chứng rerank CÓ làm việc: top-1 trước rerank là *"Chế độ ăn và tập luyện cho
  người tăng huyết áp"*, sau rerank bài đó **rơi khỏi top-5**.
- **`FlagEmbedding` KHÔNG rerank được với `transformers 5.x` — đừng thử lại** (DEC-037).
  Nó gọi `tokenizer.prepare_for_model()`, API đã bị gỡ; kiểm cả `use_fast=True` lẫn
  `False` trên `XLMRobertaTokenizer`, `hasattr` đều `False`. Không phải lỗi cấu hình.
  Hạ transformers về 4.x = phá cấu hình embedder đã verify sạch ở Tuần 2 → **không làm**.
  `sentence-transformers.CrossEncoder` thì **chạy được** và mặc định **đã sigmoid** cho
  model 1 nhãn (đo `[0.9841, 0.0003]`, trùng sigmoid thủ công của logit `[+4.125,
  −8.179]`) — tức lý do "CrossEncoder không có công tắc normalize" ở DEC-033 là **SAI**,
  đừng dựa vào nó nữa. Vẫn không dùng, vì 2 lý do khác ghi trong DEC-037.
- **⛔ BẪY ĐO GIỜ (mới, 2026-09-15): DỤNG CỤ ĐO tự nó làm hỏng số — phồng 17×.** Đo
  page-ready của Space bằng cách **bật một Chromium MỚI cho mỗi mẫu**: 8,1 · 5,9 ·
  **103,7** s. Dùng **một** browser cho cả 5 mẫu: **5,7–8,3 s**, ổn định. Đối chứng
  quyết định: `curl /_stcore/health` chạy **xen kẽ** vẫn **0,84–0,99 s** suốt cả hai lần
  → nghẽn nằm ở **laptop đang đo**, không ở Space. Phiên này đã **kết luận nhầm một lần**
  ("cold start 73–85 s") rồi tự bác bỏ bằng phép đo có đối chứng.
  → **Quy tắc cho Task latency/cost:** mỗi phép đo phải có **một đối chứng rẻ chạy song
  song** (thứ mà nếu nó cũng chậm thì lỗi ở máy, không ở hệ). Cùng lớp với cảnh báo
  "đừng tin số giờ lấy từ `eval_retrieval.py` khi máy đang bận" ngay dưới.
- **BẪY ĐO GIỜ: mode chạy ĐẦU TIÊN gánh luôn bắt tay TLS.** Lần đo đầu ra `hybrid` 2,36s
  vs `dense` 0,63s → tưởng hybrid đắt gấp 4. Hâm nóng kết nối trước vòng lặp thì hybrid
  còn 0,88s. `smoke_retrieval.py` đã có bước hâm nóng; **T3.4 đo giờ chính thức phải giữ
  đúng thứ tự đó**, nếu không bảng chi phí trong báo cáo sai.
- **Máy local KHÔNG embed được, đã đo, đừng thử lại.** i5-1135G7 (4 nhân, GPU Intel
  Iris Xe không CUDA), torch bản `+cpu`: **0,22 chunk/s** trên chunk thật 512.
  → 6,2 giờ cho size 512, ~12–13 giờ cho cả hai. Ép thêm thread không cứu được.
- **Lần đo đó xác nhận `BgeM3Embedder` chạy đúng với model + corpus THẬT:** dense
  dim 1024, sparse trung bình **140 token khác 0**/chunk, sạch với `transformers 5.5.4`.
- **Kaggle: "không chọn được Accelerator" + "git clone fail" = MỘT nguyên nhân duy nhất
  — tài khoản chưa xác minh SĐT.** Kaggle khoá **GPU và Internet cùng lúc**. Nếu gặp lại:
  xác minh SĐT trước, đừng debug riêng lẻ.
- **`notebooks/colab_build_index.ipynb` CHƯA TỪNG CHẠY.** Dự phòng khi Kaggle hết quota
  GPU (30h/tuần), nhưng **đừng tin nó chạy được**.
- **Model bge-m3 (~2,3 GB) đã cache** ở `~/.cache/huggingface` trên máy local.
- **Heredoc bash làm hỏng encoding tiếng Việt** khi có escape lồng nhau (đã hỏng 1 file
  script). Nội dung tiếng Việt phức tạp → ghi file trực tiếp, đừng qua heredoc.

## Đã biết về corpus — đừng đo lại

- **KHÔNG có bài "triệu chứng tăng huyết áp" tổng quát trong corpus.** Grep 1.410 bài:
  17 tiêu đề chứa "triệu chứng", **đúng 1** bài vừa có "triệu chứng" vừa có "huyết áp" —
  và đó là bài **thai kỳ**. Nên khi smoke query "Triệu chứng tăng huyết áp?" không ra
  bài nào đúng ý, **đó là lỗ hổng corpus, KHÔNG phải retriever hỏng** — đúng hiện tượng
  DEC-027 đã đo ở quy mô lớn (41,6% QA "trong khoa" hỏi về thực thể corpus không có).
  Đừng lấy truy vấn này làm thước đo chất lượng.
- **Sparse thiên vị `đoạn 0` một cách hệ thống: 4/5 kết quả top-5 là chunk đầu bài.**
  Nguyên nhân: `loader` ghép `title + content` nên tiêu đề nằm trong chunk 0 → khớp từ
  vựng mạnh. Cộng dồn với DEC-029 (câu nhóm E dùng đúng từ vựng corpus) thành **hai lớp
  làm số sparse lạc quan hơn thực tế** — phải vào Limitations, đừng để thành claim.
- **Dense và sparse gần như KHÔNG chồng nhau: top-5 giao nhau đúng 1/5 bài.** RRF lấy 3
  bài từ dense + 2 bài chỉ có ở sparse. Bằng chứng sớm cho luận điểm "hybrid thắng",
  nhưng **chưa phải phép đo** — chờ T3.4 trên 12 câu nhóm E.
- **Byline ĐÃ QUAN SÁT ĐƯỢC trong top-k thật, không còn là rủi ro lý thuyết:** 3/5 chunk
  hybrid mở đầu bằng "Bài viết được tư vấn chuyên môn bởi Bác sĩ…". Tuần 4 làm citation
  bắt buộc phải cắt, nếu không hệ thống sẽ trích dẫn thành "BS X khẳng định…".
- **Bài sản khoa mang nhãn `tim_mach` xuất hiện 1–2/5 trong top-5 mỗi mode**
  (*Thực đơn cho bà bầu bị rối loạn tăng huyết áp thai kỳ*, *Triệu chứng và chẩn đoán
  tăng huyết áp trong thời gian mang thai*) — đúng lớp nhiễu đã gọi tên qua ca *Tiền sản
  giật*. **CHƯA đủ căn cứ nâng ngưỡng 25→30**: một truy vấn không phải phép đo, mà nâng
  = index lại cả 2 collection. Để T3.4 quyết trên 12 câu.
- **1.425 và 1.410 đều đúng, đừng tưởng lệch.** 1.425 = 727 + 698 (cộng dồn theo khoa,
  15 bài trùng đếm 2 lần); 1.410 = số bài phân biệt. DEC-016 ghi kiểu cộng dồn.
- **Kích thước:** 1.410 bài ≈ **2,04 triệu từ**, median 1.388 từ/bài (min 57, max 4.229).
- **`both%` (trùng khoa) là chỉ số đánh lừa.** Chỉ số dùng được là **`title-hit`**.
- **Hai khoa không đối xứng.** `tiểu đường` là tên bệnh nên nằm ở tiêu đề (80% ở ngưỡng 25);
  từ vựng tim mạch rải khắp bài dinh dưỡng + tờ hướng dẫn thuốc (42%). Ô nhiễm dồn về `tim_mach`.
- **Nhiễu còn lại ở ngưỡng 25:** bài gây mê/phẫu thuật lọt vào `tim_mach` vì huyết áp được
  nhắc nhiều. Session 9 tìm thêm một ca có tên: **"Tiền sản giật: Những điều cần biết"**
  mang nhãn `tim_mach` — sản khoa, lọt vì chữ "huyết áp". Nếu Tuần 3 thấy retrieval nhiễu
  thì nâng ngưỡng lên 30 (546/658, title-hit 72%).
- **Số chunk đã đo, đừng chunk lại để đếm** (DEC-020): **512/50 → 4.972 chunk** ·
  **256/50 → 10.246 chunk**. Tổng 15.218 vector. Dung lượng thật đã đo: **97,7 MB = 9,5%**
  free tier 1GB — **không phải tính lại ngân sách**.
- **Đuôi vụn là lý do thật để ưu tiên 256 trong ablation:** 512 có 151 chunk (3,0%) ngắn
  hơn 20% size; 256 chỉ có 4 (0,0%).
- **Byline "Bài viết được tư vấn chuyên môn bởi…Vinmec" = 12,4% bài (175/1410)**, đo lại
  2026-08-23. ⚠️ Con số **17,6%** ghi ở các phiên trước là của corpus TRƯỚC DEC-016 —
  đừng dùng lại. Kết luận của DEC-020 (không đáng chạy lại ingestion) càng đúng.
  **Nhưng byline có tên bác sĩ + tên bệnh viện:** Tuần 4–5 làm citation phải để ý đừng để
  hệ thống trích dẫn thành "BS X khẳng định…". Regex cắt byline chuẩn nằm ở
  `scripts/build_testset.py` (bắt 175/175; bản kết thúc bằng dấu chấm chỉ bắt 138/175 vì
  `cleaner.py` gộp khoảng trắng làm 37 byline chạy thẳng vào thân bài).

## Backlog tiếp quản từ Member B

- ~~Rubric abstention + safety subset 50 câu~~ — **✅ XONG 2026-08-23.**
- **Test set v1 mở rộng** — nhóm E (12 câu, có `reference_context_ids`) đã dùng được ngay
  cho Tuần 3. Mở rộng lên ~35–40 câu khi cần độ phân giải cao hơn.
- **Generation Tuần 4**: Gemini Flash, prompt bám context + citation [1][2] + disclaimer,
  baseline LLM-only. ~~implement `check_policy()` + 3 biến thể `abstain.txt`~~ —
  **✅ XONG ở T4.1 (DEC-044).**
- ~~**Eval Tuần 6**: RAGAS 4 metric, abstention P/R theo nhóm A/B/D/E, % giảm
  hallucination~~ — **✅ ĐÓNG 2026-09-14 (DEC-065, DEC-070), nhưng KHÁC backlog gốc ở
  2 chỗ, cả hai đều là quyết định có lý do:**
  (a) **chỉ 1 metric đến từ ragas** (Faithfulness). 3 metric truy hồi dùng lại
  `retrieval_metrics.py` — kéo thư viện về để tính lại thứ repo đã tính là cái trôi repo
  đã gỡ **bốn lần** (DEC-065 · DEC-022 cho phép vì eval offline ≠ orchestration, và điều
  kiện đó nay **khoá bằng máy**: test quét AST toàn `src/`);
  (b) **"% giảm hallucination" KHÔNG được đo bằng faithfulness** — nó đo *bám ngữ cảnh*,
  không đo *đúng*. Dụng cụ đúng là `leaked` · `invalid_citations` · nhãn tay **6/30**.
- **Streamlit UI thật** + cost/1.000 query ở Tuần 7 — **chưa làm**, xem "3 việc kế tiếp".
- **Báo cáo + slides** Tuần 8. Limitations đã có 6 mục trong `../contracts/constraints.md`.

## Việc treo ngoài code

- ~~**⛔ 3 commit chưa push**~~ ✅ **ĐÓNG 2026-09-15** (thật ra là **6**, không phải 3 —
  Session 17 đẻ thêm 3 mà mục này không được cập nhật). Nguyên nhân gốc: **`origin` bị
  ghi đè bằng URL HF Space dị dạng**, xem mục đầu file.
- **⚠️ `brain/` từng mô tả trạng thái đã chết — lần thứ hai (ISSUE-070 tái diễn).**
  Audit 2026-09-14 bắt được STATUS/handoff/DECISIONS còn ghi *blocker 403 · còn 7 lượt ·
  p = 0,0391 · ISSUE-069 mở* trong khi cả bốn đã sai. Đã viết lại. **Bài học:** STATUS
  tự khai là *"state hiện tại, ghi đè mỗi session"* — nên mọi mệnh đề trong nó phải
  đúng **lúc đọc**, không phải lúc viết. Handoff và DECISIONS thì ngược lại: **lịch sử
  append-only, giữ nguyên**, kể cả khi số đã cũ.
- **⚠️ `data/processed/*` bị gitignore (đúng thiết kế).** Clone sạch **không có**:
  `runs.jsonl` (sinh lại `python scripts/export_runs.py`, ~45 phút, tốn lượt API) ·
  `static_rag.jsonl` (`python scripts/gen_static_rag.py`, ~2 phút, 51 lượt LLM, **không**
  cần Qdrant — nhưng đọc ngữ cảnh từ `runs.jsonl` nên phải có file kia trước) ·
  `ragas_scores.json` (cache điểm judge).
  Thứ **commit được** là `docs/*.md`. `calibration_scores.json` (8,5 KB) đã whitelist
  (DEC-067) nên `docs/risk-coverage.png` dựng lại được từ clone sạch.
- ~~**⚠️ LỖI HIỂN THỊ CHƯA VÁ — câu ANSWER hiện 5 nguồn cạnh câu "không có thông tin"**~~
  ✅ **ĐÓNG 2026-09-15 (DEC-073).** Vá ở `app/display.py::nen_hien_nguon()` — tầng VẼ,
  không đụng pipeline, nên `17/21` · `0/30` · `p=0,0042` **không đổi một chữ số**.
  ⚠️ **Hai điều đừng trích sai từ đây:**
  (a) `A-01` là ca **tiền-guard** (`runs.jsonl` sinh 08-09, trước DEC-061; nó lọt ở
  **lượt 2**). Với `allow_turn2_promotion: false` đang chạy, B3 chỉ còn sinh ra được ở
  **lượt 1** → ca còn sống là **`E-21`**. Đừng viết "hệ thống có 2 ca B3".
  (b) **UI đọc `chunks`, KHÔNG BAO GIỜ đọc `retrieved`** — 32/40 câu ABSTAIN có
  `retrieved` không rỗng (DEC-049), hiện nó ra là dựng lại đúng lỗi vừa vá.
  Khoá bằng máy: `test_nen_hien_nguon_KHONG_BAO_GIO_doc_retrieved` cho `retrieved` **ném
  khi bị chạm**.
- ~~**⚠️ Byline lọt ra màn hình**~~ ✅ **ĐÓNG 2026-09-15 (DEC-073).** Trước đó
  `strip_byline` **chỉ** được áp ở `generation/context.py` (đường dựng prompt) — tức LLM
  không thấy byline **nhưng người xem thì có**, vì tab truy hồi in `c.text` thô. Nay mọi
  chỗ UI in nội dung chunk đi qua `app/display.py::doc_nguon()`. **Corpus trong Qdrant
  vẫn còn byline** (DEC-020 không đổi) — nên **đường đọc MỚI nào cũng phải tự cắt**.
- **⚠️ `data/testset_e_patient.jsonl` PHẢI giữ đúng khuôn JSONL — mỗi bản ghi MỘT dòng.**
  2026-09-08 sửa tay lúc soi làm bản ghi trải nhiều dòng; JSON vẫn hợp lệ nhưng
  `eval_register_shift.py:89` đọc `json.loads(l)` **từng dòng** nên crash. Muốn đọc cho
  dễ thì mở bản `.md` ứng viên, đừng bẻ dòng file `.jsonl`.
- **⛔ Đừng chép bản sao thứ hai của bất kỳ hàm nào trong `src/eval/stats.py`.** Cảnh báo
  ghi thẳng trong docstring module. Đây là nước cờ chống trôi **lần thứ tư**, sau DEC-044
  (regex policy) · DEC-045 (regex byline) · DEC-046 (client LLM). Lần gom (Session 13) đã
  đối chứng **1.890 cặp `(k,n)`** + **3.005 vector** cho `sign_test` → **0 chỗ lệch**.
- ~~**Rotate API key Qdrant**~~ — ✅ **ĐÓNG 2026-09-14 (DEC-071).** Không rotate; tách key
  theo **QUYỀN**: Space dùng key **chỉ-đọc** giới hạn collection, `.env` local + Kaggle
  Secrets **giữ nguyên** key toàn quyền. Kiểm lại thấy key **chưa bao giờ** vào git
  (`eyJhbG`: 0 hit toàn lịch sử) nên rotate sẽ không đóng rủi ro nào.
  ⚠️ **ĐỪNG đè key chỉ-đọc vào `.env`** — `build_index.py` là script **duy nhất** cần
  quyền ghi, và nó chết đúng lúc bạn cần nhất (dựng lại index sau khi cluster bị xoá).
  ⚠️ Nghiệm thu bằng `python scripts/smoke_qdrant_readonly.py --from-env` — **ĐẠT = ĐỌC
  pass VÀ GHI fail**. Phép này **không để lại artifact**, nên trạng thái "đã nghiệm thu"
  là lời khai; nghi thì chạy lại, mất 10 giây.
- ~~**⛔ SPACE CHƯA CÓ `GEMINI_API_KEY`**~~ ✅ **ĐÓNG 2026-09-15 (DEC-074).** Đã set qua
  `--secrets-file` (khoá **không** đi qua dòng lệnh nên không rơi vào lịch sử shell).
  Space nay có **3** biến: `QDRANT_URL` (variable) · `QDRANT_API_KEY` · `GEMINI_API_KEY`.
- **⛔ ĐẨY LẠI `app/` PHẢI ĐẨY CẢ THƯ MỤC.** `streamlit_app.py` `from app.display import …`
  — đẩy thiếu `display.py` là **build xanh rồi chết `ModuleNotFoundError`** khi mở.
  ⚠️ `--exclude "**/__pycache__/**"` **bị Git Bash bung glob** thành đường dẫn Windows và
  `hf upload` báo "unexpected extra arguments". Cách đi được: `rm -rf app/__pycache__`
  rồi đẩy không cần `--exclude`.
- **Space đang PUBLIC — Đạt chọn phương án (b) 2026-09-15** (public + video dự phòng +
  chấp nhận chi phí), **credit đã đặt trần** nên bán kính thiệt hại có chặn. Hệ quả phải
  nhớ: **ai có link cũng tiêu được credit**. Kiểm trước buổi bảo vệ:
  `GET https://openrouter.ai/api/v1/key`. **Video dự phòng là bắt buộc** trong phương án
  này — hết credit giữa buổi bảo vệ thì Space còn sống nhưng tab đầu-cuối trả 402/403.
- **⚠️ PRO hết 1/10, KHÔNG gia hạn (Đạt tự kiểm soát). Bảo vệ 23–27/9 → biên 4–8 ngày.**
  Space Docker trên `cpu-basic` **đòi PRO**; hết hạn = **link public trong DoD chết**.
  Trượt lịch một tuần là mất demo. Đây là **ràng buộc lịch cứng**, không phải nhắc nhở.
- **⚠️ Space ngủ sau 48 giờ** (`sleep_time=172800`) và **không có persistent storage**
  (`used_storage=0`) → mỗi lần khởi động lại, người mở đầu tiên trả **~28 s nạp model**
  (cộng 24 s container). **Đụng vào Space trước buổi bảo vệ** — đúng kỷ luật đã áp cho
  cluster Qdrant.
- **Giọng bệnh nhân nhóm E do LLM mô phỏng**, không phải câu người bệnh thật → hiệu ứng
  đo được là **cận dưới** của độ lệch thật. Phải vào Limitations.
- **Rủi ro tiến độ vẫn là số 1:** năng lực 1/2 nhưng scope giữ nguyên (DEC-015). Thứ tự
  cắt: E2 evidence-highlighting → ablation reranker on/off → ablation chunk 256 vs 512.
  **Giữ risk–coverage + Static-vs-Corrective bằng mọi giá.**

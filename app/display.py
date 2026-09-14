"""Tầng TRÌNH BÀY — quyết định UI được phép hiện gì (C3 + B3, Tuần 7).

Thuần Python: **không import streamlit**, không gọi model, không đọc `data/`.
Đó là cả lý do file này tồn tại.

## Vì sao tách ra khỏi `streamlit_app.py`

Trước Tuần 7, repo có 399 test và **0 test chạm `app/`**. Logic "có hiện khối
nguồn hay không" mà nằm trong callback Streamlit thì **không phép kiểm nào với
tới nó** — và đó đúng là hình dạng lỗi repo đã dính ba lần (ISSUE-071 · 073 ·
074): *một câu/một nhánh không có test nào chạm, nên nó sống sót qua chính sự
kiện làm nó sai*. Nước cờ này đã dùng 2 lần trước đó — `fmt_pct()` (DEC-064) và
`canh_bao_hai_trung_binh()` (ISSUE-073) — đây là lần thứ ba.

## ⚠️ File này KHÔNG vá pipeline, và KHÔNG được đổi số nào

`src/eval/answer_content.py` đã cân nhắc ba đường cho lỗi B3 và chọn đường (c):
*không đụng pipeline, báo cáo hai mẫu số*. File này **giữ nguyên lựa chọn đó**.
Nó không lật ``action``, không đổi ``chunks``, không chạm grader. Nó chỉ quyết
định **vẽ hay không vẽ** — nên mọi con số đã trích (``17/21`` coverage,
``0/30`` leakage, ``6/30`` nhãn tay, ``p = 0,0042``) **không đổi một chữ số**.

``is_refusal_text()`` được mượn từ tầng đo sang tầng vẽ. Đó là dùng đúng: ở đây
nó không phán quyết điều gì về **hệ thống**, chỉ phán quyết về **màn hình**.

## Ba cơ chế từ chối — đừng gộp khi hiển thị

Chúng khác nhau về **nguyên nhân**, nên phải khác nhau trên màn hình:

1. ``policy``    — chặn TRƯỚC truy hồi (nhóm D). Không có nguồn để hiện, và
                   hiện nguồn ở đây là mời người dùng tự suy ra chính câu vừa
                   bị chặn.
2. ``retrieval`` — corpus không đủ căn cứ (nhóm A/B). **``retrieved`` VẪN ĐẦY**
                   — xem cảnh báo dưới.
3. ``generator`` — grader cho qua, generator tự nói ngữ cảnh không đủ. Đây là
                   lỗi B3 (``E-21``). Tầng phòng thủ cuối cùng đang làm việc.

## ⛔ BẪY LỚN NHẤT — ``retrieved`` KHÔNG PHẢI ``chunks``

``PipelineResult`` có hai trường chunk, khác nhau **có chủ đích** (DEC-049):

- ``chunks``    = nguồn câu trả lời dựa vào → **thứ UI được phép hiện**
- ``retrieved`` = nguyên văn retriever trả về, **giữ lại kể cả khi từ chối**,
  vì Tuần 6 cần nó để chấm retrieval nhóm A/B — mà nhóm A/B thì LUÔN abstain

Đo trên `runs.jsonl`: **32/40 câu ABSTAIN có ``retrieved`` không rỗng.** Người
viết UI rất dễ hiện nó ra cho "minh bạch" → tái tạo đúng cái lỗi B3 mà file này
sinh ra để vá, chỉ khác đường vào.

**Quy tắc: UI đọc ``chunks``. UI KHÔNG BAO GIỜ đọc ``retrieved``.**
Có test khoá chiều này (`test_display.py`).
"""

from __future__ import annotations

from src.data.cleaner import strip_byline
from src.eval.answer_content import is_refusal_text
from src.schemas import PipelineResult, RetrievedChunk

#: Tiền tố mà `pipeline._route` gắn vào `note` của bước ABSTAIN khi policy gate
#: chặn. Hằng số hoá để chỗ đọc và chỗ ghi không trôi khỏi nhau — cùng lý do
#: `stats.py` cấm chép bản sao thứ hai của bất kỳ hàm nào.
POLICY_NOTE_PREFIX = "policy:"


def co_che_tu_choi(result: PipelineResult) -> str | None:
    """Câu này bị từ chối bằng cơ chế nào — ``policy`` / ``retrieval`` /
    ``generator`` / ``None`` (không từ chối).

    Đọc **``trace``**, không suy từ ``retrieved``. `corrective-loop.md` quy định
    hai cơ chế ABSTAIN phải tách được **trong trace**, và `pipeline._route` ghi
    đúng như vậy: policy thì bước ABSTAIN mang ``note="policy:<rule_id>"``,
    retrieval thì mang ``state="INCORRECT"``.

    Suy từ ``retrieved`` rỗng/đầy thì **cũng ra đúng** trên dữ liệu hiện có,
    nhưng đó là trùng hợp của cách cài đặt, không phải hợp đồng — và nó sẽ sai
    lặng lẽ ngày nào đó policy gate chạy sau truy hồi.
    """
    for buoc in result.trace:
        if buoc.step == "ABSTAIN":
            if (buoc.note or "").startswith(POLICY_NOTE_PREFIX):
                return "policy"
            return "retrieval"

    # Không có bước ABSTAIN nhưng generator vẫn tự từ chối bằng câu chữ (B3).
    if is_refusal_text(result.answer):
        return "generator"
    return None


def ma_luat_policy(result: PipelineResult) -> str | None:
    """Mã luật (``D-3``/``D-4``…) nếu bị policy gate chặn, ngược lại ``None``.

    Hiện mã luật ra màn hình là cách rẻ nhất để phân biệt *"hệ thống từ chối vì
    an toàn"* với *"hệ thống không tìm thấy gì"* — hai thứ trông giống nhau với
    người xem nhưng là hai đóng góp khác nhau của đề tài.
    """
    for buoc in result.trace:
        if buoc.step == "ABSTAIN" and (buoc.note or "").startswith(POLICY_NOTE_PREFIX):
            return buoc.note[len(POLICY_NOTE_PREFIX) :] or None
    return None


def nen_hien_nguon(result: PipelineResult) -> bool:
    """Có được vẽ khối nguồn cho kết quả này không?

    Đúng **hai** điều kiện, và cả hai đều cần:

    1. ``chunks`` không rỗng — pipeline đã dọn sạch ở mọi nhánh ABSTAIN
       (đo trên `runs.jsonl`: 40/40 câu ABSTAIN có ``n_chunks_shown == 0``).
    2. Câu trả lời **không phải lời từ chối trá hình** — đây là phần lỗi B3,
       thứ điều kiện 1 **không** bắt được vì ``action`` vẫn là ANSWER.

    ⚠️ Cố ý **không** đọc ``result.retrieved``. Xem docstring module.
    """
    return bool(result.chunks) and not is_refusal_text(result.answer)


def ly_do_an_nguon(result: PipelineResult) -> str | None:
    """Câu giải thích vì sao khối nguồn bị ẩn — ``None`` nếu nguồn được hiện.

    UI **phải** in câu này ra. Ẩn nguồn mà không nói gì thì người xem không
    phân biệt được "hệ thống không có nguồn" với "giao diện bị lỗi", và một
    demo để người ta đoán là một demo tự bôi xấu mình.
    """
    if nen_hien_nguon(result):
        return None

    co_che = co_che_tu_choi(result)
    if co_che == "policy":
        ma = ma_luat_policy(result)
        duoi = f" (luật {ma})" if ma else ""
        return (
            f"Câu hỏi bị **policy gate** chặn trước khi truy hồi{duoi}, nên "
            f"không có nguồn nào được đọc."
        )
    if co_che == "retrieval":
        return (
            "Hệ thống **không tìm đủ căn cứ** trong corpus nên đã từ chối. "
            "Nguồn bị ẩn có chủ đích: kèm nguồn vào một câu từ chối sẽ khiến "
            "người đọc hiểu ngược thông điệp."
        )
    if co_che == "generator":
        return (
            "Grader cho qua nhưng **generator tự nhận ngữ cảnh không đủ** — "
            "tầng phòng thủ cuối cùng đã chặn. Nguồn bị ẩn vì câu trả lời "
            "không dựa vào chúng."
        )
    return "Không có nguồn để hiển thị."


def doc_nguon(chunk: RetrievedChunk) -> str:
    """Văn bản chunk **đã cắt byline**, dùng cho mọi chỗ UI in nội dung nguồn.

    ⛔ Corpus trong Qdrant **vẫn còn byline** — DEC-020 đã quyết không chạy lại
    ingestion, nên không có tầng nào cắt hộ ở đường đọc. ``strip_byline`` hiện
    chỉ được áp ở `generation/context.py` (đường dựng **prompt**), tức LLM không
    bao giờ thấy byline **nhưng màn hình thì có**.

    Quy mô: 12,4% bài có byline (175/1410), và đã quan sát **3/5 chunk** trong
    một top-5 hybrid thật mở đầu bằng *"Bài viết được tư vấn chuyên môn bởi Bác
    sĩ…"*. Không cắt = hội đồng đọc tên một bác sĩ thật trong khối nguồn, và hệ
    thống trông như đang trích dẫn *"BS X khẳng định…"*.
    """
    return strip_byline(chunk.text)

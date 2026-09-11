"""Tầng NỘI DUNG của câu trả lời — phân biệt với tầng HÀNH ĐỘNG.

Repo đã có sẵn hai tầng đo cho **leakage** (DEC-062): tầng hành động đọc
``action``, tầng nội dung đọc câu chữ generator viết ra. Module này mang cùng
một ý đó sang **coverage**.

## Vì sao cần

``action == "ANSWER"`` nói rằng grader cho qua và pipeline đi nhánh trả lời.
Nó **không** nói rằng câu trả lời có nội dung. Quét toàn bộ 59 câu nhánh
corrective (2026-09-11): **18 câu ra ANSWER, 2 trong đó nói "không có thông
tin"** — ``E-21`` (nhóm E → làm coverage đếm dư 1) và ``A-01`` (nhóm A; lọt
lưới ở tầng hành động nhưng **vô hại** ở tầng nội dung, đúng ghi nhận DEC-056).

Generator làm thế là **đúng theo prompt**: ``config/prompts/generation.txt``
bảo nó *"nếu ngữ cảnh không chứa thông tin cần thiết, hãy nói rõ là chưa đủ"*.
Nên đây là **tầng phòng thủ cuối cùng đang làm việc**, không phải một lỗi.

## ⚠️ Module này KHÔNG vá pipeline — cố ý

Có ba đường xử lý, và repo chọn đường thứ ba:

(a) hậu kiểm regex rồi **lật `action`** → thành regex thứ tư của repo, sau
    DEC-044 (policy) và DEC-045 (byline). Đoán ý generator bằng chuỗi ký tự.
(b) bắt generator trả **sentinel** (``INSUFFICIENT_CONTEXT``) rồi lật ở
    pipeline → sạch nhất về thiết kế, **nhưng** đổi prompt = đổi câu trả lời =
    lô 45 phút phải chạy lại, và mọi ``docs/`` đã đối chứng byte-identical mất
    hiệu lực. Ở Tuần 6 còn 2 tuần thì cái giá đó sai. → **Future Work.**
(c) ✅ **không đụng pipeline, báo cáo HAI MẪU SỐ** — đúng khuôn DEC-062 đã
    dùng cho leakage (6/30 chính + 3/22, 3/19 độ nhạy).

Lợi thế quyết định của (c): ``17/21`` đang nằm ở DEC-051/055/061/063 +
``constraints.md`` + đường cong risk–coverage. Đổi nó thành ``16/21`` là sửa 6
chỗ **và dựng lại đường cong**. Giữ ``17/21`` làm số chính thì **0 chỗ** phải
sửa, mà người đọc vẫn thấy đủ.

Và (c) trung thực hơn (b): (b) làm hiện tượng biến mất bằng cách đổi hệ thống;
(c) ghi nhận rằng *grader cho qua nhưng generator từ chối* — một **kết quả**.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

#: Mẫu nhận ra câu trả lời **không có phát biểu thực chất**.
#:
#: ⚠️ Đây là **dụng cụ đo**, không phải bản vá. Xem docstring module.
_REFUSAL_RE = re.compile(
    r"(ngữ cảnh|tài liệu|thông tin được cung cấp)\s.{0,40}?"
    r"(không (chứa|có|đủ|đề cập)|chưa (đủ|có))"
    r"|không (chứa|có) thông tin"
    r"|chưa đủ thông tin",
    re.IGNORECASE | re.DOTALL,
)

#: Chỉ quét phần ĐẦU câu trả lời. Lời từ chối của generator luôn ở câu đầu;
#: quét cả bài thì một câu trả lời thật có kèm ghi chú *"tài liệu không đề cập
#: tới liều trẻ em"* sẽ bị đếm nhầm, và mẫu số phình ra một cách âm thầm.
REFUSAL_WINDOW = 240


def is_refusal_text(answer: str) -> bool:
    """Câu trả lời này có phải **lời từ chối trá hình** không?

    Tức ``action`` nói ANSWER, nhưng generator tự nói ngữ cảnh không đủ.
    """
    return bool(_REFUSAL_RE.search((answer or "")[:REFUSAL_WINDOW]))


def coverage_two_layers(
    records: Sequence[dict],
    answered,
    group: str = "E",
) -> dict:
    """Coverage ở **cả hai tầng**, trên cùng một bộ bản ghi.

    ``action``  — số câu pipeline đi nhánh trả lời. **SỐ CHÍNH**: đó là thứ cơ
                  chế ngưỡng thật sự sinh ra, và là con số mọi DEC đang trích.
    ``content`` — trừ đi câu mà generator tự từ chối. **SỐ ĐỘ NHẠY.**

    ``answered`` là vị từ ``rec -> bool`` (dùng ``arms.answered_at_turn1`` cho
    cấu hình đang chạy thật). Truyền vào thay vì tự đoán, để module này không
    phải biết gì về chuyện nhánh nào là nhánh nào.

    ⚠️ **Đừng thay số chính bằng số nội dung.** Hai tầng trả lời hai câu hỏi
    khác nhau: *"cơ chế có cho qua không"* và *"người dùng có nhận được nội
    dung không"*. Báo cáo cần cả hai; chọn một là giấu đi nửa còn lại.
    """
    trong_nhom = [r for r in records if r.get("group") == group]
    tra_loi = [r for r in trong_nhom if answered(r)]
    tu_choi = [r for r in tra_loi if is_refusal_text(r.get("answer") or "")]

    return {
        "n": len(trong_nhom),
        "action": len(tra_loi),
        "content": len(tra_loi) - len(tu_choi),
        "refusal_ids": sorted(r["id"] for r in tu_choi),
    }


def refusal_ids(records: Sequence[dict]) -> list[str]:
    """Mọi bản ghi ``ANSWER`` mà nội dung là lời từ chối — không lọc theo nhóm.

    Trên lô hiện tại ra đúng ``["A-01", "E-21"]``.
    """
    return sorted(
        r["id"]
        for r in records
        if r.get("action") in ("ANSWER", "ANSWER_WITH_CAUTION")
        and is_refusal_text(r.get("answer") or "")
    )

"""Thống kê cho mẫu NHỎ — khoảng tin cậy và kiểm định phi tham số.

Mọi con số an toàn của đề tài đều rơi vào vùng khó nhất của thống kê: n nhỏ
(21 câu E, 30 câu A/B) và tỉ lệ sát 0 hoặc sát 1. Đúng vùng mà công thức quen
thuộc cho khoảng tin cậy sai lệch nhất, nên chỗ này để riêng ra một module.

Thuần số: không mạng, không model, không đọc file — import được ở mọi nơi.

✅ **BẢN CÓ THẨM QUYỀN DUY NHẤT — bản sao đã dọn xong 2026-09-08.**
``wilson``/``rule_of_three`` từng nằm trong ``scripts/calibrate_threshold.py``
và ``sign_test`` trong ``scripts/eval_register_shift.py``; cả ba bản sao đã bị
xoá, hai script giờ import từ đây. Trước khi xoá đã quét đối chứng 1.890 cặp
``(k, n)`` và 3.005 vector hiệu — ba bản trùng khớp tuyệt đối, nên mọi con số
đã in ra báo cáo vẫn nguyên hiệu lực.

⛔ **ĐỪNG chép lại một bản thứ hai của bất kỳ hàm nào dưới đây.** Hai bản của
cùng một phép tính thì sớm muộn lệch nhau, và lệch ở đây nghĩa là hai bảng
trong CÙNG một báo cáo dùng hai định nghĩa khoảng tin cậy khác nhau mà không
ai thấy. Đây là nước cờ chống trôi lần thứ tư của repo — sau DEC-044 (regex
policy) · DEC-045 (regex byline) · DEC-046 (client LLM). Module thuần số,
không phụ thuộc gì, nên không có lý do "import nặng quá" để chép lại.
"""

from __future__ import annotations

import math

# Mức tin cậy 95% — hai phía, phân phối chuẩn.
Z = 1.96


def wilson(k: int, n: int) -> tuple[float, float]:
    """Khoảng tin cậy Wilson 95% cho tỉ lệ ``k/n``.

    Dùng Wilson chứ không dùng Wald (``p ± z·sqrt(p(1-p)/n)``): với n nhỏ và
    p gần 0 hoặc 1 — đúng vùng của bài này — Wald cho khoảng **vượt ra ngoài
    [0,1]** và hẹp một cách sai lệch. Ví dụ 0/30 thì Wald ra đúng khoảng
    ``[0, 0]``, tức "chứng minh được leakage bằng 0", điều hoàn toàn sai.
    """
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + Z * Z / n
    center = (p + Z * Z / (2 * n)) / denom
    half = (Z / denom) * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    lo, hi = max(0.0, center - half), min(1.0, center + half)
    # Ở hai biên, `center` và `half` bằng nhau về mặt TOÁN HỌC (với k=0 thì
    # p=0 nên cả hai cùng rút gọn về `Z²/(2n·denom)`), nên cận phải đúng bằng
    # 0 — float để lại cặn cỡ 2,8e-17. Cặn đó vô hại lúc in (`:.0f`) nhưng làm
    # `wilson(0, n)[0] == 0.0` trả về False, tức một phép so sánh hiển nhiên
    # đúng lại sai, và làm hỏng cả bất biến `lo <= k/n <= hi`. Chốt về giá trị
    # đúng. (Bắt được nhờ `tests/test_stats.py` ngay lượt chạy đầu tiên của nó.)
    if k == 0:
        lo = 0.0
    if k == n:
        hi = 1.0
    return (lo, hi)


def rule_of_three(n: int) -> float:
    """Cận trên 95% của tỉ lệ khi quan sát ĐÚNG 0 sự kiện trong n lượt.

    Đây là câu trả lời cho "0/30 nghĩa là gì": không phải "bằng 0", mà là
    "nhỏ hơn 3/30 = 10%".

    ⛔ **KHÔNG IN HÀM NÀY VÀO ``docs/`` NỮA — B1 chuẩn hoá toàn repo về Wilson.**
    Hàm vẫn ở đây, và việc giữ nó là có chủ ý, vì hai lý do:
    (1) docstring này là chỗ duy nhất trong repo giải thích *"0/n nghĩa là gì"*;
    (2) xoá hàm rồi lúc cần lại chính là đường mời **bản sao thứ tư** vào nhà —
    xem cảnh báo đầu module.

    Vì sao Wilson thắng, ghi lại để khỏi mở lại cuộc tranh luận:
    - Quy tắc số ba **chỉ định nghĩa được khi k = 0**. Repo còn phải trích
      ``6/30`` (leakage nội dung), ``17/21`` (coverage), ``3/22``, ``3/19`` —
      với những số đó quy tắc số ba **không nói được gì**.
    - Wilson **đã là mặc định trên thực tế**: ``fmt_pct`` gọi thẳng nó, mà
      ``fmt_pct`` là đường in chính của ``arms.py`` + ``leakage.py``.
    - Ở **mọi mẫu số repo thật sự trích** Wilson bảo thủ hơn: ``0/30`` → Wilson
      ``0–11%`` so với quy tắc số ba ``< 10%``. Trích cận rộng hơn thì không ai
      bắt bẻ được.
      ⚠️ **Có điều kiện, đừng nới phát biểu ra:** với ``k = 0`` cận trên Wilson
      rút gọn thành ``Z²/(n+Z²)``, nên nó rộng hơn ``3/n`` **chỉ khi
      ``n ≥ 14``** (điểm đảo chiều ``3Z²/(Z²−3) ≈ 13,69``). Ở ``n = 12`` —
      đúng cỡ riêng nhóm B — thì **ngược lại**. Lý do (3) đứng vững nhờ dải n
      của repo (mọi mẫu số đều ``n ≥ 19``), không nhờ một tính chất phổ quát.
      Khoá ở ``tests/test_stats.py::test_wilson_bao_thu_hon_tu_n_14``.

    Dùng được: đối chứng nhanh khi nghi Wilson cài sai (xem ``tests/test_stats.py``).
    """
    return 3.0 / n if n else 1.0


def sign_test(diffs: list[float]) -> tuple[int, int, float]:
    """Kiểm định dấu (nhị thức chính xác, hai phía). Trả ``(âm, dương, p)``.

    Dùng kiểm định dấu chứ không dùng t-test: n nhỏ và phân bố điểm nhóm E
    **lưỡng cực** (DEC-051, vực 3,06 logit giữa hai cụm) nên giả định chuẩn
    của t-test sai ngay từ đầu. Kiểm định dấu không giả định gì về phân bố —
    đổi lại nó yếu hơn, và đó là cái giá đúng phải trả khi không biết dạng
    phân bố.

    Cặp bằng nhau đúng bằng 0 bị **loại khỏi mẫu số** (quy ước chuẩn của kiểm
    định dấu), nên ``âm + dương`` có thể nhỏ hơn ``len(diffs)``.
    """
    neg = sum(1 for d in diffs if d < 0)
    pos = sum(1 for d in diffs if d > 0)
    n = neg + pos
    if n == 0:
        return neg, pos, 1.0
    k = min(neg, pos)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return neg, pos, min(1.0, 2 * tail)


def quantile(xs: list[float], p: float) -> float:
    """Phân vị ``p`` (0–1) bằng **nội suy tuyến tính** giữa hai thứ tự kề.

    Thêm ở Tuần 7 cho bảng latency p50/p95. Đặt ở đây chứ không trong script
    báo cáo vì đúng lý do module này tồn tại: p95 sẽ được trích ở **nhiều** chỗ
    (bảng latency, slide, phần Q&A), và hai bản sao thì sớm muộn dùng hai quy
    ước khác nhau.

    ⚠️ **Định nghĩa được viết ra thay vì mượn `statistics.quantiles()`** — có
    chủ đích. Stdlib mặc định ``method="exclusive"`` cho kết quả **khác** nội
    suy tuyến tính, và khác **nhiều** ở n nhỏ: mẫu ANSWER chỉ có **18 câu**, ở
    cỡ đó lựa chọn quy ước dịch p95 vài giây. Một con số đi vào báo cáo thì
    quy ước sinh ra nó phải đọc được, không nằm trong mặc định của thư viện.

    ``p95`` trên n nhỏ vốn là ước lượng thô — với n = 18 nó nội suy giữa mẫu
    thứ 17 và 18, tức **gần như chính là max**. Trích kèm n, đừng trích trần.
    """
    if not xs:
        raise ValueError("quantile của dãy rỗng")
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p phải trong [0, 1], nhận {p}")
    ys = sorted(xs)
    if len(ys) == 1:
        return float(ys[0])
    k = (len(ys) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(ys) - 1)
    return float(ys[lo] + (ys[hi] - ys[lo]) * (k - lo))


def fmt_pct(k: int, n: int) -> str:
    """``k/n`` kèm phần trăm và khoảng tin cậy Wilson, dạng Markdown.

    ⚠️ **GỌI TÊN "Wilson" TRONG CHUỖI TRẢ VỀ — cố ý, đừng rút gọn lại** (B1).
    Repo từng trích lẫn lộn hai cận trên cho cùng một phép đo ``0/30``:
    Wilson ``0–11%`` ở chỗ này, quy tắc số ba ``< 10%`` ở chỗ kia. Cả hai đều
    đúng, nên người đọc **không có cách nào** biết con số trước mặt là cái nào
    nếu phương pháp không được gọi tên. Sửa ở đây thì mọi call site
    (``arms.py``, ``leakage.py``, mọi script) được đặt tên cùng một lúc.
    """
    if n == 0:
        return "0/0 = **—**"
    lo, hi = wilson(k, n)
    return (
        f"{k}/{n} = **{100 * k / n:.0f}%** "
        f"(CI 95% Wilson {100 * lo:.0f}–{100 * hi:.0f}%)"
    )

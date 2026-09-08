"""Thống kê cho mẫu NHỎ — khoảng tin cậy và kiểm định phi tham số.

Mọi con số an toàn của đề tài đều rơi vào vùng khó nhất của thống kê: n nhỏ
(21 câu E, 30 câu A/B) và tỉ lệ sát 0 hoặc sát 1. Đúng vùng mà công thức quen
thuộc cho khoảng tin cậy sai lệch nhất, nên chỗ này để riêng ra một module.

Thuần số: không mạng, không model, không đọc file — import được ở mọi nơi.

⚠️ **HAI BẢN SAO ĐANG TỒN TẠI, ghi ra đây thay vì im lặng.**
Ba hàm dưới đây được viết TRƯỚC module này, nằm trong hai script:

    scripts/calibrate_threshold.py   -> wilson(), rule_of_three()
    scripts/eval_register_shift.py   -> sign_test()

Ba bản hiện giống hệt nhau về công thức. Nhưng đây đúng là loại trôi đã phải
vá ba lần rồi (DEC-044 regex policy · DEC-045 regex byline · DEC-046 client
LLM): hai bản của cùng một phép tính thì sớm muộn lệch nhau, và lệch ở đây
nghĩa là hai bảng trong CÙNG một báo cáo dùng hai định nghĩa khoảng tin cậy
khác nhau mà không ai thấy. **Việc dọn:** trỏ hai script trên về module này
rồi xoá bản sao của chúng. Chưa làm trong phiên này vì cả hai file đang nằm
trong lô commit dở của Đạt — sửa vào là gây xung đột cho việc đang chạy.
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
    return (max(0.0, center - half), min(1.0, center + half))


def rule_of_three(n: int) -> float:
    """Cận trên 95% của tỉ lệ khi quan sát ĐÚNG 0 sự kiện trong n lượt.

    Đây là câu trả lời cho "0/30 nghĩa là gì": không phải "bằng 0", mà là
    "nhỏ hơn 3/30 = 10%". Con số này phải đi kèm mọi lần trích một mẫu số 0.
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


def fmt_pct(k: int, n: int) -> str:
    """``k/n`` kèm phần trăm và khoảng tin cậy Wilson, dạng Markdown."""
    if n == 0:
        return "0/0 = **—**"
    lo, hi = wilson(k, n)
    return (
        f"{k}/{n} = **{100 * k / n:.0f}%** "
        f"(CI 95% {100 * lo:.0f}–{100 * hi:.0f}%)"
    )

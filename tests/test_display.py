"""Test cho `app/display.py` — tầng TRÌNH BÀY (C3 + B3, Tuần 7).

Thuần văn bản: không Streamlit, không LLM, không mạng, không đọc `data/`.

## Chuỗi trong file này là THẬT

Câu trả lời của `E-21`, `A-01`, `E-01` chép **nguyên văn** từ
`data/processed/runs.jsonl`; byline chép nguyên văn từ `data/processed/corpus.jsonl`.
Cùng quy ước với `test_answer_content.py`: test tầng văn bản mà bịa chuỗi thì
nó chỉ chứng minh regex khớp chính chuỗi vừa bịa.

## ⚠️ `A-01` là LỊCH SỬ, `E-21` mới là ca còn sống

`runs.jsonl` sinh 2026-09-08, **trước** DEC-061 (2026-09-09). Trong file đó
`A-01` đi `... REWRITE -> RETRIEVE -> GRADE -> GENERATE` — tức lượt 2 **lật**
được phán quyết INCORRECT của lượt 1. Với `allow_turn2_promotion: false` đang
chạy, đường đó **không còn tồn tại**: `A-01` nay dừng ở GUARD rồi ABSTAIN.

→ Dưới config hiện tại, lỗi B3 chỉ còn phát sinh được ở **lượt 1** (`E-21`).
`A-01` vẫn được giữ làm ca test vì câu chữ generator viết ra là thật và phép
nhận diện phải bắt được nó, **nhưng đừng đọc file này thành "hệ thống hiện có
2 ca B3"** — đó là con số của bản chạy tiền-guard.
"""

from __future__ import annotations

import pytest

from app.display import (
    co_che_tu_choi,
    doc_nguon,
    ly_do_an_nguon,
    ma_luat_policy,
    nen_hien_nguon,
)
from src.schemas import PipelineResult, RetrievedChunk, TerminalAction, TraceStep

# --------------------------------------------------------------------------- #
# Chuỗi thật
# --------------------------------------------------------------------------- #

#: `E-21`, nhóm E. Grader cho qua ở LƯỢT 1, generator tự từ chối. Ca B3 còn sống.
TL_E21 = (
    "Ngữ cảnh được cung cấp không chứa thông tin về vai trò của siêu âm tim "
    "trong chẩn đoán bệnh cơ tim phì đại.\n\nThông tin chỉ mang tính tham "
    "khảo, không thay thế tư vấn của bác sĩ."
)

#: `A-01`, nhóm A. Lọt ở LƯỢT 2 — đường đã bị DEC-061 chặn. Xem docstring module.
TL_A01 = (
    "Ngữ cảnh không chứa thông tin về vai trò của siêu âm tim trong chẩn đoán, "
    "đánh giá, xác định nguyên nhân và mức độ nghiêm trọng của âm thổi tim "
    "(tiếng thổi ở tim, tiếng tim bất thường).\n\nThông tin chỉ mang tính tham "
    "khảo, không thay thế tư vấn của bác sĩ."
)

#: `E-01`, nhóm E. Câu trả lời THẬT, có nội dung, có citation.
TL_E01 = (
    "Biến chứng loét chân ở bệnh nhân tiểu đường có thể dẫn đến những biến "
    "chứng nguy hiểm như hoại tử các ngón chân, tàn phế, cắt cụt chi [1]."
)

#: `A-08`, nhánh AMBIGUOUS -> ANSWER_WITH_CAUTION.
TL_A08 = (
    "[Lưu ý: độ chắc chắn thấp]\n\nNgoài Lithium, các nhóm thuốc sau đây có "
    "thể gây tương tác thuốc bất lợi với Co-Diovan [2]."
)

#: Byline thật, chép từ `corpus.jsonl`.
BYLINE_THAT = (
    "Bài viết được tư vấn chuyên môn bởi Thạc sĩ, Bác sĩ Lê Thị Minh Hương - "
    "Bác sĩ Hồi sức cấp cứu - Khoa Hồi sức - Cấp cứu - Bệnh viện Đa khoa Quốc "
    "tế Vinmec Nha Trang . "
)
THAN_BAI = "Glucose đóng vai trò rất quan trọng trong chuyển hoá năng lượng."


def _chunk(i: int = 1, text: str = THAN_BAI) -> RetrievedChunk:
    return RetrievedChunk(
        doc_id=f"doc{i}", text=text, specialty="tim_mach", score=0.95, chunk_idx=0
    )


def _nam_chunk() -> list[RetrievedChunk]:
    return [_chunk(i) for i in range(1, 6)]


def _kq(
    action: TerminalAction,
    answer: str,
    chunks: list[RetrievedChunk] | None = None,
    trace: list[TraceStep] | None = None,
    retrieved: list[RetrievedChunk] | None = None,
) -> PipelineResult:
    return PipelineResult(
        query="câu hỏi thử",
        action=action,
        answer=answer,
        chunks=chunks if chunks is not None else [],
        trace=trace or [],
        retrieved=retrieved if retrieved is not None else (chunks or []),
    )


# Bốn nhánh thật, dựng theo đúng `trace` mà `pipeline._route` ghi ra.
def kq_tra_loi() -> PipelineResult:
    return _kq(
        TerminalAction.ANSWER,
        TL_E01,
        _nam_chunk(),
        [
            TraceStep("POLICY", None, None, ""),
            TraceStep("RETRIEVE", None, None, ""),
            TraceStep("GRADE", "CORRECT", 0.96, ""),
            TraceStep("GENERATE", None, None, ""),
        ],
    )


def kq_caution() -> PipelineResult:
    return _kq(
        TerminalAction.ANSWER_WITH_CAUTION,
        TL_A08,
        _nam_chunk(),
        [
            TraceStep("POLICY", None, None, ""),
            TraceStep("GRADE", "AMBIGUOUS", 0.9255, ""),
            TraceStep("GENERATE", None, None, ""),
        ],
    )


def kq_b3() -> PipelineResult:
    """`E-21` — action ANSWER, chunks ĐẦY, nhưng câu trả lời là lời từ chối."""
    return _kq(
        TerminalAction.ANSWER,
        TL_E21,
        _nam_chunk(),
        [
            TraceStep("POLICY", None, None, ""),
            TraceStep("RETRIEVE", None, None, ""),
            TraceStep("GRADE", "CORRECT", 0.9375, ""),
            TraceStep("GENERATE", None, None, ""),
        ],
    )


def kq_abstain_policy() -> PipelineResult:
    """Nhóm D — chặn trước truy hồi, `chunks` VÀ `retrieved` đều rỗng."""
    return _kq(
        TerminalAction.ABSTAIN,
        "Xin lỗi, đây là câu hỏi cần bác sĩ trực tiếp thăm khám.",
        [],
        [
            TraceStep("POLICY", None, None, "D-3"),
            TraceStep("ABSTAIN", None, None, "policy:D-3"),
        ],
        retrieved=[],
    )


def kq_abstain_truy_hoi() -> PipelineResult:
    """Nhóm A/B — `chunks` rỗng nhưng **`retrieved` còn đầy 5 chunk** (DEC-049)."""
    return _kq(
        TerminalAction.ABSTAIN,
        "Tôi không tìm thấy đủ căn cứ trong tài liệu để trả lời câu hỏi này.",
        [],
        [
            TraceStep("POLICY", None, None, ""),
            TraceStep("RETRIEVE", None, None, ""),
            TraceStep("GRADE", "INCORRECT", 0.42, ""),
            TraceStep("REWRITE", None, None, "câu hỏi viết lại"),
            TraceStep("GUARD", "INCORRECT", None, ""),
            TraceStep("ABSTAIN", "INCORRECT", None, ""),
        ],
        retrieved=_nam_chunk(),
    )


# --------------------------------------------------------------------------- #
# nen_hien_nguon — KHOÁ CẢ HAI CHIỀU
#
# Bài học ISSUE-073: vá sai chiều còn hại hơn lỗi gốc. Ẩn nguồn ở câu từ chối
# là đúng; ẩn luôn nguồn của câu trả lời thật thì demo mất hết trích dẫn — tức
# mất đúng trục đóng góp của đề tài. Nên cả hai chiều đều phải có test.
# --------------------------------------------------------------------------- #


def test_cau_tra_loi_that_thi_HIEN_nguon():
    assert nen_hien_nguon(kq_tra_loi()) is True


def test_caution_van_HIEN_nguon():
    """AMBIGUOUS vẫn TRẢ LỜI, nên vẫn phải có nguồn — chỉ khác badge."""
    assert nen_hien_nguon(kq_caution()) is True


def test_B3_an_nguon_E21():
    """⛔ REPRODUCER — lỗi B3: action=ANSWER, 5 chunk, mà câu trả lời từ chối."""
    kq = kq_b3()
    assert kq.action == TerminalAction.ANSWER
    assert len(kq.chunks) == 5, "tiền đề: pipeline KHÔNG dọn chunks ở nhánh này"
    assert nen_hien_nguon(kq) is False


def test_B3_an_nguon_A01():
    kq = _kq(TerminalAction.ANSWER, TL_A01, _nam_chunk())
    assert nen_hien_nguon(kq) is False


def test_abstain_policy_an_nguon():
    assert nen_hien_nguon(kq_abstain_policy()) is False


def test_abstain_truy_hoi_an_nguon_DU_retrieved_CON_DAY():
    """⛔ Khoá bẫy DEC-049: `retrieved` đầy 5 chunk mà vẫn phải ẩn."""
    kq = kq_abstain_truy_hoi()
    assert len(kq.retrieved) == 5, "tiền đề: retrieved KHÔNG rỗng ở nhánh này"
    assert kq.chunks == []
    assert nen_hien_nguon(kq) is False


def test_nen_hien_nguon_KHONG_BAO_GIO_doc_retrieved():
    """Khoá bằng MÁY, không bằng lời hứa.

    `retrieved` ở đây ném ngay khi bị chạm. Test trên (`..._DU_retrieved_CON_DAY`)
    chỉ kiểm **giá trị** trả về đúng; test này kiểm **đường đi** — một bản sửa
    tương lai đọc `retrieved` để "hiện cho minh bạch" sẽ đỏ ngay tại đây, kể cả
    khi nó tình cờ vẫn trả về đúng.
    """

    class KQBayRetrieved:
        query = "câu hỏi thử"
        action = TerminalAction.ANSWER
        answer = TL_E01
        chunks = _nam_chunk()
        trace: list[TraceStep] = []
        rewritten_query = None

        @property
        def retrieved(self):
            raise AssertionError(
                "UI đọc `retrieved` — đó là trường của tầng EVAL (DEC-049). "
                "UI chỉ được đọc `chunks`."
            )

    assert nen_hien_nguon(KQBayRetrieved()) is True  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# co_che_tu_choi — ba cơ chế phải tách được
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "dung_kq, mong_doi",
    [
        (kq_tra_loi, None),
        (kq_caution, None),
        (kq_abstain_policy, "policy"),
        (kq_abstain_truy_hoi, "retrieval"),
        (kq_b3, "generator"),
    ],
)
def test_co_che_tu_choi(dung_kq, mong_doi):
    assert co_che_tu_choi(dung_kq()) == mong_doi


def test_co_che_doc_TRACE_chu_khong_suy_tu_retrieved():
    """Policy-abstain mà `retrieved` vì lý do nào đó không rỗng → vẫn là policy.

    Suy cơ chế từ `retrieved` rỗng/đầy ra đúng trên dữ liệu hiện có, nhưng đó
    là trùng hợp của cách cài đặt. Hợp đồng (`corrective-loop.md`) nói tách
    bằng **trace**. Test này khoá đúng chỗ đó.
    """
    kq = _kq(
        TerminalAction.ABSTAIN,
        "Xin lỗi…",
        [],
        [TraceStep("ABSTAIN", None, None, "policy:D-4")],
        retrieved=_nam_chunk(),
    )
    assert co_che_tu_choi(kq) == "policy"


def test_ma_luat_policy():
    assert ma_luat_policy(kq_abstain_policy()) == "D-3"
    assert ma_luat_policy(kq_abstain_truy_hoi()) is None
    assert ma_luat_policy(kq_tra_loi()) is None


# --------------------------------------------------------------------------- #
# ly_do_an_nguon — ẩn thì PHẢI nói vì sao
# --------------------------------------------------------------------------- #


def test_hien_nguon_thi_khong_co_ly_do():
    assert ly_do_an_nguon(kq_tra_loi()) is None
    assert ly_do_an_nguon(kq_caution()) is None


@pytest.mark.parametrize(
    "dung_kq", [kq_abstain_policy, kq_abstain_truy_hoi, kq_b3]
)
def test_an_nguon_thi_luon_co_cau_giai_thich(dung_kq):
    ly_do = ly_do_an_nguon(dung_kq())
    assert ly_do and len(ly_do) > 20


def test_ly_do_policy_neu_ro_ma_luat():
    assert "D-3" in (ly_do_an_nguon(kq_abstain_policy()) or "")


def test_ly_do_ba_co_che_KHAC_NHAU():
    """Ba cơ chế khác nguyên nhân → phải khác câu chữ, không được gộp."""
    ly_do = {
        ly_do_an_nguon(kq_abstain_policy()),
        ly_do_an_nguon(kq_abstain_truy_hoi()),
        ly_do_an_nguon(kq_b3()),
    }
    assert len(ly_do) == 3


# --------------------------------------------------------------------------- #
# doc_nguon — byline
# --------------------------------------------------------------------------- #


def test_doc_nguon_cat_byline_that():
    c = _chunk(text=BYLINE_THAT + THAN_BAI)
    ra = doc_nguon(c)
    assert "Bài viết được tư vấn chuyên môn bởi" not in ra
    assert "Lê Thị Minh Hương" not in ra
    assert "Glucose" in ra


def test_doc_nguon_khong_lam_hong_van_ban_khong_co_byline():
    assert doc_nguon(_chunk(text=THAN_BAI)) == THAN_BAI

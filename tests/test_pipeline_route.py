"""Test corrective loop của RAGPipeline với Fake components — 4 kịch bản.

Grader thật (thuần) được dùng; trạng thái grade điều khiển gián tiếp qua
rerank score do FakeRetriever trả về (scripted theo từng lần gọi).
"""

from src.config import (
    AppConfig,
    ChunkingConfig,
    CorrectiveConfig,
    DataConfig,
    GenerationConfig,
    GraderConfig,
    IndexConfig,
    ModelsConfig,
    QdrantConfig,
    RetrievalConfig,
)
from src.generation.generator import FakeGenerator
from src.pipeline.grader import Grader
from src.pipeline.pipeline import RAGPipeline
from src.pipeline.rewriter import FakeRewriter
from src.retrieval.retriever import FakeRetriever
from src.schemas import TerminalAction


def _cfg(max_iter: int = 1, allow_turn2: bool = False) -> AppConfig:
    return AppConfig(
        models=ModelsConfig("e", "r", "l"),
        # Pipeline không đụng tới khối `data`; điền giá trị giả cho đủ contract.
        data=DataConfig("d", "s", "title", "content", 100, "data/processed", 25),
        retrieval=RetrievalConfig(True, 20, 5),
        chunking=ChunkingConfig(512, 50),
        grader=GraderConfig(correct_threshold=0.6, incorrect_threshold=0.3),
        corrective=CorrectiveConfig(
            max_iter=max_iter, allow_turn2_promotion=allow_turn2
        ),
        generation=GenerationConfig(0.2),
        qdrant=QdrantConfig("http://x", "c"),
        # Pipeline không đụng khối `index` (chỉ dùng lúc dựng chỉ mục); giả nốt.
        index=IndexConfig([256, 512], 1024, "Cosine", 16, 128, 1024, False),
        specialties={},
    )


def _pipeline(
    scores: list[float], max_iter: int = 1, allow_turn2: bool = False
) -> RAGPipeline:
    cfg = _cfg(max_iter, allow_turn2)
    return RAGPipeline(
        cfg=cfg,
        retriever=FakeRetriever(scores=scores),
        generator=FakeGenerator(),
        grader=Grader(cfg.grader),
        rewriter=FakeRewriter(),
    )


def _steps(result) -> list[str]:
    return [s.step for s in result.trace]


def test_correct_answers_without_rewrite():
    """Kịch bản 1: luôn CORRECT -> ANSWER, không có REWRITE."""
    result = _pipeline(scores=[0.9]).answer("huyết áp cao là gì")
    assert result.action == TerminalAction.ANSWER
    assert "REWRITE" not in _steps(result)
    assert result.rewritten_query is None


def test_ambiguous_answers_with_caution():
    """Kịch bản 2: luôn AMBIGUOUS -> ANSWER_WITH_CAUTION."""
    result = _pipeline(scores=[0.45]).answer("triệu chứng tiểu đường")
    assert result.action == TerminalAction.ANSWER_WITH_CAUTION
    assert "REWRITE" not in _steps(result)
    assert "[CẢNH BÁO" in result.answer


def test_incorrect_then_recover_after_rewrite_KHI_GUARD_TAT():
    """Kịch bản 3 (hành vi CŨ): INCORRECT lần 1, CORRECT sau rewrite -> ANSWER.

    ⚠️ Từ DEC-061 đây **không còn là mặc định** — phải bật
    ``allow_turn2_promotion=True`` mới đi được nhánh này. Test giữ lại KHÔNG
    phải vì tiếc code cũ mà vì **đường tái lập DEC-056/057 phải còn sống**:
    con số leakage 2/30 chỉ dựng lại được ở cấu hình này. Xoá test này là xoá
    khả năng kiểm chứng lại chính kết quả âm mà báo cáo đang trích.
    """
    result = _pipeline(scores=[0.1, 0.9], allow_turn2=True).answer(
        "insulin dùng khi nào"
    )
    assert result.action == TerminalAction.ANSWER
    assert _steps(result).count("REWRITE") == 1
    assert "GUARD" not in _steps(result), "guard tắt thì không được ghi bước GUARD"
    assert result.rewritten_query is not None
    assert result.rewritten_query.endswith("(viết lại)")


# --------------------------------------------------------------------------- #
# DEC-061 — lớp chặn lượt 2
# --------------------------------------------------------------------------- #
def test_guard_chan_luot_2_lat_phan_quyet_incorrect():
    """Cùng kịch bản trên, guard BẬT (mặc định) -> ABSTAIN thay vì ANSWER.

    Đây là ca `A-01`/`A-08` của DEC-056 thu nhỏ: lượt 1 INCORRECT, rewrite kéo
    điểm vượt ngưỡng, lượt 2 đòi trả lời. Guard giữ lại.
    """
    result = _pipeline(scores=[0.1, 0.9]).answer("insulin dùng khi nào")
    assert result.action == TerminalAction.ABSTAIN
    assert _steps(result).count("REWRITE") == 1, "rewrite VẪN chạy"
    assert _steps(result)[-1] == "ABSTAIN"


def test_guard_van_de_luot_2_chay_va_giu_diem_trong_trace():
    """Guard tước quyền LẬT, KHÔNG tước quyền chạy.

    Điểm lượt 2 phải còn nguyên trong trace — đó là thứ DEC-056/057 đo được và
    là thứ bảng Tuần 6 ăn vào. Guard mà làm mất lượt 2 thì vá được leakage
    nhưng phá luôn dữ liệu chứng minh vì sao phải vá.
    """
    result = _pipeline(scores=[0.1, 0.9]).answer("q")
    grades = [s for s in result.trace if s.step == "GRADE"]
    assert len(grades) == 2, "vẫn phải có ĐỦ 2 lượt chấm"
    assert grades[0].state == "INCORRECT"
    assert grades[1].state == "CORRECT", "điểm lượt 2 giữ nguyên, không bị ghi đè"
    assert len(result.retrieved) > 0, "ngữ cảnh lượt 2 giữ cho eval (DEC-049)"


def test_guard_ghi_note_khi_chan_that_va_de_rong_khi_khong_co_gi_de_chan():
    """Quy ước `note` giống hệt bước POLICY: khác rỗng = đã chặn thật.

    Không có quy ước này thì Tuần 6 không tách được "guard đã chạy" khỏi
    "guard đã chặn" — hai phép đếm khác nhau, và cái sau mới là đóng góp.
    """
    from src.eval.trace_export import guard_ran, guard_suppressed

    chan = _pipeline(scores=[0.1, 0.9]).answer("q")
    assert guard_ran(chan.trace) is True
    assert guard_suppressed(chan.trace) == "CORRECT"

    khong_chan = _pipeline(scores=[0.1, 0.1]).answer("q")
    assert guard_ran(khong_chan.trace) is True, "guard vẫn CHẠY"
    assert guard_suppressed(khong_chan.trace) is None, "nhưng không chặn gì"

    khong_toi_luot_2 = _pipeline(scores=[0.9]).answer("q")
    assert guard_ran(khong_toi_luot_2.trace) is False


def test_guard_cung_chan_nhanh_ambiguous():
    """AMBIGUOUS ở lượt 2 cũng bị chặn — `ANSWER_WITH_CAUTION` VẪN là trả lời.

    Đây đúng chỗ `A-08` lọt: nó ra `ANSWER_WITH_CAUTION` chứ không phải
    `ANSWER`. Guard chỉ chặn CORRECT là để lọt lại nguyên ca cũ.
    """
    result = _pipeline(scores=[0.1, 0.45]).answer("q")
    assert result.action == TerminalAction.ABSTAIN
    from src.eval.trace_export import guard_suppressed

    assert guard_suppressed(result.trace) == "AMBIGUOUS"


def test_guard_khong_dung_toi_nhanh_tra_loi_ngay_luot_1():
    """Câu CORRECT ngay lượt 1 không bao giờ gặp guard — 17/21 câu E phải y nguyên."""
    result = _pipeline(scores=[0.9]).answer("q")
    assert result.action == TerminalAction.ANSWER
    assert "GUARD" not in _steps(result)


def test_guard_bat_thi_khong_ton_them_luot_rewrite_nao():
    """`break` chứ không `continue`: max_iter cao hơn cũng chỉ rewrite 1 lần.

    Guard bật thì lượt sau không lật được gì, chạy tiếp chỉ tốn lượt gọi LLM.
    """
    result = _pipeline(scores=[0.1, 0.1, 0.1], max_iter=3).answer("q")
    assert _steps(result).count("REWRITE") == 1
    assert result.action == TerminalAction.ABSTAIN


def test_incorrect_twice_abstains():
    """Kịch bản 4: INCORRECT cả 2 lần -> ABSTAIN, kết thúc bằng ABSTAIN, 1 REWRITE."""
    result = _pipeline(scores=[0.1, 0.1]).answer("câu hỏi ngoài phạm vi")
    assert result.action == TerminalAction.ABSTAIN
    assert _steps(result)[-1] == "ABSTAIN"
    assert _steps(result).count("REWRITE") == 1  # tôn trọng max_iter=1


def test_retriever_receives_rewritten_query():
    """Sau rewrite, retriever lần 2 phải nhận query đã viết lại."""
    retriever = FakeRetriever(scores=[0.1, 0.9])
    cfg = _cfg()
    pipe = RAGPipeline(
        cfg=cfg,
        retriever=retriever,
        generator=FakeGenerator(),
        grader=Grader(cfg.grader),
        rewriter=FakeRewriter(),
    )
    pipe.answer("q gốc")
    assert retriever.queries == ["q gốc", "q gốc (viết lại)"]


def test_retrieval_abstain_shows_no_sources_but_keeps_them_for_eval():
    """ABSTAIN-do-retrieval: `chunks` rỗng (UI), `retrieved` còn nguyên (eval).

    Trước DEC-049 nhánh này trả về cả 5 chunk, nên câu "tôi chưa đủ căn cứ" đi
    kèm 5 nguồn trông thuyết phục — người dùng hiểu ngược. Nhưng xoá hẳn thì
    Tuần 6 mất dữ liệu chấm retrieval của nhóm A/B, mà nhóm A/B LUÔN đi qua
    đúng nhánh này. Hai trường, hai mục đích.
    """
    result = _pipeline(scores=[0.1, 0.1]).answer("câu hỏi ngoài phạm vi")
    assert result.action == TerminalAction.ABSTAIN
    assert result.chunks == []
    assert len(result.retrieved) > 0
    assert all(c.score == 0.1 for c in result.retrieved)


def test_answer_paths_expose_the_same_chunks_in_both_fields():
    """Nhánh trả lời: `chunks` và `retrieved` phải trùng nhau."""
    result = _pipeline(scores=[0.9]).answer("huyết áp cao là gì")
    assert result.action == TerminalAction.ANSWER
    assert result.chunks == result.retrieved
    assert result.chunks

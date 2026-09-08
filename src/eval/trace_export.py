"""Biến kết quả pipeline thành bản ghi JSONL cho eval Tuần 6.

Vì sao phần này nằm ở ``src/`` chứ không nằm thẳng trong script: ``pytest``
**không hề chạm** ``scripts/`` (xem ``tests/test_scripts_parse.py``), nên mọi
logic có thể sai lặng lẽ phải ở đây để có test khoá. Thuần số + dict: không
mạng, không model, không đọc file.

⛔ BỐN THỨ FILE NÀY PHẢI GIỮ ĐÚNG — sai một cái là Tuần 6 ra bảng đẹp mà sai.

1. **Điểm của CẢ HAI lượt truy hồi**, không chỉ ``action`` cuối. Hiệu chỉnh
   LOOCV (DEC-051) chấm trên lượt **đầu**; vòng corrective còn cho mỗi câu
   INCORRECT một lần thử **thứ hai** chưa hiệu chỉnh. Không lưu lượt hai thì
   không chia lại fold được, phải chạy lại cả lô (~40 phút).

2. **Đọc ``result.retrieved``, KHÔNG đọc ``result.chunks``** (DEC-049).
   ``chunks`` rỗng ở **mọi** nhánh ABSTAIN — mà nhóm A/B thì LUÔN abstain.
   Đọc nhầm trường thì 30/59 câu ra 0 chunk và bảng **vẫn chạy ra số**.

3. **Hai cơ chế abstain phải tách được** (T4.1, DEC-044):
   policy-ABSTAIN ⇔ có bước ``POLICY`` với ``note`` **khác rỗng**;
   retrieval-ABSTAIN ⇔ bước ``ABSTAIN`` mang ``state="INCORRECT"``.
   Gộp chung thì risk–coverage vẽ sai: nhóm D bị chặn **trước** retrieval nên
   không nằm trên đường hiệu chỉnh, trộn nó vào là pha loãng mẫu số.

4. **Lượt truy hồi ĐẦU biến mất khỏi ``PipelineResult``** khi câu đi qua
   rewrite — ``retrieved`` chỉ mang lượt cuối. Đó là lý do
   :class:`RecordingRetriever` tồn tại; thiếu nó thì mất hạng bài vàng trước
   rewrite, tức mất đúng con số phân biệt "truy hồi hỏng" với "thang điểm
   hỏng" (DEC-051).
"""

from __future__ import annotations

import math

from src.schemas import PipelineResult, RetrievedChunk, TraceStep

# Biên an toàn khi nghịch đảo sigmoid. Xem :func:`logit`.
SIGMOID_EPS = 1e-12

# Hai hành động đều là "hệ thống đã trả lời". Gộp chúng là CỐ Ý: với câu nhóm
# A/B, trả lời kèm cảnh báo vẫn là trả lời một câu lẽ ra phải từ chối — tính
# nó thành "không leakage" là tự chấm điểm cho mình.
ANSWERING_ACTIONS = ("ANSWER", "ANSWER_WITH_CAUTION")


def logit(p: float | None) -> float | None:
    """Nghịch đảo sigmoid — lấy lại logit thô từ chính điểm grader đã dùng.

    **Vì sao suy ngược thay vì chặn lấy logit ở ``BgeReranker.logits()``:**
    con số cần ghi là con số **đã ra quyết định**, tức ``max(c.score)`` mà
    ``Grader.score_of`` đọc. Suy ngược từ chính nó thì không tồn tại đường nào
    để hai số lệch nhau; chặn ở tầng reranker thì có (cắt ``top_k``, sắp lại,
    hoà điểm) và một lệch như vậy sẽ không ai thấy. Thêm nữa: không phải chép
    lại hàm ``sigmoid`` của ``reranker.py`` theo chiều ngược — chép là mở đúng
    loại trôi mà DEC-046 vừa đóng.

    Sai số vòng tròn ~1e-12 trong dải đo được (|logit| ≤ 8 — DEC-039/051), tức
    nhỏ hơn bốn bậc so với độ phân giải mà mọi bảng trong báo cáo dùng
    (3 chữ số thập phân).

    Trả ``None`` ở hai đầu bão hoà thay vì ``±inf``: float64 làm tròn sigmoid
    về đúng 0.0/1.0 khi |logit| ≳ 36 và thông tin mất **thật**, còn một ``inf``
    lọt vào bảng sẽ âm thầm thành ``NaN`` sau phép trừ đầu tiên. ``None`` cũng
    là giá trị đúng cho ngữ cảnh **rỗng**: ``score_of([])`` trả 0.0, và "không
    truy hồi được gì" không phải là "logit bằng âm vô cùng".
    """
    if p is None:
        return None
    if not (SIGMOID_EPS < p < 1.0 - SIGMOID_EPS):
        return None
    return math.log(p / (1.0 - p))


def grade_turns(trace: list[TraceStep]) -> list[dict]:
    """Mỗi bước ``GRADE`` = một lượt truy hồi đã chấm, theo ĐÚNG thứ tự.

    Lấy theo **vị trí**, không lọc theo ``note``: ``note`` là tiếng Việt tự do
    (``"lần truy hồi đầu"`` / ``"sau rewrite"``) do ``pipeline._grade`` truyền
    vào, sửa một chữ ở đó là bộ lọc chuỗi hỏng lặng lẽ. Vị trí thì được
    ``max_iter=1`` (ràng buộc #4) khoá cứng: **1** lượt nếu trả lời ngay,
    **2** lượt nếu đi qua rewrite. ``note`` vẫn được ghi lại để đọc bằng mắt.
    """
    turns: list[dict] = []
    for step in trace:
        if step.step != "GRADE":
            continue
        turns.append(
            {
                "i": len(turns),
                "state": step.state,
                "score": step.score,
                "logit": logit(step.score),
                "note": step.note,
            }
        )
    return turns


def abstain_mechanism(trace: list[TraceStep]) -> str | None:
    """``"policy"`` | ``"retrieval"`` | ``None`` — quy tắc tách của T4.1.

    ``None`` nghĩa là câu này **không** từ chối. Đừng suy ra cơ chế từ sự vắng
    mặt của bước POLICY: bước đó được ghi **kể cả khi không khớp** (``note``
    rỗng), đúng để đếm được "gate đã chạy".
    """
    for step in trace:
        if step.step == "POLICY" and step.note:
            return "policy"
    for step in trace:
        if step.step == "ABSTAIN" and step.state == "INCORRECT":
            return "retrieval"
    return None


def policy_rule(trace: list[TraceStep]) -> str | None:
    """``rule_id`` của rule đã chặn (D-1…D-4), hoặc ``None`` nếu gate không bắt."""
    for step in trace:
        if step.step == "POLICY":
            return step.note or None
    return None


def gold_rank(chunks: list[RetrievedChunk], gold_ids) -> int | None:
    """Hạng (1-based) của **BÀI** vàng đầu tiên trong danh sách đã sắp.

    Hạng theo **bài**, không theo chunk: ``doc_id`` được khử trùng lặp mà vẫn
    giữ thứ tự, nên một bài chiếm 3 chunk ở đầu vẫn chỉ tính là hạng 1. Đây là
    cùng quy ước với cột "hạng bài vàng" ở DEC-039/051/055 — đổi quy ước là
    mọi bảng cũ hết so được.

    ``None`` = bài vàng **không vào pool**. Phân biệt được ``None`` với một
    hạng lớn là điều kiện để tách "truy hồi hỏng" khỏi "thang điểm hỏng".
    """
    if not gold_ids:
        return None
    gold = set(gold_ids)
    seen: list[str] = []
    for c in chunks:
        if c.doc_id not in seen:
            seen.append(c.doc_id)
    for i, doc_id in enumerate(seen, start=1):
        if doc_id in gold:
            return i
    return None


def chunk_json(c: RetrievedChunk, *, with_text: bool = True) -> dict:
    """Một chunk ở dạng JSON. ``with_text=False`` để xem nhanh, không cho eval.

    ⚠️ RAGAS Tuần 6 cần ``text`` (context precision/recall chấm trên nội dung,
    không chấm trên id). Tắt ``with_text`` rồi đem file đi chấm là ra bảng
    toàn 0 mà không lỗi.
    """
    out = {
        "doc_id": c.doc_id,
        "chunk_idx": c.chunk_idx,
        "n_chunks": c.n_chunks,
        "score": c.score,
        "logit": logit(c.score),
        "title": c.title,
        "source": c.source,
        "specialty": c.specialty,
    }
    if with_text:
        out["text"] = c.text
    return out


class RecordingRetriever:
    """Bọc một ``Retriever`` để giữ lại kết quả **từng** lượt truy hồi.

    Chỉ uỷ quyền: không sắp lại, không cắt, không đổi điểm — nên hành vi của
    pipeline không đổi một li. Lý do tồn tại nằm ở mục 4 của docstring module:
    ``PipelineResult.retrieved`` chỉ mang lượt **cuối**.

    Dùng: dựng một lần, gọi :meth:`reset` **trước mỗi câu**.
    """

    def __init__(self, inner) -> None:
        self._inner = inner
        self.turns: list[dict] = []

    def reset(self) -> None:
        """Xoá lịch sử. Quên gọi = lượt của câu trước dính vào câu sau."""
        self.turns = []

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        out = self._inner.retrieve(query)
        self.turns.append({"query": query, "chunks": list(out)})
        return out


def build_record(
    q: dict,
    result: PipelineResult,
    *,
    turns_chunks: list[dict] | None = None,
    invalid_citations: list[str] | None = None,
    with_text: bool = True,
    cost: dict | None = None,
) -> dict:
    """Một dòng JSONL cho hệ thống **corrective** trên một câu hỏi.

    Args:
        q: dòng nguyên văn của ``data/testset.jsonl`` (cần ``id``/``group``/
            ``expected_action``/``reference_context_ids``).
        result: kết quả ``RAGPipeline.answer``.
        turns_chunks: ``RecordingRetriever.turns`` của **đúng câu này**. Để
            ``None`` thì bản ghi vẫn hợp lệ nhưng mất hạng bài vàng của lượt
            đầu — xem mục 4 docstring module.
        invalid_citations: ``gen.last_invalid_citations`` — các ``[n]`` bịa đã
            bị xoá. Chỉ báo hallucination **rẻ**, không cần LLM judge (DEC-045).
        cost: giây/lượt gọi/token của riêng câu này.

    Trường ``leaked``/``refused`` được tính sẵn ở đây thay vì để mỗi bảng tự
    suy: "trả lời" gồm **cả** ``ANSWER_WITH_CAUTION`` (xem
    :data:`ANSWERING_ACTIONS`), và đó là chỗ dễ đếm hụt nhất.
    """
    gold_ids = q.get("reference_context_ids") or []
    turns = grade_turns(result.trace)

    # Ghép hạng bài vàng của TỪNG lượt vào đúng lượt đó. `zip` cắt theo cái
    # ngắn hơn nên lệch số lượt (không truyền `turns_chunks`) là mất dữ liệu
    # chứ không phải gán sai — hỏng nhìn thấy được, không hỏng im lặng.
    if turns_chunks:
        for turn, rec in zip(turns, turns_chunks):
            turn["query"] = rec["query"]
            turn["gold_rank"] = gold_rank(rec["chunks"], gold_ids)
            turn["doc_ids"] = [c.doc_id for c in rec["chunks"]]
            turn["chunks"] = [
                chunk_json(c, with_text=with_text) for c in rec["chunks"]
            ]

    action = result.action.value
    answered = action in ANSWERING_ACTIONS
    expected = q.get("expected_action")

    return {
        "id": q["id"],
        "group": q["group"],
        "system": "corrective",
        "user_input": q["user_input"],
        "expected_action": expected,
        "action": action,
        # Hai lỗi ngược chiều nhau, Tuần 6 phải báo cáo CẢ HAI (kế hoạch T6):
        #   leaked  = trả lời câu lẽ ra phải từ chối  (unsafe answer)
        #   refused = từ chối câu lẽ ra trả lời được  (false refusal)
        "leaked": bool(expected == "ABSTAIN" and answered),
        "refused": bool(expected == "ANSWER" and not answered),
        "abstain_mechanism": abstain_mechanism(result.trace),
        "policy_rule": policy_rule(result.trace),
        "n_turns": len(turns),
        "rewritten": result.rewritten_query is not None,
        "rewritten_query": result.rewritten_query,
        "turns": turns,
        "answer": result.answer,
        "invalid_citations": list(invalid_citations or []),
        # `chunks` = thứ UI được hiện (rỗng khi ABSTAIN).
        # `retrieved` = nguyên văn retriever trả về, thứ Tuần 6 phải chấm.
        # Giữ CẢ HAI để không ai phải nhớ trường nào dùng cho việc gì (DEC-049).
        "n_chunks_shown": len(result.chunks),
        "retrieved": [
            chunk_json(c, with_text=with_text) for c in result.retrieved
        ],
        "reference": q.get("reference"),
        "reference_context_ids": gold_ids,
        "trace_steps": [s.step for s in result.trace],
        "cost": cost or {},
    }


def build_baseline_record(
    q: dict,
    answer: str,
    *,
    cost: dict | None = None,
) -> dict:
    """Một dòng JSONL cho **baseline LLM-only** trên một câu hỏi.

    Cùng khoá ``id`` với bản ghi corrective để Tuần 6 join được, nhưng KHÔNG
    có ``turns``/``retrieved``/``abstain_mechanism``: baseline không truy hồi
    và không có cơ chế từ chối nào. Để trống thay vì điền 0 là cố ý — 0 đọc
    thành "đã đo và bằng không", trống đọc thành "khái niệm này không tồn tại
    ở hệ thống này".

    ``leaked``/``refused`` cũng KHÔNG tính ở đây: quyết định "baseline có từ
    chối hay không" cần đọc văn bản (nó không có ``TerminalAction``), và đoán
    bằng regex là dựng một phép đo giả. Tuần 6 chấm nó bằng RAGAS
    faithfulness — đúng thứ baseline sinh ra để so.
    """
    return {
        "id": q["id"],
        "group": q["group"],
        "system": "baseline_llm_only",
        "user_input": q["user_input"],
        "expected_action": q.get("expected_action"),
        "answer": answer,
        "reference": q.get("reference"),
        "reference_context_ids": q.get("reference_context_ids") or [],
        "cost": cost or {},
    }

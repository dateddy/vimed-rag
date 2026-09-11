"""Faithfulness (RAGAS) + metric truy hồi — việc cuối của Tuần 6.

## Phạm vi: CHỈ Faithfulness đến từ `ragas`

Backlog cũ ghi "RAGAS 4 metric". Thực tế chỉ **một** metric được lấy từ thư
viện, và đó là quyết định có lý do:

* 3 metric không-LLM (``NonLLMContextRecall``,
  ``NonLLMContextPrecisionWithReference``, ``IDBasedContextPrecision``) **trùng
  chức năng** với ``src/eval/retrieval_metrics.py`` đã có sẵn và đã được test
  phủ. Kéo thư viện về để tính lại thứ repo đã tính chính là cái trôi mà repo
  đã phải đi gỡ bốn lần — DEC-044 (regex policy) · DEC-045 (regex byline) ·
  DEC-046 (client LLM) · Session 13 (``stats.py``).
* Thứ ``ragas`` mang lại mà repo **không có**: tách câu trả lời thành từng
  claim nguyên tử rồi NLI từng claim ngược về ngữ cảnh. Tự viết lại phần đó
  mới là thứ đáng bị nghi ngờ.

## ⚠️⚠️ BẪY LỚN NHẤT — FAITHFULNESS TRỪNG PHẠT CÂU TỪ CHỐI ĐÚNG

Đo thật 2026-09-11, không phải suy đoán:

===========  ===============================================  =============
câu          nội dung                                         faithfulness
===========  ===============================================  =============
``E-01``     trả lời thật, có trích dẫn                        **0,70**
``E-21``     *"Ngữ cảnh không chứa thông tin về…"*             **0,00**
===========  ===============================================  =============

Vì sao: RAGAS tách *"ngữ cảnh không chứa thông tin về X"* thành một **phát
biểu siêu ngôn ngữ về ngữ cảnh**, rồi hỏi ngữ cảnh có suy ra được phát biểu ấy
không. Không. Nên câu từ chối — hành vi **đúng** của hệ thống này — nhận điểm
**thấp nhất có thể**.

Hệ quả bắt buộc, đừng bỏ qua:

1. **KHÔNG được lấy trung bình faithfulness trên toàn bộ câu.** Làm thế thì hệ
   càng an toàn điểm càng thấp, và bảng sẽ nói ngược sự thật.
2. Mẫu số đúng là **câu có phát biểu thực chất**. Câu từ chối tách ra, đếm
   riêng, **không** gộp vào trung bình.
3. Đổi lại, ``faithfulness == 0`` trên một bản ghi ``action == "ANSWER"`` là
   một **máy dò B4** (câu mang nhãn ANSWER nhưng nội dung là từ chối) — dùng
   làm đối chứng độc lập cho phép đếm bằng văn bản của :func:`is_refusal_text`.

⚠️ Dự đoán ban đầu của phiên này là câu từ chối sẽ ra ``1.0``/``nan``; **sai
chiều**. Ghi lại vì cái sai đó dẫn tới kết luận ngược hẳn về cách lập bảng.

## ⚠️ Faithfulness đo "bám ngữ cảnh", KHÔNG đo "đúng"

Nhánh corrective phần lớn là từ chối, nên điểm sẽ đẹp vì một lý do chán.
**Đừng để metric này gánh claim "% giảm hallucination"** — repo đã có dụng cụ
tốt hơn hẳn cho việc đó: cờ ``leaked``, ``invalid_citations``, và nhãn tay
6/30 của ``review_static_leaks.py``. Faithfulness là **con số chuẩn hoá để
đối chiếu**, không phải bằng chứng chính.

## Judge: LLM khác họ, đi qua OpenRouter

``FaithfulnesswithHHEM`` bị loại dù nó không tốn lượt API nào: HHEM là
cross-encoder huấn luyện trên **tiếng Anh**, đem chấm tiếng Việt y khoa thì
con số không bảo vệ được. Bẫy "judge cùng họ Gemini với generator" là bẫy
thật, nhưng nó nhỏ hơn bẫy "judge không hiểu ngôn ngữ đang chấm".

DEC-054 (OpenRouter) giải bài toán độc lập judge **miễn phí**: cùng một cổng,
chỉ đổi chuỗi tên model sang một họ không phải ``google/*``. Mặc định
``openai/gpt-5`` — giữ đúng DEC-023 ("OpenAI frontier, temperature=0").

⚠️ ``max_tokens`` phải ĐỦ LỚN. GPT-5 tiêu budget vào reasoning token trước khi
kịp phát JSON; để mặc định thì ``instructor`` ném ``IncompleteOutputException``
— lỗi trông như hỏng schema chứ không như hết token. Xem :data:`JUDGE_MAX_TOKENS`.

## Ràng buộc #2 — không gì nặng chạy lúc import

Module này **không** import ``ragas`` ở cấp module. Judge được **tiêm vào**
(:data:`Judge`), nên toàn bộ test chạy bằng judge giả: không mạng, không API,
không cần ``ragas`` cài trong máy.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from src.eval.answer_content import is_refusal_text
from src.eval.retrieval_metrics import dedup_docs, evaluate

# Một judge nhận (câu hỏi, câu trả lời, các đoạn ngữ cảnh) -> điểm 0..1,
# hoặc **None** nghĩa là "chưa chấm được câu này".
# Kiểu hẹp thế này là cố ý: nó là toàn bộ bề mặt mà `ragas` chạm vào repo.
#
# ⚠️ `None` KHÁC HẲN `0.0`. 0,0 là một phán quyết ("không claim nào được
# chống đỡ"); None là "không có phán quyết". Gộp hai thứ đó lại thì mỗi câu
# chưa chấm được sẽ kéo trung bình xuống như một thất bại — và lô đầu tiên
# CHẾT GIỮA CHỪNG ở 403 sau 28/76 câu, nên đây là tình huống thật, không
# phải giả định.
Judge = Callable[[str, str, list[str]], float | None]

#: Tên model judge mặc định trên OpenRouter. KHÁC họ với generator
#: (`google/gemini-2.5-flash`) — đó là cả mục đích.
DEFAULT_JUDGE_MODEL = "openai/gpt-5"

#: ⚠️ Phải lớn. Model suy luận tiêu token vào reasoning trước khi phát JSON;
#: thiếu budget thì `instructor` ném IncompleteOutputException, đọc như lỗi
#: schema chứ không như hết token. 16k là mức đã chạy thật 2026-09-11.
JUDGE_MAX_TOKENS = 16000

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class FaithRow:
    """Một câu đã được chấm faithfulness."""

    id: str
    group: str
    arm: str
    faithfulness: float
    n_contexts: int
    refusal: bool

    @property
    def substantive(self) -> bool:
        """Có phát biểu thực chất để mà chấm không?"""
        return not self.refusal


@dataclass
class FaithSummary:
    """Tổng hợp một nhánh. **Trung bình chỉ trên câu thực chất.**"""

    arm: str
    rows: list[FaithRow] = field(default_factory=list)
    #: Câu judge trả `None` — chưa chấm được. KHÔNG vào mẫu số nào.
    unscored: list[str] = field(default_factory=list)

    @property
    def substantive(self) -> list[FaithRow]:
        return [r for r in self.rows if r.substantive]

    @property
    def refusals(self) -> list[FaithRow]:
        return [r for r in self.rows if r.refusal]

    @property
    def mean_faithfulness(self) -> float | None:
        """Trung bình trên câu THỰC CHẤT. ``None`` khi không có câu nào.

        ⚠️ Cố ý **không** có thuộc tính "trung bình trên tất cả". Xem cảnh báo
        đầu module: câu từ chối ra 0,0 nên trung bình toàn bộ sẽ phạt đúng
        hành vi mà đề tài này muốn thưởng.
        """
        vals = [r.faithfulness for r in self.substantive]
        return sum(vals) / len(vals) if vals else None

    @property
    def zero_scored_ids(self) -> list[str]:
        """Câu ``faithfulness == 0`` — máy dò B4 độc lập với phép dò văn bản."""
        return [r.id for r in self.rows if r.faithfulness == 0.0]

    def disagreement(self) -> list[str]:
        """Chỗ hai máy dò B4 **không khớp** — phải soi tay, đừng làm ngơ.

        Phép dò văn bản (:func:`is_refusal_text`) và phép dò điểm
        (``faithfulness == 0``) đo hai thứ khác nhau, nên lệch nhau là chuyện
        bình thường: một câu trả lời thật cũng có thể ra 0 vì bịa hoàn toàn.
        Hàm này chỉ **chỉ chỗ**, không phán quyết.
        """
        by_text = {r.id for r in self.refusals}
        by_score = set(self.zero_scored_ids)
        return sorted(by_text ^ by_score)


def score_records(
    records: Sequence[dict],
    judge: Judge,
    *,
    arm: str,
    contexts_by_id: dict[str, list[str]] | None = None,
) -> FaithSummary:
    """Chấm faithfulness cho các bản ghi **đã trả lời** của một nhánh.

    ``contexts_by_id`` để chấm nhánh **LLM-only**: nhánh đó không truy hồi nên
    tự nó không có ngữ cảnh nào. Đưa ngữ cảnh mà nhánh corrective lấy được cho
    *cùng câu hỏi đó* vào, phép đo trở thành *"câu trả lời không-truy-hồi này
    có được chống đỡ bởi bằng chứng tốt nhất corpus đưa ra được không"*.

    ⚠️ Đó là cách dùng **phi tiêu chuẩn** của Faithfulness và báo cáo phải gọi
    tên nó. Không nói ra thì người đọc sẽ hiểu thành hai nhánh được chấm bằng
    cùng một phép đo, mà không phải.
    """
    out = FaithSummary(arm=arm)
    for rec in records:
        ctxs = (
            [c["text"] for c in rec.get("retrieved") or []]
            if contexts_by_id is None
            else contexts_by_id.get(rec["id"], [])
        )
        if not ctxs:
            continue
        answer = rec.get("answer") or ""
        diem = judge(rec["user_input"], answer, ctxs)
        if diem is None:          # chưa chấm được -> KHÔNG phải điểm 0
            out.unscored.append(rec["id"])
            continue
        out.rows.append(
            FaithRow(
                id=rec["id"],
                group=rec.get("group", "?"),
                arm=arm,
                faithfulness=float(diem),
                n_contexts=len(ctxs),
                refusal=is_refusal_text(answer),
            )
        )
    return out


def retrieval_metrics(
    records: Sequence[dict], ks: Sequence[int] = (1, 3, 5, 10)
) -> dict[str, float]:
    """3 metric truy hồi — tính bằng `retrieval_metrics.py`, KHÔNG bằng ragas.

    Chỉ nhóm **E** có ``reference_context_ids``, nên chỉ nhóm E vào được đây.
    Bản ghi thiếu ground truth bị bỏ qua chứ không tính là 0 — tính 0 cho câu
    vốn không có đáp án vàng là bịa ra một thất bại không tồn tại.
    """
    ranked, relevant = [], []
    for rec in records:
        gold = set(rec.get("reference_context_ids") or [])
        if not gold:
            continue
        ranked.append(dedup_docs(c["doc_id"] for c in rec.get("retrieved") or []))
        relevant.append(gold)
    if not ranked:
        return {}
    out = evaluate(ranked, relevant, ks=ks)
    out["n_queries"] = float(len(ranked))
    return out


def make_openrouter_judge(
    api_key: str,
    model: str = DEFAULT_JUDGE_MODEL,
    *,
    max_tokens: int = JUDGE_MAX_TOKENS,
) -> Judge:
    """Dựng judge thật: ragas Faithfulness chạy qua OpenRouter.

    ``ragas``/``openai`` import **bên trong hàm** — ràng buộc #2. Clone chưa
    cài ragas vẫn chạy sạch toàn bộ test, vì test tiêm judge giả.

    ⚠️ ``ragas==0.4.3`` KHÔNG chạy được với ``langchain-community`` 0.4.x: nó
    import ``langchain_community.chat_models.vertexai``, API đã bị gỡ. Pin
    lùi ``langchain-community<0.4`` — lý do ghi trong ``requirements-eval.txt``.
    """
    import asyncio  # noqa: PLC0415 — cố ý: import lười

    from openai import AsyncOpenAI  # noqa: PLC0415
    from ragas.llms import llm_factory  # noqa: PLC0415
    from ragas.metrics.collections import Faithfulness  # noqa: PLC0415

    client = AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)
    llm = llm_factory(
        model,
        provider="openai",
        client=client,
        temperature=0.0,          # DEC-023
        max_tokens=max_tokens,
    )
    metric = Faithfulness(llm=llm)

    def judge(user_input: str, response: str, contexts: list[str]) -> float:
        res = asyncio.run(
            metric.ascore(
                user_input=user_input,
                response=response,
                retrieved_contexts=contexts,
            )
        )
        return float(res.value)

    return judge


def paired_comparison(a: FaithSummary, b: FaithSummary) -> dict:
    """So sánh hai nhánh **trên đúng những câu cả hai đều có điểm**.

    ⚠️⚠️ **ĐỪNG so hai trung bình rời.** Lô đầu chết ở 403 sau 28/76 câu, nên
    nhánh corrective có 16 câu thực chất còn nhánh LLM-only chỉ có 11 — và 11
    câu ấy **không phải tập con ngẫu nhiên**, chúng là ``E-01…E-11``, đúng thứ
    tự file. So ``0,747`` với ``0,463`` khi hai con số đứng trên hai tập câu
    khác nhau là so hai thứ khác nhau rồi gọi đó là hiệu ứng.

    Hàm này cắt về **giao** của hai bên, và chỉ giữ câu **thực chất ở cả hai**
    (câu từ chối không có claim nào để chấm — xem cảnh báo đầu module).

    Trả về ``n`` = cỡ mẫu ghép cặp, hai trung bình trên đúng mẫu đó, ``delta``,
    và ``diffs`` để đẩy sang :func:`src.eval.stats.sign_test` — kiểm định dấu,
    không phải t-test, vì n nhỏ và phân bố không rõ dạng (cùng lý do DEC-055).
    """
    ma = {r.id: r for r in a.substantive}
    mb = {r.id: r for r in b.substantive}
    chung = sorted(set(ma) & set(mb))
    if not chung:
        return {"n": 0, "ids": [], "diffs": [],
                "mean_a": None, "mean_b": None, "delta": None}

    va = [ma[i].faithfulness for i in chung]
    vb = [mb[i].faithfulness for i in chung]
    tba, tbb = sum(va) / len(va), sum(vb) / len(vb)
    return {
        "n": len(chung),
        "ids": chung,
        "diffs": [x - y for x, y in zip(va, vb)],
        "mean_a": tba,
        "mean_b": tbb,
        "delta": tba - tbb,
    }

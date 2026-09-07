"""Interface viết lại truy vấn + FakeRewriter + LLMRewriter (Tuần 4).

``LLMRewriter`` là **lượt gọi LLM thứ hai** của một truy vấn: nó chỉ chạy khi
grader trả INCORRECT, tức chi phí của nó là ``+1 LLM call`` cho đúng những câu
khó nhất. Bảng chi phí Tuần 7 phải tính riêng, không gộp vào một lượt gọi.

Đi lại đúng khuôn của ``GeminiGenerator`` (DEC-045): ``transport`` tiêm được,
SDK nạp lười qua ``src/llm.py``, nên test không chạm mạng và không cần key.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from src.config import GenerationConfig, load_prompt
from src.llm import DEFAULT_MODEL, Transport, gemini_call
from src.schemas import RetrievedChunk

# Truy vấn viết lại dài hơn ngần này = model đã GIẢI THÍCH thay vì viết lại.
# Đo trên test set 59 câu (2026-09-07): dài nhất **181** ký tự, trung vị 63.
# 300 để dư ~1,7 lần câu dài nhất; vượt qua là dấu hiệu hỏng, không phải câu
# hỏi công phu. Tái lập số: xem `data/testset.jsonl`, trường `user_input`.
MAX_REWRITE_CHARS = 300

# Nhãn model hay tự thêm dù prompt bảo "CHỈ trả về truy vấn đã viết lại".
_LABEL_RE = re.compile(
    r"^\s*(truy\s*vấn\s*(đã\s*)?viết\s*lại|rewritten\s*query)\s*[:：]\s*",
    re.I,
)
_BULLET_RE = re.compile(r"^\s*[-*•]\s+")
_QUOTES = "\"'“”‘’`"


@runtime_checkable
class Rewriter(Protocol):
    """Giao diện viết lại query khi context bị đánh giá INCORRECT."""

    def rewrite(self, query: str, chunks: list[RetrievedChunk]) -> str:
        ...


class FakeRewriter:
    """Rewriter giả: thêm hậu tố tất định (không gọi LLM)."""

    def rewrite(self, query: str, chunks: list[RetrievedChunk]) -> str:
        return f"{query} (viết lại)"


def clean_rewritten(raw: str, fallback: str) -> str:
    """Gạn truy vấn sạch từ đầu ra model; hỏng thì trả ``fallback``.

    Prompt đã bảo "CHỈ trả về truy vấn đã viết lại, không giải thích", nhưng
    yêu cầu trong prompt là **mong đợi**, không phải bảo đảm — cùng lý do
    ``ensure_disclaimer`` tồn tại ở tầng generation.

    Bốn kiểu hỏng đã tính tới, theo thứ tự xử lý:

    1. Model thêm nhãn ``TRUY VẤN VIẾT LẠI:`` → cắt nhãn.
    2. Model giải thích ở các dòng sau → chỉ lấy **dòng đầu có chữ**.
    3. Model bọc nháy hoặc gạch đầu dòng → gỡ.
    4. Model viết cả đoạn văn (hoặc trả rỗng) → **trả lại truy vấn gốc**.

    Trường hợp 4 quan trọng hơn vẻ ngoài của nó: truy vấn rác đi vào retriever
    thì lượt truy hồi thứ hai *chắc chắn* hỏng, và ``max_iter=1`` nghĩa là
    không còn cơ hội sửa. Thà lặp lại truy vấn gốc — kết quả xấu nhất khi đó là
    ABSTAIN thật thà, không phải ABSTAIN vì mình tự phá câu hỏi.
    """
    for line in raw.splitlines():
        line = _LABEL_RE.sub("", _BULLET_RE.sub("", line)).strip().strip(_QUOTES)
        line = line.strip()
        if not line:
            continue
        return line if len(line) <= MAX_REWRITE_CHARS else fallback
    return fallback


class LLMRewriter:
    """Rewriter thật: gọi Gemini mở rộng/làm rõ truy vấn.

    ``chunks`` nằm trong chữ ký để hợp ``Rewriter`` Protocol và khớp pseudo-code
    ``q2=rewrite(q,ctx)`` của contract, nhưng **CỐ Ý KHÔNG đi vào prompt**:
    ``config/prompts/query_rewrite.txt`` chỉ có chỗ trống ``{query}``. Đưa ngữ
    cảnh vừa truy hồi hỏng vào đó là mời model bám vào đúng thứ đang sai — nó
    sẽ viết lại theo từ vựng của những bài KHÔNG liên quan (DEC-046). Muốn đổi
    thì đổi prompt trước, và phải đo lại trên nhóm E.

    ``last_fallback`` = lần gọi gần nhất có phải rơi về truy vấn gốc không.
    Tuần 6/7 dùng để biết rewrite thực sự làm việc bao nhiêu phần, thay vì giả
    định nó luôn trả ra câu tử tế.
    """

    def __init__(
        self,
        cfg: GenerationConfig,
        api_key: str,
        model: str = DEFAULT_MODEL,
        transport: Transport | None = None,
    ) -> None:
        # KHÔNG khởi tạo client ở đây — dựng pipeline phải rẻ và không cần mạng.
        self._cfg = cfg
        self._api_key = api_key
        self._model = model
        self._transport = transport
        self.last_fallback = False

    def build_prompt(self, query: str) -> str:
        tpl = load_prompt("query_rewrite")
        if "{query}" not in tpl:
            raise ValueError("Prompt `query_rewrite.txt` thiếu chỗ trống {query}")
        # `.replace` chứ không `.format`: prompt là văn bản người viết, một dấu
        # `{` trong đó không được phép làm nổ vòng corrective.
        return tpl.replace("{query}", query)

    def _default_transport(self, prompt: str, temperature: float) -> str:
        return gemini_call(
            prompt, temperature, api_key=self._api_key, model=self._model
        )

    def rewrite(self, query: str, chunks: list[RetrievedChunk]) -> str:
        transport = self._transport or self._default_transport
        raw = transport(self.build_prompt(query), self._cfg.temperature)
        out = clean_rewritten(raw, fallback=query)
        self.last_fallback = out == query
        return out

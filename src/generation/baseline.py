"""Baseline LLM-only — Gemini trả lời KHÔNG có retrieval.

Đây là **cột so sánh** của claim Tuần 6 ("RAG giảm hallucination bao nhiêu so
với hỏi thẳng LLM"). Không có nó thì con số của hệ thống không có mốc để đo.

⚠️ **BẪY PHƯƠNG PHÁP — đọc trước khi sửa `baseline_llm_only.txt`.**
Baseline phải là một **đối thủ công bằng**, không phải hình nộm. Prompt của nó
giữ nguyên mọi thứ của bản RAG *trừ* ngữ cảnh và trích dẫn: cùng vai trợ lý y
tế, cùng tiếng Việt, cùng yêu cầu miễn trừ, và **vẫn được phép nói "không chắc
chắn"**. Làm baseline yếu đi (bỏ lời mời nói không chắc, ép nó phải trả lời)
thì "% giảm hallucination" tăng lên vì mình đã dàn xếp, không vì hệ thống tốt.
Sai lệch đó không phát hiện được từ bảng kết quả — chỉ đọc prompt mới thấy.

⚠️ **CỐ Ý KHÔNG hợp `Generator` Protocol.** Hàm ở đây là ``answer(query)``, không
phải ``generate(query, chunks, caution)``. Nếu nó hợp Protocol thì cắm nhầm vào
``RAGPipeline`` sẽ ra một hệ thống **trông như RAG trong `trace`** (có bước
RETRIEVE, có GRADE) nhưng generator lặng lẽ vứt hết ngữ cảnh — một baseline giả
dạng hệ thống thật là kiểu hỏng tệ nhất có thể có ở chương kết quả.
"""

from __future__ import annotations

from src.config import GenerationConfig, load_prompt
from src.generation.context import ensure_disclaimer
from src.llm import DEFAULT_MODEL, Transport, gemini_call


class BaselineGenerator:
    """Hỏi thẳng Gemini, không truy hồi, không trích dẫn.

    Cùng khuôn ``transport`` tiêm được của ``GeminiGenerator`` (DEC-045) nên
    test không chạm mạng và không cần API key.
    """

    def __init__(
        self,
        cfg: GenerationConfig,
        api_key: str,
        model: str = DEFAULT_MODEL,
        transport: Transport | None = None,
    ) -> None:
        self._cfg = cfg
        self._api_key = api_key
        self._model = model
        self._transport = transport

    def build_prompt(self, query: str) -> str:
        tpl = load_prompt("baseline_llm_only")
        if "{query}" not in tpl:
            raise ValueError(
                "Prompt `baseline_llm_only.txt` thiếu chỗ trống {query}"
            )
        if "{context}" in tpl:
            raise ValueError(
                "Prompt baseline KHÔNG được có {context} — có ngữ cảnh thì nó "
                "không còn là baseline LLM-only nữa."
            )
        return tpl.replace("{query}", query)

    def _default_transport(self, prompt: str, temperature: float) -> str:
        return gemini_call(
            prompt, temperature, api_key=self._api_key, model=self._model
        )

    def answer(self, query: str) -> str:
        """Trả lời không ngữ cảnh. Chốt disclaimer y như đường RAG.

        Chốt disclaimer ở cả hai nhánh là **cố ý**: nếu chỉ đường RAG có miễn
        trừ thì khác biệt đo được ở Tuần 6 lẫn cả phần "một bên có dòng chữ kia,
        một bên không", chứ không còn thuần là khác biệt về nội dung.
        """
        transport = self._transport or self._default_transport
        return ensure_disclaimer(
            transport(self.build_prompt(query), self._cfg.temperature)
        )

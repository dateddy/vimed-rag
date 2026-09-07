"""Interface sinh câu trả lời + FakeGenerator + GeminiGenerator (Tuần 4).

``GeminiGenerator`` mở khoá ở Tuần 4 nhưng **không** chạm mạng lúc
``__init__``: SDK ``google.genai`` chỉ import **bên trong** hàm và client dựng
lười, y như ``indexer.py``/``retriever.py``. Import module này không gọi API,
không cần key (ràng buộc #2).

Phần thuần (dựng ngữ cảnh, kiểm trích dẫn, chốt disclaimer) nằm ở
``src/generation/context.py`` để test được mà không tốn một lượt API nào; ở đây
chỉ còn ghép prompt, gọi model, và hậu xử lý.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from src.config import GenerationConfig, load_prompt
from src.generation.context import (
    ensure_disclaimer,
    format_context,
    invalid_citations,
    strip_invalid_citations,
)
from src.schemas import RetrievedChunk


@runtime_checkable
class Generator(Protocol):
    """Giao diện sinh câu trả lời bám context, có citation."""

    def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        caution: bool = False,
    ) -> str:
        ...


class FakeGenerator:
    """Generator giả: trả chuỗi template có citation [n] (không gọi LLM)."""

    def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        caution: bool = False,
    ) -> str:
        tag = "[CẢNH BÁO độ chắc chắn thấp] " if caution else ""
        cites = " ".join(f"[{i + 1}]" for i in range(len(chunks)))
        disclaimer = " (Thông tin tham khảo, không thay thế tư vấn bác sĩ.)"
        return f"{tag}Trả lời mẫu cho: {query} {cites}".strip() + disclaimer


class GeminiGenerator:
    """Generator thật dùng ``gemini-2.5-flash`` (SDK ``google-genai``).

    Đường đi: nạp prompt từ ``config/prompts`` → ghép ngữ cảnh đánh số ``[n]``
    (byline đã cắt) → gọi model ở ``temperature`` lấy từ config → hậu xử lý
    thuần (xoá trích dẫn bịa, chốt disclaimer).

    ``transport`` là chỗ tiêm: một callable ``(prompt, temperature) -> str``.
    Để ``None`` thì lần ``generate()`` đầu tiên mới dựng client thật. Test
    truyền transport giả nên **không test nào chạm mạng hay cần API key**.

    ``last_invalid_citations`` giữ các ``[n]`` bịa của lần sinh gần nhất — Tuần 6
    dùng làm chỉ báo hallucination rẻ, không cần LLM judge.
    """

    def __init__(
        self,
        cfg: GenerationConfig,
        api_key: str,
        model: str = "gemini-2.5-flash",
        transport: Callable[[str, float], str] | None = None,
    ) -> None:
        # KHÔNG khởi tạo client ở đây: dựng pipeline phải rẻ và không cần mạng.
        self._cfg = cfg
        self._api_key = api_key
        self._model = model
        self._transport = transport
        self.last_invalid_citations: list[int] = []

    # ------------------------------------------------------------------ #
    # Phần thuần — test được, không tốn API
    # ------------------------------------------------------------------ #
    def build_prompt(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        caution: bool = False,
    ) -> str:
        """Ghép prompt từ file + ngữ cảnh đánh số.

        Bản ``caution`` dùng khi grader trả AMBIGUOUS — nó KHÁC bản thường ở
        chỗ buộc model mở đầu bằng "[Lưu ý: độ chắc chắn thấp]", tức người đọc
        thấy được mức tin cậy chứ không chỉ hệ thống biết.
        """
        name = "generation_caution" if caution else "generation"
        tpl = load_prompt(name)
        for slot in ("{context}", "{query}"):
            if slot not in tpl:
                raise ValueError(f"Prompt `{name}.txt` thiếu chỗ trống {slot}")
        # `.replace` chứ không `.format`: prompt là văn bản người viết, thêm một
        # dấu `{` vào đó không được phép làm nổ đường sinh câu trả lời.
        return tpl.replace("{context}", format_context(chunks)).replace(
            "{query}", query
        )

    def _postprocess(self, answer: str, n_chunks: int) -> str:
        """Xoá trích dẫn bịa rồi chốt disclaimer. Ghi lại số đã xoá."""
        self.last_invalid_citations = invalid_citations(answer, n_chunks)
        return ensure_disclaimer(strip_invalid_citations(answer, n_chunks))

    # ------------------------------------------------------------------ #
    # Phần chạm mạng — nạp lười
    # ------------------------------------------------------------------ #
    def _default_transport(self, prompt: str, temperature: float) -> str:
        """Gọi Gemini thật. Import SDK BÊN TRONG hàm (ràng buộc #2).

        Dùng ``google-genai`` (2.x) chứ không phải ``google-generativeai``
        (đóng băng ở 0.8.6) — DEC-045.
        """
        # Kiểm key TRƯỚC khi import SDK: lỗi cấu hình phải báo được trên máy
        # chưa cài `google-genai` (test chạy sạch trên clone mới, y như
        # FlagEmbedding ở embedder.py).
        if not self._api_key:
            raise RuntimeError(
                "Thiếu GEMINI_API_KEY. `setx` KHÔNG áp cho terminal đang mở — "
                "mở terminal mới sau khi đặt biến."
            )
        from google import genai  # noqa: PLC0415 — cố ý: import lười
        from google.genai import types  # noqa: PLC0415

        client = genai.Client(api_key=self._api_key)
        resp = client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                # Không khai báo tool nào -> tắt hẳn function calling. Không tắt
                # thì SDK in cảnh báo AFC mỗi lượt gọi, làm bẩn log demo Tuần 7.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
        text = resp.text
        if not text:
            # Trả rỗng thường là do safety filter chặn, không phải lỗi mạng —
            # nuốt im lặng thì Tuần 6 đếm nhầm thành "câu trả lời rỗng".
            raise RuntimeError(
                f"Gemini trả về rỗng (có thể bị chặn). "
                f"prompt_feedback={getattr(resp, 'prompt_feedback', None)}"
            )
        return text.strip()

    def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        caution: bool = False,
    ) -> str:
        transport = self._transport or self._default_transport
        raw = transport(
            self.build_prompt(query, chunks, caution), self._cfg.temperature
        )
        return self._postprocess(raw, len(chunks))

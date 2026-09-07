"""Một chỗ duy nhất gọi Gemini — dùng chung cho generation và rewrite.

Vì sao tách ra khỏi ``generator.py``: rewrite (Tuần 4) là **lượt gọi LLM thứ
hai** của cùng một truy vấn. Để mỗi bên tự dựng client thì sửa model, nhiệt độ,
timeout hay tắt safety ở một chỗ mà quên chỗ kia là chuyện thời gian — và hai
lượt gọi trong CÙNG một câu trả lời sẽ chạy theo hai cấu hình khác nhau mà
không gì bắt được. Cùng loại lỗi mà DEC-044 (regex policy) và DEC-045 (regex
byline) đã gỡ; đây là lần thứ ba.

Ràng buộc #2 giữ nguyên: SDK ``google-genai`` import **bên trong hàm**, client
dựng lười, và key kiểm **trước** khi import — nên module này import được trên
máy chưa cài SDK, và test không cần key.
"""

from __future__ import annotations

from typing import Callable

# Chữ ký của mọi transport: (prompt, temperature) -> text.
# `RAGPipeline` không biết gì về nó; chỉ generator/rewriter cầm.
Transport = Callable[[str, float], str]

DEFAULT_MODEL = "gemini-2.5-flash"


def gemini_call(
    prompt: str,
    temperature: float,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    usage_out: dict | None = None,
) -> str:
    """Gọi Gemini một lượt, trả về text đã strip.

    Args:
        prompt: prompt đầy đủ, đã ghép sẵn ngữ cảnh.
        temperature: lấy từ ``config.generation.temperature``, không hard-code.
        api_key: khoá thật; rỗng thì báo lỗi chứ không im lặng trả rỗng.
        model: mặc định ``gemini-2.5-flash`` (khớp ``config/config.yaml``).
        usage_out: nếu truyền dict, hàm ghi vào đó ``prompt_tokens`` /
            ``output_tokens`` / ``total_tokens``. Tuỳ chọn có chủ đích —
            đường chạy thường không cần, còn bảng chi phí Tuần 7 thì cần
            **token thật**, không phải đếm ký tự rồi đoán.

    Raises:
        RuntimeError: thiếu key, hoặc model trả rỗng (thường do safety filter —
            nuốt im lặng thì Tuần 6 đếm nhầm thành "câu trả lời rỗng").
    """
    # Kiểm key TRƯỚC khi import SDK: lỗi cấu hình phải báo được cả trên máy
    # chưa cài `google-genai` (y như FlagEmbedding ở embedder.py).
    if not api_key:
        raise RuntimeError(
            "Thiếu GEMINI_API_KEY. `setx` KHÔNG áp cho terminal đang mở — "
            "mở terminal mới sau khi đặt biến."
        )
    from google import genai  # noqa: PLC0415 — cố ý: import lười
    from google.genai import types  # noqa: PLC0415

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            # Không khai báo tool nào -> tắt hẳn function calling. Không tắt thì
            # SDK in cảnh báo AFC mỗi lượt gọi, làm bẩn log demo Tuần 7.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )
    if usage_out is not None:
        # Ghi TRƯỚC khi kiểm text rỗng: lượt bị safety filter chặn vẫn tính
        # tiền phần prompt, nên bảng chi phí phải thấy được nó.
        um = getattr(resp, "usage_metadata", None)
        usage_out.update(
            prompt_tokens=getattr(um, "prompt_token_count", None),
            output_tokens=getattr(um, "candidates_token_count", None),
            total_tokens=getattr(um, "total_token_count", None),
        )
    text = resp.text
    if not text:
        raise RuntimeError(
            f"Gemini trả về rỗng (có thể bị chặn). "
            f"prompt_feedback={getattr(resp, 'prompt_feedback', None)}"
        )
    return text.strip()


def make_transport(api_key: str, model: str = DEFAULT_MODEL) -> Transport:
    """Đóng gói ``gemini_call`` thành một ``Transport`` để tiêm vào component."""

    def transport(prompt: str, temperature: float) -> str:
        return gemini_call(prompt, temperature, api_key=api_key, model=model)

    return transport

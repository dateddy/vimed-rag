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

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Callable

# src/llm.py -> src -> <repo>
_REPO_ROOT = Path(__file__).resolve().parent.parent
LLM_CACHE_PATH = _REPO_ROOT / "data" / "processed" / "llm_cache.json"

# Chữ ký của mọi transport: (prompt, temperature) -> text.
# `RAGPipeline` không biết gì về nó; chỉ generator/rewriter cầm.
Transport = Callable[[str, float], str]

DEFAULT_MODEL = "google/gemini-2.5-flash"
DEFAULT_PROVIDER = "openrouter"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Timeout mỗi lượt gọi. Đo được 9-14s/lượt trên gemini-2.5-flash (DEC-048), nên
# 120s là rất rộng; nó ở đây để một lượt treo không làm đứng cả lô 59 câu.
HTTP_TIMEOUT_S = 120.0

# ⛔⛔ FREE TIER GEMINI CÓ **HAI** HẠN MỨC — đo 2026-09-08 bằng cách đâm vào cả
# hai (DEC-053). Hạn mức thứ hai mới là thứ chặn dự án:
#
#   GenerateRequestsPerMinutePerProjectPerModel-FreeTier   quotaValue: 5   /phút
#   GenerateRequestsPerDayPerProjectPerModel-FreeTier      quotaValue: 20  /NGÀY
#
# 20 lượt MỖI NGÀY cho `gemini-2.5-flash`. Throttle dưới đây chỉ chữa được hạn
# mức phút; hạn mức ngày thì **không code nào lách được**:
#   - phương án B (21 biến thể)        -> quá một ngày
#   - Tuần 6 (~90 lượt trên 59 câu)    -> ~5 NGÀY
#   - Tuần 7 demo trước hội đồng       -> 20 câu là hết quota
# => Hoặc bật thanh toán, hoặc rải nhiều ngày. Xem `llm_cache` bên dưới: mỗi
#    lần chạy lại script lúc phát triển đang ĂN vào đúng 20 lượt đó.
DEFAULT_RPM = 5

_throttle_lock = threading.Lock()
_last_call_at = 0.0

# 429 (hết quota) và 503 (quá tải) đều là lỗi TẠM THỜI — thử lại được. Mọi mã
# khác (401 sai key, 400 prompt hỏng) thì thử lại chỉ tốn thời gian.
_RETRYABLE = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE",
              "500", "502", "504", "Timeout", "timed out")
MAX_RETRIES = 4


class LlmCache:
    """Cache đĩa cho đáp án LLM, khoá theo (model, temperature, prompt).

    Sinh ra vì hạn mức **20 lượt/ngày**: trong lúc phát triển, mỗi lần chạy lại
    một script là đốt vào đúng cái quota mà Tuần 6 cần. Cùng tinh thần với
    ``LogitCache`` của rerank — thứ đắt thì chạy lại phải gần như free.

    ⚠️ **Tắt mặc định.** Bật nó ở script chạy LÔ (sinh dữ liệu, xuất trace), KHÔNG
    bật ở chỗ đang **đo chi phí**: một lượt cache hit tốn ~0s và sẽ làm bảng
    thời gian/token của Tuần 7 sai hoàn toàn.

    ⚠️ Chỉ ghi cache khi gọi THÀNH CÔNG. Cache một lỗi lại là đóng băng lỗi đó.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, str] = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(model: str, temperature: float, prompt: str) -> str:
        h = hashlib.sha256(
            f"{model}|{temperature}|{prompt}".encode("utf-8")
        ).hexdigest()
        return h[:32]

    def get(self, k: str) -> str | None:
        v = self.data.get(k)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
        return v

    def put(self, k: str, v: str) -> None:
        self.data[k] = v
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False), encoding="utf-8"
        )


def _quota_hint(msg: str) -> str:
    """Gợi ý theo ĐÚNG loại hạn mức. Nhầm loại là ngồi chờ vô ích."""
    if "PerDay" in msg or "quotaValue': '20'" in msg:
        return (
            "⛔ HẾT QUOTA NGÀY (Google AI Studio free = 20 lượt/ngày, DEC-053). "
            "KHÔNG code nào lách được: chờ sang ngày mới, nạp tiền, hoặc dùng "
            "LlmCache."
        )
    if "402" in msg or "credit" in msg.lower():
        return "⛔ HẾT TIỀN TRÊN OPENROUTER — nạp thêm credit."
    return (
        f"Nếu là hạn mức phút thì hạ `generation.requests_per_minute` "
        f"(đang {DEFAULT_RPM})."
    )


def _openrouter_once(
    prompt: str, temperature: float, api_key: str, model: str
) -> tuple[str, dict]:
    """Một lượt gọi OpenRouter (API kiểu OpenAI).

    Dùng ``httpx`` thẳng thay vì SDK ``openai``: httpx đã theo sẵn
    ``qdrant-client`` nên không thêm dependency nào, mà giao thức thì chỉ là một
    lời POST JSON. Import trong hàm để giữ ràng buộc #2.
    """
    import httpx  # noqa: PLC0415 — cố ý: import lười

    r = httpx.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter dùng hai header này để quy công; không bắt buộc.
            "X-Title": "ViMed-RAG",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code != 200:
        # Ném kèm mã số để `_RETRYABLE` và `_quota_hint` nhận ra được.
        raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    if "choices" not in data:
        raise RuntimeError(f"OpenRouter trả về lạ: {str(data)[:300]}")
    text = (data["choices"][0]["message"].get("content") or "").strip()
    u = data.get("usage") or {}
    return text, {
        "prompt_tokens": u.get("prompt_tokens"),
        "output_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
        "cached": False,
    }


def _google_once(
    prompt: str, temperature: float, api_key: str, model: str
) -> tuple[str, dict]:
    """Một lượt gọi Google AI Studio qua SDK ``google-genai``.

    Giữ lại để đảo được quyết định DEC-054 mà không phải viết lại gì.
    """
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
    um = getattr(resp, "usage_metadata", None)
    return (resp.text or "").strip(), {
        "prompt_tokens": getattr(um, "prompt_token_count", None),
        "output_tokens": getattr(um, "candidates_token_count", None),
        "total_tokens": getattr(um, "total_token_count", None),
        "cached": False,
    }


def _throttle(rpm: int) -> None:
    """Giãn các lượt gọi cho đủ thưa. Khoá để nhiều luồng không cùng lách qua."""
    if rpm <= 0:
        return
    interval = 60.0 / rpm
    global _last_call_at
    with _throttle_lock:
        wait = _last_call_at + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


def gemini_call(
    prompt: str,
    temperature: float,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    usage_out: dict | None = None,
    rpm: int = DEFAULT_RPM,
    cache: "LlmCache | None" = None,
    provider: str = DEFAULT_PROVIDER,
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
    # Cache TRƯỚC cả import SDK: một lượt hit thì không cần SDK, không cần mạng,
    # và quan trọng nhất là không ăn vào 20 lượt/ngày.
    ck = None
    if cache is not None:
        ck = cache.key(model, temperature, prompt)
        hit = cache.get(ck)
        if hit is not None:
            if usage_out is not None:
                usage_out.update(
                    prompt_tokens=None, output_tokens=None,
                    total_tokens=None, cached=True,
                )
            return hit

    call = _openrouter_once if provider == "openrouter" else _google_once
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        _throttle(rpm)
        try:
            out, usage = call(prompt, temperature, api_key, model)
            break
        except Exception as exc:  # noqa: BLE001 — phân loại theo nội dung lỗi
            last = exc
            msg = str(exc)
            if not any(tag in msg for tag in _RETRYABLE):
                raise
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"LLM vẫn lỗi sau {MAX_RETRIES} lần thử "
                    f"({provider}/{model}). {_quota_hint(msg)} "
                    f"Lỗi gốc: {msg[:200]}"
                ) from exc
            # Lùi theo cấp số nhân. Không đọc `retryDelay` của server: nó chỉ
            # nói về quota phút hiện tại, còn 503 thì không có trường đó.
            time.sleep(2.0 * (2 ** attempt))
    else:  # pragma: no cover — vòng lặp luôn break hoặc raise
        raise RuntimeError("không tới được") from last

    if usage_out is not None:
        usage_out.update(usage)
    if not out:
        raise RuntimeError(
            f"LLM trả về rỗng ({provider}/{model}) — thường do safety filter "
            f"chặn. Nuốt im lặng thì Tuần 6 đếm nhầm thành 'câu trả lời rỗng'."
        )
    if cache is not None and ck is not None:
        cache.put(ck, out)   # chỉ ghi khi THÀNH CÔNG
    return out


def make_transport(
    api_key: str,
    model: str = DEFAULT_MODEL,
    rpm: int = DEFAULT_RPM,
    cache: LlmCache | None = None,
    provider: str = DEFAULT_PROVIDER,
) -> Transport:
    """Đóng gói ``gemini_call`` thành một ``Transport`` để tiêm vào component.

    Truyền ``cache`` ở script chạy LÔ; để ``None`` ở chỗ đang đo chi phí.
    """

    def transport(prompt: str, temperature: float) -> str:
        return gemini_call(
            prompt, temperature, api_key=api_key, model=model, rpm=rpm,
            cache=cache, provider=provider,
        )

    return transport


def transport_from_config(cfg, api_key: str, cache: LlmCache | None = None):
    """Dựng ``Transport`` từ ``AppConfig`` — MỘT chỗ đọc provider/model/rpm.

    Tồn tại để script không phải tự nhớ ghép 4 tham số; quên `provider` là
    lặng lẽ gọi nhầm cổng và nhận 404 khó hiểu (DEC-054).
    """
    return make_transport(
        api_key,
        model=cfg.models.llm,
        rpm=cfg.generation.requests_per_minute,
        cache=cache,
        provider=cfg.models.llm_provider,
    )

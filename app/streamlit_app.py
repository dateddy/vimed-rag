"""Streamlit demo cho ViMed-RAG — C3 (Tuần 7).

BA TAB, có chủ đích tách rời:

1. **Hỏi đáp (hệ đầy đủ)** — `RAGPipeline` chạy **đầu-cuối thật**: policy gate
   → truy hồi hybrid → rerank → grader → (rewrite → guard) → generator. Đây là
   hệ được đo ở Tuần 6, và là thứ đem đi demo.
2. **Truy hồi thật** — chỉ `HybridRetriever` + `BgeReranker`, **dừng ở truy
   hồi**. Công cụ soi: xem chunk thô + score trước khi grader phán quyết. Cho
   đổi mode/size vì nó không chạy grader.
3. **Corrective loop (Fake)** — `FakeRetriever` + `FakeGenerator`, score kéo
   bằng slider. Xem 3 nhánh mà không tốn lượt API nào.

## Điều kiện DEC-039 đặt ra đã được thoả

Bản Tuần 3 viết: *"KHÔNG nối retriever thật vào `RAGPipeline` — ngưỡng `0.6` đã
bị bác bỏ"*. Chuỗi gỡ nó, đừng trích gộp:

* **DEC-051** hiệu chỉnh ngưỡng bằng LOOCV → `+2,430 logit = sigmoid 0,919`.
* **DEC-052** đóng hai số vào `config.yaml` (`incorrect 0.919`/`correct 0.933`).
* **DEC-061** thêm guard lượt 2 → leakage **0/30**, coverage **17/21** giữ nguyên.

## ⛔ Quyết định hiển thị nằm ở `app/display.py`, KHÔNG ở file này

Lỗi B3 — câu `action=ANSWER` hiện 5 nguồn cạnh một câu nói *"ngữ cảnh không
chứa thông tin"* (`E-21`) — được vá bằng `nen_hien_nguon()`, có **22 test
khoá cả hai chiều**. File Streamlit **không có test nào chạm tới**, nên mọi
điều kiện hiển thị phải sống ở `display.py`; viết lại điều kiện tại đây là
đúng cách bản vá trôi mất (ISSUE-071 · 073 · 074 đều cùng hình dạng đó).

Tương tự, mọi chỗ in nội dung chunk phải đi qua `doc_nguon()` (= `strip_byline`):
corpus trong Qdrant **vẫn còn byline** (DEC-020) và đường đọc không có tầng nào
cắt hộ.

CHẠY:
    streamlit run app/streamlit_app.py

Tab 1 cần `.env` (QDRANT_URL + QDRANT_API_KEY + **GEMINI_API_KEY**, biến này
mang khoá OpenRouter — tên là lịch sử) và model bge-m3 + reranker đã cache
(~4,5 GB). Tab 2 không cần khoá LLM. Tab 3 chạy được không cần gì.

⚠️ Trên HF Space, `GEMINI_API_KEY` phải được thêm vào **Secrets** — Space hiện
chỉ có `QDRANT_URL` + `QDRANT_API_KEY` (DEPLOY.md bước 2), đủ cho tab 2 nhưng
**không** đủ cho tab 1.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Cho phép chạy trực tiếp bằng `streamlit run` (thêm gốc repo vào sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from app.display import doc_nguon, ly_do_an_nguon, nen_hien_nguon  # noqa: E402
from src.config import load_config  # noqa: E402
from src.generation.generator import FakeGenerator  # noqa: E402
from src.pipeline.grader import Grader  # noqa: E402
from src.pipeline.pipeline import RAGPipeline  # noqa: E402
from src.pipeline.rewriter import FakeRewriter  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402
from src.retrieval.reranker import sigmoid  # noqa: E402  (thuần Python, không kéo torch)
from src.retrieval.retriever import RETRIEVAL_MODES, FakeRetriever  # noqa: E402

# ⚠️ HẰNG SỐ NÀY ĐÃ LỖI THỜI — giữ lại CHỈ để giải thích vì sao nó từng tồn tại.
#
# 2.63 là điểm giữa dải an toàn đo ở DEC-042, hồi ngưỡng còn CHƯA hiệu chỉnh.
# Nay ngưỡng thật nằm trong `config/config.yaml` (DEC-051/052) và mọi chỗ trong
# file này phải đọc `cfg.grader.*`, KHÔNG đọc hằng số ở đây.
#
# ⛔ Đừng dùng nó để hiển thị bất cứ con số nào cho người xem: một demo in ra
# ngưỡng khác với ngưỡng hệ đang chạy là demo mô tả sai chính nó.
SAFE_LOGIT_HINT = 2.63  # noqa: F401 — lịch sử, xem cảnh báo trên


# --------------------------------------------------------------------------- #
# Thành phần thật — nạp LƯỜI và cache, để tab Fake không phải chờ 30s
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Nạp bge-m3 + reranker (~30s, chỉ lần đầu)…")
def _real_parts():
    """Embedder + reranker + client Qdrant. Chỉ gọi khi tab 1 thật sự cần."""
    import torch
    from qdrant_client import QdrantClient

    from src.retrieval.embedder import BgeM3Embedder
    from src.retrieval.reranker import BgeReranker

    cfg = load_config()
    fp16 = bool(cfg.index.use_fp16 and torch.cuda.is_available())

    embedder = BgeM3Embedder(cfg.models, cfg.index, use_fp16=fp16)
    embedder.embed_hybrid(["khởi động"])  # nạp weight ngay, đừng để lần hỏi đầu gánh

    reranker = BgeReranker(
        cfg.models, use_fp16=fp16, max_length=cfg.retrieval.rerank_max_length
    )
    client = QdrantClient(
        url=cfg.qdrant.url, api_key=cfg.qdrant.api_key or None, timeout=60
    )
    return embedder, reranker, client


def _grader_verdict(cfg, score: float) -> tuple[str, str]:
    """Grader SẼ nói gì với score này, theo ĐÚNG ngưỡng trong `config.yaml`.

    Đọc `cfg.grader.*` chứ không hằng số tại chỗ: ngưỡng đã hiệu chỉnh bằng
    LOOCV (DEC-051) và đóng vào config ở DEC-052. Một demo in ra con số khác
    với con số hệ đang chạy là demo mô tả sai chính nó.
    """
    g = cfg.grader
    if score >= g.correct_threshold:
        return "CORRECT", "🟢"
    if score < g.incorrect_threshold:
        return "INCORRECT", "🔴"
    return "AMBIGUOUS", "🟡"


# --------------------------------------------------------------------------- #
# Tab đầu-cuối — hệ THẬT (C3 + B3, Tuần 7)
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Dựng pipeline đầu-cuối…")
def _pipeline(_api_key: str):
    """`RAGPipeline` thật. Nối dây theo đúng `scripts/export_runs.py:203-228`.

    **Bỏ `RecordingRetriever`** so với script đó: nó chỉ tồn tại để giữ điểm
    lượt truy hồi ĐẦU cho LOOCV, thứ UI không dùng tới.

    Tham số tên `_api_key` (gạch dưới) để Streamlit **không** đưa khoá vào khoá
    cache — `st.cache_resource` bỏ qua tham số bắt đầu bằng `_`.
    """
    from src.generation.generator import GeminiGenerator
    from src.pipeline.rewriter import LLMRewriter
    from src.retrieval.retriever import HybridRetriever

    cfg = load_config()
    embedder, reranker, client = _real_parts()

    # ⚠️ KHÔNG nhận mode/size từ người dùng — xem caption trong `tab_e2e`.
    retr = HybridRetriever(
        cfg,
        embedder,
        collection=collection_name(cfg.qdrant.collection, cfg.chunking.size),
        mode="hybrid",
        reranker=reranker,
        client=client,
    )
    return RAGPipeline(
        cfg=cfg,
        retriever=retr,
        generator=GeminiGenerator(cfg.generation, _api_key, model=cfg.models.llm),
        grader=Grader(cfg.grader),
        rewriter=LLMRewriter(cfg.generation, _api_key, model=cfg.models.llm),
    )


#: Nhãn + màu cho từng `TerminalAction`. ABSTAIN KHÔNG dùng màu đỏ: từ chối
#: đúng là hệ thống **làm việc**, không phải hệ thống hỏng. Tô đỏ nó là tự bôi
#: xấu đúng trục đóng góp của đề tài.
_BADGE = {
    "ANSWER": ("🟢", "Trả lời", "success"),
    "ANSWER_WITH_CAUTION": ("🟡", "Trả lời KÈM CẢNH BÁO", "warning"),
    "ABSTAIN": ("🔵", "Từ chối có hiệu chỉnh", "info"),
}


def tab_e2e(cfg) -> None:
    st.caption(
        "**Hệ đầy đủ**: policy gate → truy hồi hybrid → rerank → grader → "
        "(rewrite → guard) → sinh câu trả lời có trích dẫn. Đây là thứ được đo "
        "ở Tuần 6."
    )
    st.markdown(
        f"Cấu hình **cố định** `hybrid` · chunk `{cfg.chunking.size}` · "
        f"`top_k_dense={cfg.retrieval.top_k_dense}` · "
        f"`rerank_max_length={cfg.retrieval.rerank_max_length}` · ngưỡng "
        f"`{cfg.grader.incorrect_threshold}`/`{cfg.grader.correct_threshold}`.\n\n"
        "⚠️ Tab này **cố ý không cho đổi chế độ truy hồi** — khác tab *Truy hồi "
        "thật*. Ngưỡng grader chỉ được hiệu chỉnh cho **đúng một** cấu hình "
        "(LOOCV trên 51 câu, DEC-051); chạy grader ở cấu hình khác là để demo "
        "mô tả sai chính nó."
    )

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error(
            "Thiếu `GEMINI_API_KEY` (biến này mang khoá **OpenRouter** — tên là "
            "lịch sử). Local: đặt trong `.env`. Trên HF Space: thêm vào "
            "**Secrets**, xem `deploy/hf-space/DEPLOY.md` bước 2."
        )
        return

    query = st.text_input(
        "Câu hỏi:", "Biến chứng loét chân ở bệnh nhân tiểu đường?", key="q_e2e"
    )
    if not (st.button("Hỏi", type="primary", key="b_e2e") and query.strip()):
        return

    try:
        pipe = _pipeline(api_key)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Không dựng được pipeline: {exc}")
        return

    t0 = time.perf_counter()
    try:
        with st.spinner("Đang chạy corrective loop… (rerank trên CPU nên chậm)"):
            kq = pipe.answer(query)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Pipeline lỗi: {exc}")
        st.warning(
            "**TCP mở mà TLS reset = cluster Qdrant free tier đang NGỦ**, không "
            "phải lỗi `.env`/DNS/firewall. Vào console bấm resume.\n\n"
            "Lỗi **402/403** = hết credit OpenRouter, không phải lỗi khoá."
        )
        return
    took = time.perf_counter() - t0

    icon, nhan, kieu = _BADGE.get(kq.action.value, ("⚪", kq.action.value, "info"))
    c1, c2 = st.columns([3, 1])
    getattr(c1, kieu)(f"{icon} **{nhan}** · `action = {kq.action.value}`")
    c2.metric("Thời gian", f"{took:.1f}s")

    st.markdown("### Câu trả lời")
    st.write(kq.answer)

    if kq.rewritten_query:
        st.caption(f"🔁 Truy vấn đã viết lại: *{kq.rewritten_query}*")

    # ----------------------------------------------------------------- #
    # Khối nguồn — CHỖ VÁ B3.
    # Quyết định nằm ở `app/display.py`, có 22 test khoá. KHÔNG viết lại
    # điều kiện tại đây: đó đúng là cách bản vá trôi mất.
    # ----------------------------------------------------------------- #
    if nen_hien_nguon(kq):
        st.markdown(f"### Nguồn ({len(kq.chunks)})")
        for i, c in enumerate(kq.chunks, 1):
            pos = f"đoạn {c.chunk_idx}/{c.n_chunks}" if c.chunk_idx is not None else ""
            with st.expander(
                f"[{i}] {c.score:.4f} · {c.title or '(không tiêu đề)'} · {pos}",
                expanded=i == 1,
            ):
                st.caption(
                    f"`doc_id={c.doc_id}` · khoa: {', '.join(c.specialties) or '—'} "
                    f"· nguồn: {c.source or '—'}"
                )
                st.write(doc_nguon(c))
    else:
        st.info(f"**Không hiển thị nguồn.** {ly_do_an_nguon(kq)}")

    with st.expander("🔬 Trace — đường đi thật của corrective loop", expanded=False):
        st.caption(
            "Đây là trục đóng góp của đề tài: mỗi bước ghi lại được, nên "
            "abstention **kiểm chứng được** thay vì phải tin."
        )
        for i, b in enumerate(kq.trace, 1):
            phan = [f"**{i}. {b.step}**"]
            if b.state:
                phan.append(f"`{b.state}`")
            if b.score is not None:
                phan.append(f"score `{b.score:.4f}`")
            if b.note:
                phan.append(f"— {b.note}")
            st.markdown(" · ".join(phan))


# --------------------------------------------------------------------------- #
# Tab 2 — truy hồi thật (không sinh câu trả lời)
# --------------------------------------------------------------------------- #
def tab_real(cfg) -> None:
    st.caption(
        "`HybridRetriever` + `BgeReranker` chạy thật trên Qdrant Cloud. "
        "⚠️ Đây là **truy hồi**, KHÔNG phải hệ đầy đủ: chưa có policy gate, "
        "chưa sinh câu trả lời, chưa có vòng corrective. Tab đầu-cuối là "
        "việc C3 của Tuần 7."
    )

    c1, c2, c3 = st.columns(3)
    mode = c1.selectbox("Chế độ", RETRIEVAL_MODES, index=0)
    size = c2.selectbox("Chunk size", cfg.index.sizes, index=cfg.index.sizes.index(cfg.chunking.size))
    use_rr = c3.checkbox("Bật rerank", value=True)

    st.markdown(
        f"`top_k_dense={cfg.retrieval.top_k_dense}` → rerank → "
        f"`top_k_rerank={cfg.retrieval.top_k_rerank}` · "
        f"`rerank_max_length={cfg.retrieval.rerank_max_length}` "
        f"(cấu hình chi phí Tuần 7 — DEC-042. ⚠️ `17,2s` là số **dự tính**; "
        f"số ĐO được trên hệ đầy đủ là **~45s** nhánh từ chối · **~27s** "
        f"nhánh trả lời — nhánh an toàn đắt hơn)"
    )

    query = st.text_input("Câu hỏi:", "Triệu chứng tăng huyết áp?", key="q_real")
    if not (st.button("Truy hồi", type="primary", key="b_real") and query.strip()):
        return

    from src.retrieval.retriever import HybridRetriever

    try:
        embedder, reranker, client = _real_parts()
    except Exception as exc:  # noqa: BLE001 — hiện lỗi thân thiện thay vì traceback
        st.error(f"Không nạp được thành phần thật: {exc}")
        return

    retr = HybridRetriever(
        cfg,
        embedder,
        collection=collection_name(cfg.qdrant.collection, size),
        mode=mode,
        reranker=reranker if use_rr else None,
        client=client,
    )

    t0 = time.perf_counter()
    try:
        with st.spinner("Đang truy hồi… (rerank chạy trên CPU nên chậm)"):
            chunks = (
                retr.retrieve(query)
                if retr.scores_are_rerank
                else retr.search(query, limit=cfg.retrieval.top_k_rerank)
            )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Truy hồi lỗi: {exc}")
        st.warning(
            "**TCP mở mà TLS reset = cluster Qdrant free tier đang NGỦ**, không "
            "phải lỗi `.env`/DNS/firewall. Vào Qdrant Cloud console bấm resume. "
            "Xem mục Blocker trong `brain/state/STATUS.md`."
        )
        return
    took = time.perf_counter() - t0

    if not chunks:
        st.warning("Không có kết quả.")
        return

    top = max(c.score for c in chunks)
    if retr.scores_are_rerank:
        state, badge = _grader_verdict(cfg, top)
        st.metric("Thời gian", f"{took:.1f}s", help="Rerank chiếm ~99%")
        st.info(
            f"{badge} Grader SẼ trả **{state}** — score cao nhất `{top:.4f}`, "
            f"ngưỡng CORRECT ≥ `{cfg.grader.correct_threshold}` / INCORRECT < "
            f"`{cfg.grader.incorrect_threshold}` (`config/config.yaml`).\n\n"
            f"✅ Ngưỡng này **đã được hiệu chỉnh bằng LOOCV** trên 51 câu "
            f"(DEC-051): coverage **17/21 = 81%** (CI Wilson 60–92%), leakage "
            f"**0/30** (CI Wilson 0–11%) sau guard lượt 2 (DEC-061).\n\n"
            f"⚠️ *SẼ trả* chứ không phải *đã trả*: tab này dừng ở *truy hồi*, "
            f"chưa chạy policy gate lẫn vòng corrective."
        )
    else:
        st.metric("Thời gian", f"{took:.1f}s")
        st.warning(
            "Chưa bật rerank → `score` là RRF/cosine thô, **không cùng thang** với "
            "ngưỡng grader (DEC-033). Đừng so."
        )

    for i, c in enumerate(chunks, 1):
        pos = f"đoạn {c.chunk_idx}/{c.n_chunks}" if c.chunk_idx is not None else ""
        with st.expander(
            f"[{i}] {c.score:.4f} · {c.title or '(không tiêu đề)'} · {pos}", expanded=i == 1
        ):
            st.caption(
                f"`doc_id={c.doc_id}` · khoa: {', '.join(c.specialties) or '—'} "
                f"· nguồn: {c.source or '—'}"
            )
            # `doc_nguon` = strip_byline. Corpus trong Qdrant VẪN còn byline
            # (DEC-020), và không có tầng nào cắt hộ ở đường đọc — chỗ duy nhất
            # đang cắt là `generation/context.py`, tức LLM không thấy byline
            # nhưng MÀN HÌNH thì có. Đừng đổi lại thành `c.text`.
            st.write(doc_nguon(c))


# --------------------------------------------------------------------------- #
# Tab 2 — corrective loop bằng Fake (giữ nguyên demo cũ)
# --------------------------------------------------------------------------- #
def tab_fake(cfg) -> None:
    st.caption(
        "Fake components — không gọi model/API thật. Kéo slider để xem 3 nhánh "
        "của corrective loop."
    )
    c1, c2 = st.columns(2)
    score1 = c1.slider("Score truy hồi lần 1", 0.0, 1.0, 0.9, 0.05)
    score2 = c2.slider("Score sau rewrite", 0.0, 1.0, 0.9, 0.05)
    st.markdown(
        f"Ngưỡng grader: CORRECT ≥ **{cfg.grader.correct_threshold}**, "
        f"INCORRECT < **{cfg.grader.incorrect_threshold}** (`config/config.yaml`)"
    )

    query = st.text_input("Câu hỏi:", "Huyết áp cao nên ăn uống thế nào?", key="q_fake")
    if not (st.button("Hỏi", type="primary", key="b_fake") and query.strip()):
        return

    result = RAGPipeline(
        cfg=cfg,
        retriever=FakeRetriever(scores=[score1, score2]),
        generator=FakeGenerator(),
        grader=Grader(cfg.grader),
        rewriter=FakeRewriter(),
    ).answer(query)

    badge = {"ANSWER": "🟢", "ANSWER_WITH_CAUTION": "🟡", "ABSTAIN": "🔴"}.get(
        result.action.value, "⚪"
    )
    st.subheader(f"{badge} Hành động: {result.action.value}")
    st.write(result.answer)

    if result.rewritten_query:
        st.info(f"Truy vấn đã viết lại: `{result.rewritten_query}`")

    st.markdown("**Trace (corrective loop):**")
    st.table(
        [
            {
                "step": s.step,
                "state": s.state or "",
                "score": "" if s.score is None else round(s.score, 3),
                "note": s.note,
            }
            for s in result.trace
        ]
    )


# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title="ViMed-RAG", page_icon="🩺", layout="wide")
    st.title("🩺 ViMed-RAG — Hỏi đáp y tế tiếng Việt")

    cfg = load_config()
    # Tab đầu-cuối đứng ĐẦU: nó là hệ thật, hai tab kia là công cụ soi.
    t0, t1, t2 = st.tabs(
        ["🩺 Hỏi đáp (hệ đầy đủ)", "🔎 Truy hồi thật", "🧪 Corrective loop (Fake)"]
    )
    with t0:
        tab_e2e(cfg)
    with t1:
        tab_real(cfg)
    with t2:
        tab_fake(cfg)

    st.divider()
    st.caption(
        "⚠️ Hệ thống nghiên cứu, KHÔNG thay thế tư vấn y tế. Nhãn abstention "
        "theo khả năng truy xuất + policy, KHÔNG theo đánh giá lâm sàng; "
        "chưa có reviewer y khoa."
    )


if __name__ == "__main__":
    main()

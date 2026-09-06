"""Streamlit demo cho ViMed-RAG — T3.6.

HAI TAB, có chủ đích tách rời:

1. **Truy hồi thật** — `HybridRetriever` + `BgeReranker` trên Qdrant Cloud.
   Đây là phần T3.6 mở khoá, và cũng đóng nốt DoD Tuần 2 ("UI hiển thị được
   raw chunk") vốn treo từ Session 5 vì lúc đó chưa có retriever.

2. **Corrective loop (Fake)** — giữ nguyên demo cũ, score điều khiển bằng
   slider để xem 3 nhánh ANSWER / CAUTION / ABSTAIN.

⛔ **Vì sao KHÔNG nối retriever thật vào `RAGPipeline`** — DEC-039. Ngưỡng
`grader.correct_threshold = 0.6` đã được đo và **bác bỏ**: ở ngưỡng đó
**10/30 câu nhóm A/B (corpus không có tài liệu) vẫn được TRẢ LỜI**. Nối vào
là dựng một demo trông chạy tốt nhưng trả lời cả những câu đáng lẽ phải từ
chối — đúng thứ mà cả đề tài đang cố chứng minh là mình không làm. Tab 1 vì
thế chỉ hiển thị **truy hồi + điểm rerank**, và ghi rõ grader SẼ nói gì kèm
cảnh báo là ngưỡng chưa hiệu chỉnh.

CHẠY:
    streamlit run app/streamlit_app.py

Tab 1 cần `.env` (QDRANT_URL + QDRANT_API_KEY) và model bge-m3 + reranker đã
cache (~4,5 GB). Tab 2 chạy được không cần gì.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Cho phép chạy trực tiếp bằng `streamlit run` (thêm gốc repo vào sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from src.config import load_config  # noqa: E402
from src.generation.generator import FakeGenerator  # noqa: E402
from src.pipeline.grader import Grader  # noqa: E402
from src.pipeline.pipeline import RAGPipeline  # noqa: E402
from src.pipeline.rewriter import FakeRewriter  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402
from src.retrieval.reranker import sigmoid  # noqa: E402  (thuần Python, không kéo torch)
from src.retrieval.retriever import RETRIEVAL_MODES, FakeRetriever  # noqa: E402

# Điểm giữa DẢI AN TOÀN đo ở đúng cấu hình triển khai (DEC-042):
# A/B cao nhất +2.15 · E thứ 9 +3.12 -> dải (+2.15, +3.12], 0/30 câu A/B lọt lưới.
# CHƯA phải ngưỡng chính thức — chốt ở Tuần 6, bắt buộc có tập giữ lại (DEC-039).
SAFE_LOGIT_HINT = 2.63


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
    """Grader SẼ nói gì với score này — chỉ để tham khảo, xem DEC-039."""
    g = cfg.grader
    if score >= g.correct_threshold:
        return "CORRECT", "🟢"
    if score < g.incorrect_threshold:
        return "INCORRECT", "🔴"
    return "AMBIGUOUS", "🟡"


# --------------------------------------------------------------------------- #
# Tab 1 — truy hồi thật
# --------------------------------------------------------------------------- #
def tab_real(cfg) -> None:
    st.caption(
        "`HybridRetriever` + `BgeReranker` chạy thật trên Qdrant Cloud. "
        "Đây là **truy hồi**, chưa phải sinh câu trả lời (Tuần 4)."
    )

    c1, c2, c3 = st.columns(3)
    mode = c1.selectbox("Chế độ", RETRIEVAL_MODES, index=0)
    size = c2.selectbox("Chunk size", cfg.index.sizes, index=cfg.index.sizes.index(cfg.chunking.size))
    use_rr = c3.checkbox("Bật rerank", value=True)

    st.markdown(
        f"`top_k_dense={cfg.retrieval.top_k_dense}` → rerank → "
        f"`top_k_rerank={cfg.retrieval.top_k_rerank}` · "
        f"`rerank_max_length={cfg.retrieval.rerank_max_length}` "
        f"(cấu hình chi phí Tuần 7 — DEC-042, ~17s/truy vấn trên CPU)"
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
            f"{badge} Grader SẼ trả **{state}** (score cao nhất `{top:.4f}` so với "
            f"CORRECT ≥ `{cfg.grader.correct_threshold}`).\n\n"
            f"⛔ **Đừng tin con số này.** Ngưỡng `0.6` đã bị bác bỏ bằng dữ liệu "
            f"(DEC-039): ở ngưỡng đó **10/30 câu nhóm A/B vẫn được trả lời**. "
            f"Mép an toàn đo được nằm quanh sigmoid "
            f"**{sigmoid(SAFE_LOGIT_HINT):.3f}**. Ngưỡng chính "
            f"thức chốt ở Tuần 6, bắt buộc có tập giữ lại."
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
            st.write(c.text)


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
    t1, t2 = st.tabs(["🔎 Truy hồi thật", "🧪 Corrective loop (Fake)"])
    with t1:
        tab_real(cfg)
    with t2:
        tab_fake(cfg)

    st.divider()
    st.caption(
        "⚠️ Hệ thống nghiên cứu, KHÔNG thay thế tư vấn y tế. "
        "Chưa có sinh câu trả lời (Tuần 4) và chưa hiệu chỉnh ngưỡng (Tuần 6)."
    )


if __name__ == "__main__":
    main()

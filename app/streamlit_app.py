"""Streamlit demo cho ViMed-RAG (chạy bằng Fake components).

Chạy được KHÔNG cần API key / Qdrant / GPU:
    streamlit run app/streamlit_app.py

Hiển thị: câu trả lời (FakeGenerator), hành động cuối (ANSWER/CAUTION/ABSTAIN),
và bảng trace của corrective loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Cho phép chạy trực tiếp bằng `streamlit run` (thêm gốc repo vào sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from src.config import load_config  # noqa: E402
from src.generation.generator import FakeGenerator  # noqa: E402
from src.pipeline.grader import Grader  # noqa: E402
from src.pipeline.pipeline import RAGPipeline  # noqa: E402
from src.pipeline.rewriter import FakeRewriter  # noqa: E402
from src.retrieval.retriever import FakeRetriever  # noqa: E402


@st.cache_resource
def _build_pipeline() -> RAGPipeline:
    """Dựng pipeline demo với Fake components (score điều khiển bằng sidebar)."""
    cfg = load_config()
    return RAGPipeline(
        cfg=cfg,
        retriever=FakeRetriever(),  # sẽ được thay theo score demo bên dưới
        generator=FakeGenerator(),
        grader=Grader(cfg.grader),
        rewriter=FakeRewriter(),
    )


def main() -> None:
    st.set_page_config(page_title="ViMed-RAG (demo)", page_icon="🩺")
    st.title("🩺 ViMed-RAG — Hỏi đáp y tế tiếng Việt")
    st.caption(
        "DEMO chạy bằng Fake components — không gọi model/API thật. "
        "Corrective RAG + calibrated abstention."
    )

    cfg = load_config()

    with st.sidebar:
        st.header("Điều khiển demo")
        st.write("Mô phỏng rerank score để thử các nhánh của corrective loop.")
        score1 = st.slider("Score truy hồi lần 1", 0.0, 1.0, 0.9, 0.05)
        score2 = st.slider("Score truy hồi lần 2 (sau rewrite)", 0.0, 1.0, 0.9, 0.05)
        st.markdown(
            f"Ngưỡng grader: CORRECT ≥ **{cfg.grader.correct_threshold}**, "
            f"INCORRECT < **{cfg.grader.incorrect_threshold}** "
            f"(nguồn: `config/config.yaml`)"
        )

    query = st.text_input("Nhập câu hỏi:", "Huyết áp cao nên ăn uống thế nào?")

    if st.button("Hỏi", type="primary") and query.strip():
        pipeline = RAGPipeline(
            cfg=cfg,
            retriever=FakeRetriever(scores=[score1, score2]),
            generator=FakeGenerator(),
            grader=Grader(cfg.grader),
            rewriter=FakeRewriter(),
        )
        result = pipeline.answer(query)

        badge = {
            "ANSWER": "🟢",
            "ANSWER_WITH_CAUTION": "🟡",
            "ABSTAIN": "🔴",
        }.get(result.action.value, "⚪")
        st.subheader(f"{badge} Hành động: {result.action.value}")
        st.markdown("**Câu trả lời:**")
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

        with st.expander("Chunk đã truy hồi"):
            for i, c in enumerate(result.chunks):
                st.write(f"[{i + 1}] ({c.score:.3f}) {c.text}")


if __name__ == "__main__":
    main()

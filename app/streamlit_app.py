"""Streamlit demo cho ViMed-RAG — T3.6.

HAI TAB, có chủ đích tách rời:

1. **Truy hồi thật** — `HybridRetriever` + `BgeReranker` trên Qdrant Cloud.
   Đây là phần T3.6 mở khoá, và cũng đóng nốt DoD Tuần 2 ("UI hiển thị được
   raw chunk") vốn treo từ Session 5 vì lúc đó chưa có retriever.

2. **Corrective loop (Fake)** — giữ nguyên demo cũ, score điều khiển bằng
   slider để xem 3 nhánh ANSWER / CAUTION / ABSTAIN.

⚠️⚠️ **FILE NÀY ĐANG ĐỨNG YÊN Ở TUẦN 3 TRONG KHI HỆ ĐÃ ĐI TỚI TUẦN 6.**

Bản trước viết: *"KHÔNG nối retriever thật vào `RAGPipeline` — DEC-039, ngưỡng
`0.6` đã bị bác bỏ, ở ngưỡng đó 10/30 câu A/B vẫn được trả lời"*. Lý do đó
**đã hết hiệu lực**, và đây là cách nó hết:

* **DEC-051** hiệu chỉnh ngưỡng bằng LOOCV → `+2,430 logit = sigmoid 0,919`.
* **DEC-052** đóng số đó vào `config.yaml` (`incorrect 0.919` / `correct 0.933`)
  — ngưỡng `0.6` **không còn tồn tại ở đâu** ngoài mấy dòng chữ trong file này.
* **DEC-061** thêm guard lượt 2 → leakage **0/30**, coverage **17/21** không đổi.

Nên điều kiện mà DEC-039 đặt ra đã được thoả, và cái còn thiếu bây giờ **không
phải một lý do, mà là công sức**: tab chạy `RAGPipeline` **đầu-cuối thật** chưa
được viết. Đó là việc **C3 của Tuần 7**.

⛔ **HAI TAB HIỆN CÓ ĐỀU KHÔNG PHẢI HỆ THẬT** — đừng demo mà nói ngược:

1. **Truy hồi thật** — `HybridRetriever` + `BgeReranker` trên Qdrant Cloud.
   Thật, nhưng **dừng ở truy hồi**: không sinh câu trả lời, không có policy
   gate, không có vòng corrective.
2. **Corrective loop (Fake)** — đủ 3 nhánh ANSWER / CAUTION / ABSTAIN nhưng
   chạy bằng `FakeRetriever` + `FakeGenerator`, score kéo bằng slider.

→ **Hệ quả cho B3** (câu `ANSWER` hiện 5 nguồn cạnh một câu nói *"không có
thông tin"*, `A-01`/`E-21`): lỗi đó **chưa hiện ra ở UI này**, vì không tab nào
chạy generator thật. Nó sẽ hiện ra **ngay khi** tab đầu-cuối được viết — nên
chỗ vá đúng là **lúc viết tab đó**, không phải một bản vá riêng bây giờ.

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
# Tab 1 — truy hồi thật
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
        "⚠️ Hệ thống nghiên cứu, KHÔNG thay thế tư vấn y tế. Nhãn abstention "
        "theo khả năng truy xuất + policy, KHÔNG theo đánh giá lâm sàng; "
        "chưa có reviewer y khoa. UI này mới là **truy hồi + demo Fake**, "
        "chưa phải hệ đầu-cuối."
    )


if __name__ == "__main__":
    main()

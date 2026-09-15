"""Benchmark latency TÁCH THEO STAGE — Tuần 7, DoD "latency p50/p95 tách stage".

    python scripts/bench_latency.py                # cả 59 câu (~35 phút)
    python scripts/bench_latency.py --limit 3      # thử đường ống trước
    python scripts/bench_latency.py --groups D     # chỉ nhóm D (0 lượt LLM, miễn phí)

Ghi ra ``data/processed/bench_latency.jsonl`` — **KHÔNG chạm ``runs.jsonl``**.

## ⛔ Vì sao KHÔNG dùng `export_runs.py --force --no-cache`

Đó là đường đầu tiên nghĩ ra, và nó sai ở ba chỗ cộng lại:

* ``--force`` **ghi NỐI THÊM** (``done = set()`` rồi append), không ghi đè;
* ``OUT`` **hard-code** ở ``export_runs.py:80``, không có cờ ``--out``;
* ``runs.jsonl`` **bị gitignore** → không có bản lưu nào trong git.

Cộng lại: một lượt chạy sẽ để lại **118 bản ghi corrective trùng `id`** trong
đúng file mà mọi bảng Tuần 6 ăn vào (risk–coverage · Static-vs-Corrective ·
RAGAS), và không có ``git checkout`` nào cứu được. File riêng thì rủi ro đó
**không tồn tại**, thay vì phải "cẩn thận".

## Vì sao phải có script này, thay vì đọc `cost` trong `runs.jsonl`

``Meter.cost()`` chỉ tách **hai tầng**, và docstring của chính nó đã tự thú:
*"`retrieval_s`: phần còn lại = truy hồi + rerank. **Suy ra chứ không đo
riêng** … con số này **không dùng để chốt bảng Tuần 7**."* Hai chỗ hụt:

* **retrieval và rerank bị gộp** — mà rerank mới là chỗ tốn ~99% (DEC-042);
* **``llm_s`` KHÔNG phải generation.** Ở nhánh TỪ CHỐI nó là **rewrite**
  (32/32 câu ABSTAIN-truy-hồi có ``llm_calls=1`` mà nhánh đó không gọi
  generate). Gộp hai thứ vào một cột là bảng nói sai về chính nó.

## Cách đo: BỌC, không sửa

``HybridRetriever.retrieve()`` vốn đã tách sẵn thành hai lời gọi rời
(``self.search(...)`` rồi ``self._reranker.rerank(...)``), nên không cần đụng
vào nó:

* bọc **reranker** → ``rerank_s``
* bọc **retriever** → ``retrieve_total_s``; suy ra ``search_s = hiệu``
* **hai ``Meter`` riêng** cho generator và rewriter → tách ``generation_s``
  khỏi ``rewrite_s`` (``export_runs.py`` dùng chung **một** meter nên không tách được)

⚠️ Bọc **reranker** chứ **không** bọc ``retrieve()``: bọc ``retrieve()`` đòi
chép lại thân hàm (search rồi rerank) — đúng cái bẫy ``stats.py`` cấm, và là
lần thứ năm repo suýt dính. ``Meter`` cũng **import lại** từ ``export_runs``
chứ không chép.

## ⛔ ĐỐI CHỨNG NHỊP MÁY — phép đo phải tự tố cáo khi máy bận

Phiên 2026-09-15 hỏng **hai** phép đo vì tải máy: smoke ra 100,6 s (so với
44,8 s của lô cũ và 33–41 s trên Space), và page-ready phồng **17×** (5,9 →
103,7 s) chỉ vì bật Chromium mới mỗi mẫu. STATUS cũng đã ghi cùng một cấu hình
rerank từng đo ra 1,72 và **9,35** s/cặp tuỳ tải.

Nên mỗi câu đo kèm ``nhip_may()`` — một vòng lặp CPU thuần, cố định, không
mạng, không I/O. Máy rảnh thì nó ra hằng số; máy bận thì nó phồng theo. Bản
ghi mang ``nhip_ratio``; báo cáo **loại** câu vượt ngưỡng thay vì trộn vào p50.
Một phép đo không có đối chứng thì không phân biệt được "hệ chậm" với
"laptop đang bận", và nó sẽ **âm thầm** ra số sai.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.export_runs import Meter  # noqa: E402  — dùng lại, KHÔNG chép
from src.config import load_config  # noqa: E402
from src.generation.generator import GeminiGenerator  # noqa: E402
from src.pipeline.grader import Grader  # noqa: E402
from src.pipeline.pipeline import RAGPipeline  # noqa: E402
from src.pipeline.rewriter import LLMRewriter  # noqa: E402
from src.retrieval.indexer import collection_name  # noqa: E402

OUT = ROOT / "data" / "processed" / "bench_latency.jsonl"
TESTSET = ROOT / "data" / "testset.jsonl"


#: Ngưỡng đối chứng: câu nào có `nhip_ratio` vượt số này thì báo cáo LOẠI.
#: 1.5 = máy chậm hơn lúc hiệu chuẩn 50%. Chọn rộng tay có chủ đích — mục tiêu
#: là bắt ca hỏng nặng (17x, 9.35/1.72 = 5.4x), không phải lọc nhiễu ±10%.
NGUONG_NHIP = 1.5


# --------------------------------------------------------------------------- #
# Đối chứng nhịp máy
# --------------------------------------------------------------------------- #
def nhip_may(vong: int = 1_000_000) -> float:
    """Vòng lặp CPU thuần, cố định — trả về giây.

    Không mạng, không đĩa, không phụ thuộc dữ liệu. Thời gian của nó **chỉ**
    phụ thuộc CPU rảnh hay bận, nên nó là thước đo tải máy tại đúng thời điểm
    phép đo thật đang chạy.
    """
    t = time.perf_counter()
    s = 0
    for i in range(vong):
        s += i * i % 7
    return time.perf_counter() - t


def hieu_chuan_nhip(lan: int = 7) -> float:
    """Nhịp cơ sở = TRUNG VỊ vài lượt. Trung vị chứ không min: min bắt được
    lúc may mắn nhất, còn ta muốn 'bình thường của máy này'.

    ⚠️ **PHẢI gọi SAU khi dựng pipeline** — bản nháp đầu gọi trước, và lượt thử
    nhóm D gắn cờ "máy bận" cho **13/16 câu** với tỉ lệ 1,36–2,48× trong khi máy
    thật ra rảnh. Nguyên nhân: nền được lấy ở trạng thái **chưa nạp 4,5 GB model
    và chưa spin-up thread pool của torch** — một trạng thái không bao giờ tái
    diễn trong lúc đo. Nền phải lấy ở **đúng điều kiện của phép đo**, nếu không
    chính cái đối chứng trở thành nguồn báo động giả.

    Đo riêng cho thấy bản thân vòng lặp **ổn định 1,04×** (max/trung vị, 15 lượt,
    máy rảnh) — nên nó đủ nhạy, vấn đề nằm ở thời điểm hiệu chuẩn.
    """
    return statistics.median(nhip_may() for _ in range(lan))


# --------------------------------------------------------------------------- #
# Bọc để đo — không sửa gì trong đường được đo
# --------------------------------------------------------------------------- #
class DemGio:
    """Bộ cộng dồn giây + số lượt, dùng chung cho hai lớp bọc dưới."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.seconds = 0.0
        self.calls = 0

    def ghi(self, t0: float) -> None:
        self.seconds += time.perf_counter() - t0
        self.calls += 1


class RerankerDoGio:
    """Bọc reranker. Giữ nguyên chữ ký ``rerank`` để `HybridRetriever` không biết."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.dem = DemGio()

    def rerank(self, query, chunks, top_k):
        t0 = time.perf_counter()
        ra = self._inner.rerank(query, chunks, top_k=top_k)
        self.dem.ghi(t0)
        return ra


class RetrieverDoGio:
    """Bọc retriever ở tầng ``retrieve`` — tổng của (search + rerank).

    ⚠️ Cố ý **không** tự gọi ``search`` rồi ``rerank``: làm thế là chép lại thân
    ``HybridRetriever.retrieve()``, và hai bản sao sẽ trôi khỏi nhau mà không
    có gì bắt được (bài học ``stats.py``). ``search_s`` suy ra bằng hiệu.
    """

    def __init__(self, inner) -> None:
        self._inner = inner
        self.dem = DemGio()

    def retrieve(self, query):
        t0 = time.perf_counter()
        ra = self._inner.retrieve(query)
        self.dem.ghi(t0)
        return ra


# --------------------------------------------------------------------------- #
def nap_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def nap_cau_hoi(groups: set[str], limit: int | None) -> list[dict]:
    """Câu hỏi + nhóm, **chỉ** từ `testset.jsonl`.

    ⚠️ **ĐỪNG nạp thêm `testset_d.jsonl`** — bản nháp đầu làm thế và nhóm D ra
    **16 câu thay vì 8**. `testset.jsonl` đã chứa đủ **cả 59 câu A18/B12/D8/E21**
    kèm `user_input`; `testset_d.jsonl` là bản ghi riêng của nhóm D, **trùng**
    chứ không bổ sung. Lượt thử `--groups D` bắt được ngay ở dòng đếm `[3/16]`.
    """
    ra: list[dict] = []
    for line in TESTSET.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("group") in groups:
            ra.append({"id": r["id"], "group": r["group"], "q": r["user_input"]})
    ra.sort(key=lambda x: x["id"])
    return ra[:limit] if limit else ra


def dung_pipeline(cfg, api_key: str):
    """Pipeline thật + 4 dụng cụ đo. Nối dây y hệt `export_runs.build_pipeline`,
    khác đúng hai chỗ: bỏ `RecordingRetriever` (không cần lượt 1) và **hai**
    meter thay vì một."""
    import torch

    from src.retrieval.embedder import BgeM3Embedder
    from src.retrieval.reranker import BgeReranker
    from src.retrieval.retriever import HybridRetriever

    fp16 = bool(cfg.index.use_fp16 and torch.cuda.is_available())
    embedder = BgeM3Embedder(cfg.models, cfg.index, use_fp16=fp16)
    embedder.embed_hybrid(["khởi động"])

    rr = RerankerDoGio(
        BgeReranker(cfg.models, use_fp16=fp16, max_length=cfg.retrieval.rerank_max_length)
    )
    retr = RetrieverDoGio(
        HybridRetriever(
            cfg,
            embedder,
            collection=collection_name(cfg.qdrant.collection, cfg.chunking.size),
            mode="hybrid",
            reranker=rr,
        )
    )
    # HAI meter riêng — đây là thứ `export_runs.py` không có, và là lý do
    # `llm_s` của nó không tách được generation khỏi rewrite.
    m_gen, m_rw = Meter(cfg, api_key), Meter(cfg, api_key)
    pipe = RAGPipeline(
        cfg=cfg,
        retriever=retr,
        generator=GeminiGenerator(
            cfg.generation, api_key, model=cfg.models.llm, transport=m_gen.transport
        ),
        grader=Grader(cfg.grader),
        rewriter=LLMRewriter(
            cfg.generation, api_key, model=cfg.models.llm, transport=m_rw.transport
        ),
    )
    return pipe, retr, rr, m_gen, m_rw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--groups", default="A,B,D,E")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=str(OUT), help="đường ra (mặc định KHÁC runs.jsonl)")
    args = ap.parse_args()

    nap_env()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("⛔ Thiếu GEMINI_API_KEY. `setx` KHÔNG áp cho terminal đang mở.")
        return 1

    cfg = load_config()
    cau = nap_cau_hoi(set(args.groups.split(",")), args.limit)
    out = Path(args.out)
    if out.resolve() == (ROOT / "data" / "processed" / "runs.jsonl").resolve():
        print("⛔ TỪ CHỐI ghi đè `runs.jsonl` — đó là bằng chứng Tuần 6. Xem docstring.")
        return 1

    print(
        f"Cấu hình: {cfg.models.llm_provider}/{cfg.models.llm} · hybrid · "
        f"chunk={cfg.chunking.size} · top_k_dense={cfg.retrieval.top_k_dense} · "
        f"rerank_max_length={cfg.retrieval.rerank_max_length}"
    )
    print(f"Câu hỏi : {len(cau)} · ghi ra {out.name}\n")

    t0 = time.perf_counter()
    pipe, retr, rr, m_gen, m_rw = dung_pipeline(cfg, api_key)
    print(f"[ok] nạp model {time.perf_counter() - t0:.1f}s")

    # Hiệu chuẩn SAU khi nạp model — xem docstring `hieu_chuan_nhip`.
    nhip0 = hieu_chuan_nhip()
    print(f"[ok] nhịp máy cơ sở = {nhip0 * 1000:.0f} ms (đối chứng tải máy)\n")

    out.parent.mkdir(parents=True, exist_ok=True)
    fh = out.open("w", encoding="utf-8")
    ban = 0
    for i, c in enumerate(cau, 1):
        for d in (retr.dem, rr.dem):
            d.reset()
        m_gen.reset()
        m_rw.reset()

        nhip_truoc = nhip_may()
        t1 = time.perf_counter()
        kq = pipe.answer(c["q"])
        tong = time.perf_counter() - t1
        nhip_sau = nhip_may()

        # Lấy nhịp XẤU NHẤT quanh phép đo: một đợt tải đi qua giữa chừng thì
        # trung bình sẽ giấu nó, còn max thì không.
        ratio = max(nhip_truoc, nhip_sau) / nhip0
        if ratio > NGUONG_NHIP:
            ban += 1

        rec = {
            "id": c["id"],
            "group": c["group"],
            "action": kq.action.value,
            "co_che": "policy"
            if any(b.step == "ABSTAIN" and (b.note or "").startswith("policy:") for b in kq.trace)
            else ("retrieval" if kq.action.value == "ABSTAIN" else None),
            "total_s": round(tong, 3),
            "retrieve_total_s": round(retr.dem.seconds, 3),
            "rerank_s": round(rr.dem.seconds, 3),
            "search_s": round(retr.dem.seconds - rr.dem.seconds, 3),
            "generation_s": round(m_gen.seconds, 3),
            "rewrite_s": round(m_rw.seconds, 3),
            "n_retrieve": retr.dem.calls,
            "n_rerank": rr.dem.calls,
            "generation_calls": m_gen.calls,
            "rewrite_calls": m_rw.calls,
            "prompt_tokens": m_gen.prompt_tokens + m_rw.prompt_tokens,
            "output_tokens": m_gen.output_tokens + m_rw.output_tokens,
            "nhip_ratio": round(ratio, 3),
            "may_ban": ratio > NGUONG_NHIP,
        }
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()

        co = "⚠️ MÁY BẬN" if rec["may_ban"] else ""
        print(
            f"[{i:>2}/{len(cau)}] {c['id']:<6} {kq.action.value:<20} "
            f"{tong:>6.1f}s  (rerank {rr.dem.seconds:>5.1f} · "
            f"search {rec['search_s']:>4.1f} · gen {m_gen.seconds:>4.1f} · "
            f"rw {m_rw.seconds:>4.1f})  nhịp×{ratio:.2f} {co}"
        )
    fh.close()

    print(f"\n[ok] {len(cau)} câu → {out}")
    if ban:
        print(f"⚠️  {ban}/{len(cau)} câu đo lúc MÁY BẬN (nhịp × > {NGUONG_NHIP}).")
        print("    Báo cáo sẽ LOẠI chúng khỏi p50/p95. Máy rảnh thì chạy lại.")
    else:
        print(f"✅ 0 câu bị tải máy làm bẩn — nhịp giữ trong {NGUONG_NHIP}× suốt lô.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

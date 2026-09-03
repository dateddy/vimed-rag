"""
Sinh ỨNG VIÊN nhóm A (ngoài corpus) và nhóm B (ngoài chuyên khoa) — Bước 3.
===========================================================================
Tiêu chí gán nhãn: **DEC-026**.

  A (18 câu) = Q+A khớp **>=1** keyword 2 khoa  VÀ  thực thể **0 hit** trong corpus
  B (12 câu) = Q+A khớp **0**  keyword 2 khoa  VÀ  thực thể **0 hit** trong corpus

Cả hai đều nhãn **ABSTAIN**.

VÌ SAO HARVEST CHỨ KHÔNG TỰ VIẾT (DEC-026 lý do 1)
--------------------------------------------------
Tự nghĩ tên thuốc "chắc chắn không có trong KB" có rủi ro bịa nhầm một tên KHÔNG
TỒN TẠI — khi đó nhóm A đo "phát hiện câu vô nghĩa" chứ không phải "biết ranh
giới tri thức của chính mình". ViMedAQA có cột `keyword` = thực thể CÓ THẬT của
câu hỏi, nên chỉ cần grep nó trên corpus là ra nhãn máy kiểm được.

VÌ SAO NHÓM B CŨNG PHẢI 0-HIT (DEC-026 lý do 3)
-----------------------------------------------
Plan gốc verify nhóm B bằng metadata `specialty` là KHÔNG ĐỦ. DEC-025 đã chứng
minh corpus có bài ngoài khoa do gán nhầm (bài *Tiền sản giật* mang nhãn
`tim_mach`). Câu B rơi trúng bài đó thì retrieval tìm ra, hệ thống trả lời, và bị
đếm thành "unsafe answer" trong khi thực chất là artifact gán khoa.

PHÉP KIỂM 0-HIT
---------------
Chuẩn hoá `keyword`: bỏ hàm lượng (20mg, 5ml...) + dạng bào chế/hậu tố (LA, SR,
viên, nang...), fold dấu + lowercase. Rồi đếm số BÀI chứa cụm đó, khớp
word-boundary. Tăng tốc bằng index token -> tập bài: giao tập của mọi token
trong cụm; rỗng thì chắc chắn 0 hit, không rỗng thì mới regex trên vài bài đó.
Kết quả là ĐẾM CHÍNH XÁC, không phải xấp xỉ.

CHẠY
----
  python scripts/testset_ab_candidates.py
  python scripts/testset_ab_candidates.py --n-a 40 --n-b 30

KHÔNG được import bởi `src/` hay `tests/` — script chạy tay, tải dataset thật.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "processed" / "corpus.jsonl"
OUT_MD = ROOT / "data" / "processed" / "testset_ab_candidates.md"
OUT_JSONL = ROOT / "data" / "processed" / "testset_ab_candidates.jsonl"

_spec = importlib.util.spec_from_file_location("gate0", ROOT / "scripts" / "gate0_data_check.py")
g0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g0)

from datasets import load_dataset  # noqa: E402

# Hàm lượng + dạng bào chế + hậu tố phóng thích: KHÔNG phải tên thực thể.
# "Adalat LA 20mg" -> "adalat". Giữ lại phần định danh thật để grep cho đúng.
DOSE = re.compile(r"\b\d+[\d.,/]*\s*(mg|mcg|g|ml|l|ui|iu|%|đvqt)\b", re.I)
FORM = re.compile(
    r"\b(la|sr|xr|mr|cr|xl|od|forte|plus|retard|film|tab|tablet|caps?|"
    r"viên|nang|tiêm|siro|gói|ống|hộp|vỉ|dung dịch|hỗn dịch|bột)\b", re.I)
NUM = re.compile(r"\b\d+\b")
TOKEN = re.compile(r"\w+", re.UNICODE)

# Token quá phổ thông thì không dùng làm bằng chứng "vắng mặt".
STOP = {"bệnh", "thuốc", "hội", "chứng", "viêm", "đau", "u", "ung", "thư",
        "cấp", "mạn", "tính", "của", "và", "các", "loại", "người", "trẻ", "em"}

# --- Lọc keyword dạng TIÊU ĐỀ, không phải thực thể nguyên tử ---
# Cột `keyword` của ViMedAQA TRỘN hai loại: thực thể ("Aspirin STELLA",
# "Đái tháo đường type 1") và cụm tiêu đề ("Hormone Estrogen và những thông tin
# bạn cần biết", "Biến chứng tiểu đường gây loét da").
#
# Kiểm 0-hit CHỈ có nghĩa với loại đầu. Với cụm tiêu đề, "0 hit" chỉ nói lên
# rằng corpus không dùng đúng cách diễn đạt đó — chủ đề vẫn có thể được phủ rất
# dày. Phát hiện 2026-08-23: E-01 ("Biến chứng tiểu đường gây loét da") bị cờ
# 0-hit trong khi corpus có nguyên một bài về loét bàn chân do tiểu đường.
# Không lọc thì nhóm A/B sẽ đầy "thực thể vắng mặt" giả.
TITLE_WORDS = {"và", "những", "cần", "bạn", "thông", "tin", "biết", "gì", "nào",
               "sao", "cách", "gây", "khi", "cho", "về", "với", "là", "có", "thế"}
MAX_KW_TOKENS = 5


def is_atomic_entity(nk: str) -> bool:
    """`nk` có phải thực thể nguyên tử (chứ không phải cụm tiêu đề) không?"""
    toks = TOKEN.findall(nk)
    return bool(toks) and len(toks) <= MAX_KW_TOKENS and not (set(toks) & TITLE_WORDS)


# --- Gợi ý XẾP HẠNG: thực thể nghe có "mùi" tim mạch / tiểu đường không? ---
#
# ⚠️ CHỈ DÙNG ĐỂ SẮP THỨ TỰ VÀ CẢNH BÁO. KHÔNG dùng để gán nhãn.
# Tiêu chí gán nhãn A/B vẫn nguyên như DEC-026 (khớp keyword trên Q+A).
#
# Lý do cần thêm tín hiệu này: `config/specialties.yaml` được chỉnh để GÁN KHOA CHO
# BÀI VIẾT (DEC-010 siết cho sạch), không phải để phân loại CÂU HỎI, nên nó sai cả
# hai hướng. Đo 2026-08-23: khớp trên Q+A thì `Ung thư xương` lọt vào nhóm A; khớp
# chỉ trên câu hỏi thì `Hẹp van 2 lá` và `Âm thổi tại tim` bị loại — hai câu tim mạch
# rõ ràng nhất. Từ vựng có `van tim` nhưng không có `van hai lá`.
#
# Nên thay vì siết tiêu chí (sẽ mất câu tốt), ta chỉ ĐẨY LÊN ĐẦU những ứng viên có
# khả năng thuộc khoa, để người soi gặp câu tốt trước. Quyết định cuối vẫn là mắt người.
HINT_TERMS = (
    "tim|mạch|van|nhịp|thất|nhĩ|vành|huyết áp|cholesterol|lipid|mỡ máu|xơ vữa|"
    "đường huyết|tiểu đường|đái tháo|insulin|glucose|tụy|hba1c|glycemic"
)
# Hậu tố nhóm thuốc — bắt được thuốc tim mạch/tiểu đường mà tên riêng không lộ gì,
# vd "Atorvastatin T.V Pharm" (statin, hạ lipid) vốn rơi nhầm sang nhóm B.
HINT_DRUG = "statin|sartan|pril|olol|dipine|gliptin|glifl?ozin|glinide|glitazone|metformin|gliclazid|glimepirid"
HINT = re.compile(f"({HINT_TERMS}|{HINT_DRUG})", re.I)


def spec_hint(kw: str) -> bool:
    """Thực thể có mùi 2 khoa không? Chỉ để xếp hạng/cảnh báo."""
    return bool(HINT.search(g0.normalize_text(kw)))


def norm_keyword(kw: str) -> str:
    s = g0.normalize_text(kw)
    s = DOSE.sub(" ", s)
    s = FORM.sub(" ", s)
    s = NUM.sub(" ", s)
    return " ".join(s.split())


def build_index(docs: list[dict]) -> tuple[list[str], dict[str, set]]:
    """text đã chuẩn hoá của từng bài + index token -> tập chỉ số bài."""
    norms, idx = [], collections.defaultdict(set)
    for i, d in enumerate(docs):
        t = g0.normalize_text(d["text"])
        norms.append(t)
        for tok in set(TOKEN.findall(t)):
            idx[tok].add(i)
    return norms, idx


def count_hits(phrase: str, norms: list[str], idx: dict[str, set]) -> int:
    """Số BÀI chứa `phrase` (word-boundary). Chính xác, không xấp xỉ."""
    toks = TOKEN.findall(phrase)
    if not toks:
        return -1  # keyword rỗng sau chuẩn hoá -> không dùng được
    cands: set | None = None
    for t in toks:
        s = idx.get(t, set())
        cands = s if cands is None else (cands & s)
        if not cands:
            return 0
    pat = re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)")
    return sum(1 for i in cands if pat.search(norms[i]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-a", type=int, default=36, help="số ứng viên nhóm A (cần chọn 18)")
    ap.add_argument("--n-b", type=int, default=24, help="số ứng viên nhóm B (cần chọn 12)")
    args = ap.parse_args()

    kw_map = g0.load_specialty_keywords()
    specs = list(kw_map)
    pats = {s: [re.compile(r"(?<!\w)" + re.escape(k) + r"(?!\w)") for k in ks]
            for s, ks in kw_map.items()}

    if not CORPUS.exists():
        sys.exit(f"!! Thiếu {CORPUS}. Chạy scripts/run_ingestion.py trước.")
    docs = [json.loads(line) for line in CORPUS.open(encoding="utf-8")]
    print(f"[corpus] {len(docs)} bài — dựng index token ...")
    norms, idx = build_index(docs)
    print(f"[corpus] {len(idx)} token phân biệt")

    print(f"[eval] tải {g0.EVAL_DATASET} split={g0.EVAL_SPLIT} ...")
    ds = load_dataset(g0.EVAL_DATASET, split=g0.EVAL_SPLIT)

    cache: dict[str, int] = {}
    pool_a: dict[str, dict] = {}   # 1 câu / thực thể, tránh 10 câu cùng 1 thuốc
    pool_b: dict[str, dict] = {}
    n_seen = n_nokw = 0

    for i, row in enumerate(ds):
        q = str(row.get("question", "")).strip()
        a = str(row.get("answer", "")).strip()
        kw = str(row.get("keyword", "")).strip()
        if not (15 <= len(q) <= 300 and 40 <= len(a) <= 1500 and kw):
            continue
        n_seen += 1
        nk = norm_keyword(kw)
        if not nk or all(t in STOP for t in TOKEN.findall(nk)) or not is_atomic_entity(nk):
            n_nokw += 1
            continue
        if nk in cache:
            hits = cache[nk]
        else:
            hits = count_hits(nk, norms, idx)
            cache[nk] = hits
        if hits != 0:
            continue
        hit_spec = [s for s, ps in pats.items()
                    if any(p.search(g0.normalize_text(f"{q} {a}")) for p in ps)]
        # LOẠI thực thể (body-part | disease | drug | medicine) lấy từ tiền tố
        # `question_idx`; `topic` là ClassLabel int nên khó đọc khi soi tay.
        etype = str(row.get("question_idx", "")).split("_")[0] or "?"
        rec = {"idx": i, "q": q, "a": a, "kw": kw, "nk": nk, "etype": etype,
               "topic": str(row.get("topic", "")), "specs": hit_spec,
               "hint": spec_hint(kw)}
        tgt = pool_a if hit_spec else pool_b
        if nk not in tgt:
            tgt[nk] = rec

    print(f"[eval] {n_seen} QA hợp lệ · {n_nokw} bỏ vì keyword rỗng/toàn stopword")
    print(f"[0-hit] thực thể vắng mặt khỏi corpus: "
          f"A(trong khoa) {len(pool_a)} · B(ngoài khoa) {len(pool_b)}")

    # Nhóm A: cân theo LOẠI THỰC THỂ trước, rồi cân khoa trong từng loại.
    #
    # Cân theo loại là BẮT BUỘC, không phải cho đẹp. Loại thực thể quyết định độ
    # KHÓ của việc abstain: tên biệt dược là token hiếm -> retrieval không khớp gì
    # -> score thấp -> abstain dễ. Còn một BỆNH trong khoa nhưng vắng mặt (vd
    # "cường aldosterone nguyên phát", một nguyên nhân tăng huyết áp thứ phát có
    # thật) sẽ kéo về hàng loạt bài tăng huyết áp rất giống -> score CAO -> grader
    # chấm CORRECT -> hệ thống trả lời tự tin về thứ nó không có. Đó mới là ca
    # nguy hiểm và là ca phải đo.
    #
    # Đo 2026-08-23 khi chưa cân: 36/36 ứng viên đều là `drug` (ViMedAQA xếp
    # dataset theo cụm, thuốc nằm đầu) -> nhóm A chỉ đo ĐẦU DỄ của phổ và làm số
    # abstention đẹp hơn thực tế. Xem DEC-028.
    A_MIX = {"disease": 12, "drug": 12, "medicine": 8, "body-part": 4}
    a_by_type = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in pool_a.values():
        a_by_type[r["etype"]][r["specs"][0]].append(r)
    # Đẩy ứng viên "có mùi 2 khoa" lên đầu mỗi rổ -> người soi gặp câu tốt trước.
    for et in a_by_type:
        for sp in a_by_type[et]:
            a_by_type[et][sp].sort(key=lambda r: not r["hint"])
    picked_a = []
    for et, quota in A_MIX.items():
        buckets = a_by_type[et]
        take, i = [], 0
        while len(take) < quota and any(buckets[s] for s in specs):
            s = specs[i % len(specs)]
            if buckets[s]:
                take.append(buckets[s].pop(0))
            i += 1
        picked_a.extend(take)
        if len(take) < quota:
            print(f"[pick] !! loại '{et}' chỉ có {len(take)}/{quota} ứng viên")
    b_by_topic = collections.defaultdict(list)
    for r in pool_b.values():
        b_by_topic[r["topic"]].append(r)
    # Nhóm B: đẩy ứng viên KHÔNG có mùi 2 khoa lên đầu. Ngược chiều nhóm A, vì B
    # cần câu ngoài khoa rõ ràng. Bắt được ca "Atorvastatin T.V Pharm" — statin hạ
    # lipid, tim mạch thật, nhưng Q+A không nhắc keyword nào nên lọt sang B.
    for t in b_by_topic:
        b_by_topic[t].sort(key=lambda r: r["hint"])
    picked_b, t_keys = [], list(b_by_topic)
    while len(picked_b) < args.n_b and any(b_by_topic[t] for t in t_keys):
        for t in t_keys:
            if b_by_topic[t] and len(picked_b) < args.n_b:
                picked_b.append(b_by_topic[t].pop(0))

    print(f"[pick] A {len(picked_a)} "
          f"· khoa {dict(collections.Counter(r['specs'][0] for r in picked_a))} "
          f"· loại {dict(collections.Counter(r['etype'] for r in picked_a))}")
    print(f"[pick] B {len(picked_b)} "
          f"(topic: {dict(collections.Counter(r['topic'] for r in picked_b))})")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MD.open("w", encoding="utf-8") as f:
        f.write("# Ứng viên nhóm A + B — SOI TAY, script không gán nhãn\n\n")
        f.write("Mọi ứng viên dưới đây đã qua kiểm máy: thực thể (`keyword`) có **0 bài** "
                "trong corpus. Việc của bạn là câu hỏi CÒN LẠI.\n\n")
        f.write("## Nhóm A — hỏi: *đây có phải câu người dùng hệ tim mạch/tiểu đường sẽ hỏi không?*\n\n"
                "Cần **18**. Tỉ lệ mục tiêu theo LOẠI thực thể (DEC-028): "
                "**disease 7 · drug 6 · medicine 3 · body-part 2**.\n\n"
                "Đừng chọn toàn `drug`: tên biệt dược là token hiếm nên abstain quá dễ, "
                "chỉ đo được đầu dễ của phổ. `disease` mới là ca khó — nó kéo về bài "
                "cùng chủ đề với score cao và dụ hệ thống trả lời.\n\n"
                "Loại nếu: câu quá hẹp/kỹ thuật, hoặc thực ra không thuộc 2 khoa mà chỉ "
                "dính keyword.\n\n---\n\n")
        for et in ("disease", "drug", "medicine", "body-part"):
            grp = [(n, r) for n, r in enumerate(picked_a, 1) if r["etype"] == et]
            if not grp:
                continue
            f.write(f"\n### === LOẠI: {et} ({len(grp)} ứng viên) ===\n\n")
            for n, r in grp:
                tag = "⭐ " if r["hint"] else "   "
                f.write(f"#### {tag}A-cand {n:02d} · `{r['kw']}` -> grep `{r['nk']}` = 0 bài\n\n")
                f.write(f"**Hỏi:** {r['q']}\n\n**Đáp án (ViMedAQA):** {r['a'][:400]}\n\n")
        f.write("\n## Nhóm B — hỏi: *đây có RÕ RÀNG là khoa khác không?*\n\n"
                "Cần **12**. Loại nếu còn mơ hồ về khoa.\n\n---\n\n")
        for n, r in enumerate(picked_b, 1):
            warn = " ⚠️ **NGHI thuộc 2 khoa — kiểm kỹ trước khi lấy**" if r["hint"] else ""
            f.write(f"### B-cand {n:02d} · `{r['kw']}` -> grep `{r['nk']}` = 0 bài{warn}\n\n")
            f.write(f"**Hỏi:** {r['q']}\n\n**Đáp án (ViMedAQA):** {r['a'][:400]}\n\n")

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for grp, picked in (("A", picked_a), ("B", picked_b)):
            for n, r in enumerate(picked, 1):
                f.write(json.dumps({
                    "id": f"{grp}-cand-{n:02d}",
                    "group": grp,
                    "user_input": r["q"],
                    "expected_action": "ABSTAIN",
                    "specialty": r["specs"][0] if r["specs"] else None,
                    "label_source": f"vimedaqa:{g0.EVAL_SPLIT}:{r['idx']} + grep:corpus",
                    "label_evidence": {"entity": r["kw"], "entity_normalized": r["nk"],
                                       "entity_type": r["etype"], "corpus_hits": 0,
                                       "eyeballed": False},
                    "reference": None,
                    "reference_contexts": [],
                    "reference_context_ids": [],
                }, ensure_ascii=False) + "\n")

    print(f"\n[out] {OUT_MD.relative_to(ROOT)}   <- MỞ FILE NÀY ĐỂ SOI TAY")
    print(f"[out] {OUT_JSONL.relative_to(ROOT)}")
    print("\nBước tiếp: chọn 18 nhóm A + 12 nhóm B, gửi lại danh sách id.")


if __name__ == "__main__":
    main()

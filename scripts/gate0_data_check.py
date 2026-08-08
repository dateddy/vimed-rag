"""
Gate 0 — Data Sufficiency Check for ViMed-RAG
================================================
Chạy TRƯỚC khi build bất cứ thứ gì. Trả lời 3 câu hỏi go/no-go:

  1. Corpus có đủ >=150 bài chất lượng / khoa không?      (urnus11/Vietnamese-Healthcare)
  2. Eval set có đủ ~40-50 QA thuộc 2 khoa không?          (ViMedAQA)
  3. Đáp án ViMedAQA có THỰC SỰ nằm trong corpus không?    (alignment — cái tinh vi nhất)

Nếu #3 fail (đáp án không có trong corpus) thì faithfulness/context-recall sẽ thấp
GIẢ TẠO, và bạn không phân biệt được "retrieval hỏng" với "đáp án vốn không có".
=> Cả claim corrective sập theo. Đây là lý do phải gate trước khi build.

Môi trường: Kaggle / Colab (CPU đủ — không cần GPU).
  pip install datasets scikit-learn pandas numpy

CÁCH DÙNG:
  1. Chạy lần 1 với INSPECT_ONLY = True  -> in schema để biết tên cột thật.
  2. Sửa block CONFIG cho khớp tên cột.
  3. Chạy lần 2 với INSPECT_ONLY = False -> ra verdict.

GHI CHÚ TÍCH HỢP REPO:
  - SPECIALTY_KEYWORDS ưu tiên đọc từ config/specialties.yaml (single source of
    truth). Nếu chạy standalone trên Colab (không có repo) thì dùng dict fallback
    ngay bên dưới. Muốn đổi/thêm keyword: sửa config/specialties.yaml.
  - Đây là script cổng dữ liệu, KHÔNG tải model/API. An toàn chạy trước Gate 0 GO.
"""

import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Ép stdout UTF-8 để in tiếng Việt trên console Windows (cp1252) không lỗi.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ============================================================================
# CONFIG  —  CHỈNH PHẦN NÀY SAU KHI CHẠY LẦN 1 (INSPECT_ONLY=True)
# ============================================================================

INSPECT_ONLY = False  # True: chỉ in schema + sample. False: chạy full check.

# --- Datasets ---
CORPUS_DATASET = "urnus11/Vietnamese-Healthcare"   # GATED — cần HF_TOKEN + accept terms
# Dataset KHÔNG có split "train". Split thật: full | medical_qa |
# vinmec_article_content | vinmec_article_main | vinmec_article_subtitle.
# Chọn article_content = 32,604 bài viết đầy đủ -> đúng nghĩa "bài" của tiêu chí #1.
CORPUS_SPLIT = "vinmec_article_content"
# Tên cột chứa nội dung bài viết. Để None để tự đoán (cột text dài nhất).
CORPUS_TEXT_COL = "content"
# Ghép title + content: keyword khoa hay nằm ở title ("Nhồi máu cơ tim", "Tiểu đường
# type 2") trong khi body chỉ viết "bệnh này" -> ghép để không sót bài khi lọc khoa.
CORPUS_TEXT_COLS = ["title", "content"]

EVAL_DATASET = "tmnam20/ViMedAQA"   # public, không gated (verify 2026-08-07)
EVAL_SPLIT = "train"                # config "all": train=39,881 / test=2,217 / val=2,215
EVAL_QUESTION_COL = "question"
EVAL_ANSWER_COL = "answer"
EVAL_CATEGORY_COL = "topic"         # ClassLabel: body-part | disease | drug | medicine

# --- Ngưỡng pass ---
MIN_ARTICLES_PER_SPECIALTY = 150
MIN_EVAL_QA_TOTAL = 40
MIN_ARTICLE_CHARS = 100            # bài ngắn hơn -> loại
ALIGNMENT_SIM_FLOOR = 0.15        # max cosine < mức này coi như đáp án "không tìm thấy"
ALIGNMENT_PASS_RATIO = 0.6        # cần >=60% QA có đáp án tìm thấy trong corpus
ALIGNMENT_SAMPLE_N = 30           # số QA lấy mẫu để check (in 10 ca xấu nhất)

# --- Keyword 2 khoa: FALLBACK khi chạy standalone (không có config/specialties.yaml) ---
# Repo có config/specialties.yaml -> load_specialty_keywords() ưu tiên đọc từ đó.
# PHẢI KHỚP config/specialties.yaml — sync tay khi đổi bên đó (siết 2026-08-07,
# xem DEC-010). Lệch nhau = chạy standalone ra số khác chạy trong repo.
_FALLBACK_SPECIALTY_KEYWORDS = {
    "tim_mach": [
        "tim mạch", "bệnh tim", "trái tim", "suy tim", "nhịp tim", "cơ tim",
        "van tim", "màng ngoài tim", "tim bẩm sinh", "đau tim", "sốc tim",
        "ngừng tim", "phẫu thuật tim", "thông tim", "điện tim", "điện tâm đồ",
        "mạch vành", "xơ vữa động mạch", "đau thắt ngực", "huyết áp",
        "cholesterol", "mỡ máu", "rối loạn lipid máu",
    ],
    "tieu_duong": [
        "tiểu đường", "đái tháo đường", "đường huyết", "đường máu",
        "insulin", "glucose", "hba1c", "metformin",
    ],
}


def load_specialty_keywords() -> dict:
    """Đọc keyword 2 khoa từ config/specialties.yaml (single source of truth).

    Fallback về _FALLBACK_SPECIALTY_KEYWORDS nếu không tìm thấy repo/file
    (VD chạy standalone trên Colab chỉ upload mỗi file .py này).
    """
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "specialties.yaml"
    try:
        import yaml  # pyyaml có sẵn trên Colab/Kaggle

        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data:
            print(f"[keywords] đọc từ {cfg_path}")
            return {k: list(v) for k, v in data.items()}
    except Exception as e:  # noqa: BLE001 — standalone thì fallback là hành vi đúng
        print(f"[keywords] không đọc được config/specialties.yaml ({e}); dùng fallback.")
    return _FALLBACK_SPECIALTY_KEYWORDS


SPECIALTY_KEYWORDS = load_specialty_keywords()

# ============================================================================
# CORE FUNCTIONS  (đã unit-test)
# ============================================================================

def normalize_text(s: str) -> str:
    """Chuẩn hóa Unicode NFC + lowercase + gộp khoảng trắng."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFC", str(s))
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_article(s: str) -> str:
    """Bỏ tag HTML + ký tự rác cơ bản (bản nhẹ cho gate; clean thật ở Tuần 1)."""
    if s is None:
        return ""
    s = re.sub(r"<[^>]+>", " ", str(s))          # strip HTML
    s = re.sub(r"[ \t]+", " ", s)
    return unicodedata.normalize("NFC", s).strip()


def matched_specialties(text: str, keyword_map: dict) -> list:
    """Trả về list khoa mà text khớp (>=1 keyword). Match theo ranh giới từ Unicode."""
    norm = normalize_text(text)
    hits = []
    for spec, kws in keyword_map.items():
        for kw in kws:
            # (?<!\w) ... (?!\w): không nằm giữa 1 từ khác. \w bao gồm cả chữ có dấu.
            if re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", norm):
                hits.append(spec)
                break
    return hits


def guess_text_column(dataset) -> str:
    """Đoán cột text: cột string có độ dài trung bình lớn nhất trên 200 dòng mẫu."""
    cols = dataset.column_names
    sample = dataset.select(range(min(200, len(dataset))))
    best_col, best_len = None, -1
    for c in cols:
        vals = sample[c]
        if not vals or not isinstance(vals[0], str):
            continue
        avg = np.mean([len(v) for v in vals if isinstance(v, str)])
        if avg > best_len:
            best_col, best_len = c, avg
    return best_col


def pick_column(dataset, configured, candidates):
    """Chọn cột: ưu tiên configured, sau đó dò theo candidates, cuối cùng đoán."""
    cols = dataset.column_names
    if configured and configured in cols:
        return configured
    for cand in candidates:
        for c in cols:
            if c.lower() == cand:
                return c
    return guess_text_column(dataset)


def get_article_text(row, text_col, text_cols) -> str:
    if text_cols:
        return " ".join(str(row.get(c, "")) for c in text_cols)
    return str(row.get(text_col, ""))


# ============================================================================
# ANALYSIS
# ============================================================================

def inspect(name, dataset):
    print(f"\n{'='*70}\nSCHEMA — {name}\n{'='*70}")
    print(f"Số dòng: {len(dataset)}")
    print(f"Cột: {dataset.column_names}")
    print("\n--- 2 dòng mẫu ---")
    for i in range(min(2, len(dataset))):
        row = dataset[i]
        for k, v in row.items():
            preview = str(v).replace("\n", " ")
            preview = preview[:180] + ("..." if len(str(v)) > 180 else "")
            print(f"  [{k}] {preview}")
        print("  " + "-" * 40)


def check_corpus_coverage(corpus_ds):
    text_col = pick_column(corpus_ds, CORPUS_TEXT_COL, ["content", "text", "body", "article"])
    print(f"\n[Corpus] dùng cột text: '{text_col}'"
          + (f" (ghép: {CORPUS_TEXT_COLS})" if CORPUS_TEXT_COLS else ""))

    per_spec = defaultdict(int)
    both = 0
    total_kept = 0
    seen = set()

    for row in corpus_ds:
        raw = get_article_text(row, text_col, CORPUS_TEXT_COLS)
        text = clean_article(raw)
        if len(text) < MIN_ARTICLE_CHARS:
            continue
        key = text[:200]                      # dedup thô theo 200 ký tự đầu
        if key in seen:
            continue
        seen.add(key)
        specs = matched_specialties(text, SPECIALTY_KEYWORDS)
        if not specs:
            continue
        total_kept += 1
        for s in specs:
            per_spec[s] += 1
        if len(specs) > 1:
            both += 1

    print(f"\n--- KẾT QUẢ CORPUS (sau clean + loại <{MIN_ARTICLE_CHARS} ký tự + dedup) ---")
    passed = True
    for spec in SPECIALTY_KEYWORDS:
        n = per_spec[spec]
        ok = n >= MIN_ARTICLES_PER_SPECIALTY
        passed = passed and ok
        print(f"  {spec:12s}: {n:5d} bài   [{'PASS' if ok else 'FAIL'}] "
              f"(cần >={MIN_ARTICLES_PER_SPECIALTY})")
    print(f"  (bài khớp cả 2 khoa: {both})")
    return passed, text_col


def check_eval_coverage(eval_ds):
    q_col = pick_column(eval_ds, EVAL_QUESTION_COL, ["question", "query", "cauhoi", "cau_hoi"])
    a_col = pick_column(eval_ds, EVAL_ANSWER_COL, ["answer", "answers", "dapan", "dap_an"])
    print(f"\n[Eval] cột question: '{q_col}' | answer: '{a_col}'")

    if EVAL_CATEGORY_COL and EVAL_CATEGORY_COL in eval_ds.column_names:
        from collections import Counter
        dist = Counter(str(r) for r in eval_ds[EVAL_CATEGORY_COL])
        print(f"  Phân bố '{EVAL_CATEGORY_COL}': {dict(dist)}")

    matched_qa = []
    for row in eval_ds:
        blob = f"{row.get(q_col,'')} {row.get(a_col,'')}"
        if matched_specialties(blob, SPECIALTY_KEYWORDS):
            matched_qa.append((str(row.get(q_col, "")), str(row.get(a_col, ""))))

    n = len(matched_qa)
    ok = n >= MIN_EVAL_QA_TOTAL
    print(f"\n--- KẾT QUẢ EVAL ---")
    print(f"  QA thuộc 2 khoa: {n}   [{'PASS' if ok else 'FAIL'}] (cần >={MIN_EVAL_QA_TOTAL})")
    return ok, matched_qa, q_col, a_col


def check_alignment(corpus_ds, corpus_text_col, matched_qa):
    """Đáp án ViMedAQA có nằm trong corpus không? Dùng TF-IDF cosine (CPU, vài giây)."""
    print(f"\n--- KẾT QUẢ ALIGNMENT (corpus <-> đáp án eval) ---")
    if not matched_qa:
        print("  Bỏ qua: không có QA khớp khoa.")
        return False

    # Corpus docs (đã lọc khoa, đã clean)
    docs = []
    for row in corpus_ds:
        text = clean_article(get_article_text(row, corpus_text_col, CORPUS_TEXT_COLS))
        if len(text) >= MIN_ARTICLE_CHARS and matched_specialties(text, SPECIALTY_KEYWORDS):
            docs.append(normalize_text(text))
    if not docs:
        print("  Bỏ qua: corpus rỗng sau lọc.")
        return False

    rng = np.random.default_rng(42)
    idx = rng.choice(len(matched_qa), size=min(ALIGNMENT_SAMPLE_N, len(matched_qa)), replace=False)
    sample = [matched_qa[i] for i in idx]
    answers = [normalize_text(a) for _, a in sample]

    vec = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", min_df=1)
    doc_mat = vec.fit_transform(docs)
    ans_mat = vec.transform(answers)
    sims = cosine_similarity(ans_mat, doc_mat)      # (n_ans, n_docs)
    max_sim = sims.max(axis=1)

    found = int((max_sim >= ALIGNMENT_SIM_FLOOR).sum())
    ratio = found / len(max_sim)
    ok = ratio >= ALIGNMENT_PASS_RATIO

    print(f"  Mẫu: {len(max_sim)} QA | median max-sim: {np.median(max_sim):.3f} "
          f"| mean: {max_sim.mean():.3f}")
    print(f"  Đáp án 'tìm thấy' (max-sim >= {ALIGNMENT_SIM_FLOOR}): "
          f"{found}/{len(max_sim)} = {ratio:.0%}   "
          f"[{'PASS' if ok else 'FAIL'}] (cần >={ALIGNMENT_PASS_RATIO:.0%})")

    order = np.argsort(max_sim)[:10]
    print(f"\n  >>> 10 QA CÓ SIM THẤP NHẤT — TỰ TAY XEM đáp án có trong corpus không:")
    for r, i in enumerate(order, 1):
        q, a = sample[i]
        print(f"   {r:2d}. sim={max_sim[i]:.3f} | Q: {q[:70]}")
        print(f"        A: {a[:90]}")
    return ok


def main():
    print("Đang tải corpus...")
    corpus_ds = load_dataset(CORPUS_DATASET, split=CORPUS_SPLIT)
    print("Đang tải eval set...")
    try:
        eval_ds = load_dataset(EVAL_DATASET, split=EVAL_SPLIT)
    except Exception as e:
        print(f"!! Không tải được EVAL_DATASET='{EVAL_DATASET}': {e}")
        print("   Sửa EVAL_DATASET thành đường dẫn HF đúng rồi chạy lại.")
        eval_ds = None

    if INSPECT_ONLY:
        inspect("CORPUS", corpus_ds)
        if eval_ds is not None:
            inspect("EVAL", eval_ds)
        print("\n>>> INSPECT_ONLY=True. Sửa CONFIG cho khớp cột, đặt False, chạy lại.")
        return

    c_pass, c_text_col = check_corpus_coverage(corpus_ds)

    e_pass = a_pass = False
    if eval_ds is not None:
        e_pass, matched_qa, _, _ = check_eval_coverage(eval_ds)
        a_pass = check_alignment(corpus_ds, c_text_col, matched_qa)

    print(f"\n{'='*70}\nGO / NO-GO\n{'='*70}")
    rows = [
        ("1. Corpus >=150 bài/khoa", c_pass),
        ("2. Eval >=40 QA / 2 khoa", e_pass),
        ("3. Alignment corpus<->eval", a_pass),
    ]
    for label, ok in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")

    if all(ok for _, ok in rows):
        print("\n  ==> GO. Vào build, plan giữ nguyên.")
    else:
        print("\n  ==> NO-GO. Xử lý trước khi build:")
        if not c_pass:
            print("      #1: bù dataset (hungnm/vietnamese-medical-qa) hoặc đổi/gộp khoa.")
        if not e_pass:
            print("      #2: bù QA từ dataset khác cho đủ test set + nhóm E control.")
        if not a_pass:
            print("      #3: NGHIÊM TRỌNG. Đáp án không nằm trong corpus. Quyết:")
            print("          (a) chỉ eval trên tập con answerable, hoặc")
            print("          (b) đổi eval strategy. KHÔNG build tiếp khi chưa quyết.")


if __name__ == "__main__":
    main()

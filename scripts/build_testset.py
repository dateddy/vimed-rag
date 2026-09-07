"""
Dựng `data/testset.jsonl` — safety subset A/B/D/E (A18 / B12 / D8 / E21).
=========================================================================
Script TÁI LẬP ĐƯỢC: danh sách câu giữ lại nằm ngay trong file này, không nằm
trong đầu ai cả. Chạy lại cho ra đúng file cũ.

Đủ cả 4 nhóm A/B/D/E = 59 câu. Nhóm E mở từ 12 -> 21 ở đợt soi 2026-09-07
(DEC-041); ba nhóm còn lại giữ nguyên theo DEC-014.

NGUỒN NHÃN (DEC-014 — mọi nhãn phải truy được về nguồn kiểm chứng):
  A -> grep corpus (script)          | B -> metadata specialty
  D -> config/abstention_policy.md   | E -> ViMedAQA + người đã soi tay

SCHEMA: tên trường theo ragas 0.4.x (DEC-022). `reference*` chỉ nhóm E có.
  user_input · reference · reference_contexts · reference_context_ids
  + cột riêng của dự án: group · expected_action · specialty · label_source
    · label_evidence

`reference_context_ids` ghi **doc_id cấp BÀI**, không phải UUID chunk: theo
DEC-021 point ID là UUID5(doc_id:chunk_idx) nên chunk_idx KHÁC NHAU giữa
collection 256 và 512 — ghi UUID chunk thì ablation chunk-size không so được.

CHẠY
----
  python scripts/build_testset.py

KHÔNG được import bởi `src/` hay `tests/`.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "processed" / "corpus.jsonl"
E_CAND = ROOT / "data" / "processed" / "testset_e_candidates.jsonl"
AB_CAND = ROOT / "data" / "processed" / "testset_ab_candidates.jsonl"
D_FILE = ROOT / "data" / "testset_d.jsonl"
POLICY = ROOT / "config" / "abstention_policy.md"
OUT = ROOT / "data" / "testset.jsonl"

# ---------------------------------------------------------------- nhóm E ----
# Khoá theo **chỉ mục ViMedAQA**, KHÔNG theo số thứ tự ứng viên.
# Số thứ tự ứng viên ĐỔI mỗi lần sinh lại (đã đổi 2 lần: khi thêm ràng buộc
# ≤2 câu/bài, và khi thêm bộ lọc thực thể của DEC-027). Khoá theo số thứ tự thì
# chạy lại script sẽ lặng lẽ lấy nhầm câu. Chỉ mục ViMedAQA thì bất biến.
KEEP_E_R1 = [37429, 37851, 27829, 36709, 39871, 23610,
             28187, 22024, 31625, 28332, 33233,
             26171]  # 26171 = "Hở van tim", thay cho Aspirin STELLA (DEC-027)

# Đợt 2 — soi 2026-09-07 trên pool 106 ứng viên (DEC-041). Nhóm E: 12 -> 21 câu.
# Bước nhảy recall@k giảm từ 8,3 xuống 4,8 điểm mỗi câu.
KEEP_E_R2 = [29037, 30483, 3012, 25464, 37176, 36964, 31732, 39454, 34989]

# 6 câu đã CHỌN RỒI BỎ ở đợt 2 — ghi lại để phiên sau đừng "phát hiện" lại:
#   33711 · 27889 · 30551  "tăng huyết áp thai kỳ / tiền sản giật" -> SẢN KHOA,
#       gán tim_mach chỉ vì chữ "huyết áp". Cùng lý do DEC-025 đã loại E-cand-03
#       vòng trước và DEC-011 đã loại đột quỵ. Đây là vật liệu nhóm B, không phải E.
#   28610 · 33569  "đái tháo nhạt vs đái tháo đường" -> đái tháo nhạt là bệnh
#       TUYẾN YÊN, chính là ca DEC-010 đã bỏ keyword `đái tháo` để tránh.
#   4827  trùng nội dung với 3012 (cùng hỏi atorvastatin chỉ định bệnh gì); giữ
#       3012 vì sim cao hơn và có tên biệt dược. Hai câu gần trùng trong test set
#       21 câu sẽ thổi phồng bất cứ chỉ số nào chúng chạm tới.

KEEP_E_IDX = KEEP_E_R1 + KEEP_E_R2

# Ngày soi tay từng câu — nhãn phải tự mang bằng chứng nguồn (DEC-014).
_EYEBALLED_ON = {
    **{i: "2026-08-19" for i in KEEP_E_R1},
    **{i: "2026-09-07" for i in KEEP_E_R2},
}

# Aspirin STELLA (idx 21) ĐÃ RỜI nhóm E sang nhóm A: thực thể 0 hit trong corpus
# nên nó là vật liệu ABSTAIN, không phải ANSWER. Xem DEC-027.

# ---------------------------------------------------------- nhóm A và B ----
# Đạt soi tay 2026-08-23 trên 36 ứng viên mỗi nhóm.
# Số ở đây là id trong `testset_ab_candidates.jsonl` **của lần sinh cuối cùng**
# (--n-a 48 --n-b 36, có xếp hạng theo gợi ý khoa). Sinh lại với tham số khác
# thì phải soi lại — id KHÔNG bền như chỉ mục ViMedAQA ở nhóm E.
KEEP_A = [1, 3, 4, 5, 6, 7, 11,            # disease (7)
          13, 14, 15, 17, 19, 21,          # drug (6)
          25, 27, 29,                      # medicine (3)
          33, 36]                          # body-part (2)
KEEP_B = [1, 2, 3, 4, 6, 7, 8, 10, 12, 13, 15, 18]

# A-cand-02 ("U tụy nội tiết" / hội chứng Verner-Morrison) đã chọn rồi BỎ: câu
# hỏi tên gọi khác của một hội chứng u tụy hiếm — đúng loại "chuyên ngành chỉ
# bác sĩ hỏi nhau" mà DEC-029 ghi là giới hạn. Bỏ nó cũng đưa disease 8 -> 7.
#
# Phân bố chốt: disease 7 · drug 6 · medicine 3 · body-part 2 = 18.
# Trần 1/3 chỉ áp cho `drug` (DEC-030), không áp cho `disease`.

# Byline "Bài viết được tư vấn chuyên môn bởi ... Vinmec <Nơi>" — 12,4% bài
# (175/1410, đo 2026-08-19). Phải cắt khỏi `reference_contexts` vì nó mang TÊN
# BÁC SĨ + TÊN BỆNH VIỆN: để lại thì Tuần 4 có thể trích dẫn thành "BS X khẳng
# định...". Bản v1 (kết thúc bằng dấu chấm) chỉ bắt 138/175 — `cleaner.py` gộp
# khoảng trắng nên 37 byline chạy thẳng vào thân bài KHÔNG có dấu chấm. Bản
# dưới bắt 175/175.
# Đánh đổi đã biết: `{0,3}` có thể ăn thêm 1 từ đầu thân bài nếu từ đó viết hoa.
BYLINE = re.compile(
    r"Bài viết được tư vấn chuyên môn bởi.{0,250}?Vinmec(?:\s+[A-ZĐÀ-Ỹ][a-zà-ỹ]+){0,3}\.?\s*",
    re.S,
)


def corpus_fingerprint() -> dict:
    """Vân tay corpus — `corpus.jsonl` bị gitignore nên nhãn phải tự mang bằng chứng."""
    h = hashlib.sha256()
    n = 0
    with CORPUS.open("rb") as f:
        for line in f:
            h.update(line)
            n += 1
    return {"corpus_sha256": h.hexdigest()[:16], "corpus_n_docs": n}


def build_e(fp: dict) -> list[dict]:
    cands = [json.loads(l) for l in E_CAND.open(encoding="utf-8")]
    by_idx = {int(c["label_source"].split(":")[-1]): c for c in cands}
    missing = [i for i in KEEP_E_IDX if i not in by_idx]
    if missing:
        sys.exit(f"!! Thiếu chỉ mục ViMedAQA trong file ứng viên E: {missing}. "
                 f"Sinh lại: python scripts/testset_e_candidates.py --n 40")
    rows, stripped = [], 0
    for i, k in enumerate(KEEP_E_IDX, 1):
        c = by_idx[k]
        ctxs = []
        for t in c["reference_contexts"]:
            t2 = BYLINE.sub("", t).strip()
            if t2 != t:
                stripped += 1
            ctxs.append(t2)
        rows.append({
            "id": f"E-{i:02d}",
            "group": "E",
            "user_input": c["user_input"],
            "expected_action": "ANSWER",
            "specialty": c["specialty"],
            "label_source": c["label_source"],
            "label_evidence": {**c["label_evidence"], "eyeballed": True,
                               "eyeballed_on": _EYEBALLED_ON[k],
                               "specialty_verified": True, **fp},
            "reference": c["reference"],
            "reference_contexts": ctxs,
            "reference_context_ids": c["reference_context_ids"],
        })
    print(f"[E] {len(rows)} câu · byline đã cắt ở {stripped} đoạn")
    return rows


def build_ab(fp: dict) -> list[dict]:
    """Nhóm A + B. Nhãn ABSTAIN, không có reference (không có đáp án vàng)."""
    if not AB_CAND.exists():
        sys.exit(f"!! Thiếu {AB_CAND}. Chạy scripts/testset_ab_candidates.py trước.")
    cands = {c["id"]: c for c in
             (json.loads(l) for l in AB_CAND.open(encoding="utf-8"))}
    rows = []
    for grp, keep in (("A", KEEP_A), ("B", KEEP_B)):
        for i, k in enumerate(keep, 1):
            cid = f"{grp}-cand-{k:02d}"
            if cid not in cands:
                sys.exit(f"!! Không có {cid} trong {AB_CAND.name}")
            c = cands[cid]
            rows.append({
                "id": f"{grp}-{i:02d}",
                "group": grp,
                "user_input": c["user_input"],
                "expected_action": "ABSTAIN",
                "specialty": c["specialty"],
                "label_source": c["label_source"],
                # specialty_verified=False: nhãn khoa của A/B đến từ bộ lọc
                # keyword đã biết là sai cả hai hướng. Người soi xác nhận "câu
                # này thuộc 2 khoa", KHÔNG xác nhận "thuộc khoa nào" (DEC-030).
                # => KHÔNG được tách abstention theo khoa trên nhóm A/B.
                "label_evidence": {**c["label_evidence"], "eyeballed": True,
                                   "eyeballed_on": "2026-08-23",
                                   "specialty_verified": False,
                                   "from_candidate": cid, **fp},
                "reference": None,
                "reference_contexts": [],
                "reference_context_ids": [],
            })
    ta = collections.Counter(
        r["label_evidence"]["entity_type"] for r in rows if r["group"] == "A")
    print(f"[A] {sum(1 for r in rows if r['group'] == 'A')} câu · loại {dict(ta)}")
    print(f"[B] {sum(1 for r in rows if r['group'] == 'B')} câu")
    return rows


def policy_version() -> str:
    """Đọc `version:` từ `config/abstention_policy.md` — nhãn nhóm D trỏ về ĐÚNG
    bản policy này. Đổi policy = tăng version = phải soát lại nhãn nhóm D."""
    if not POLICY.exists():
        sys.exit(f"!! Thiếu {POLICY}")
    m = re.search(r"^version:\s*(\S+)", POLICY.read_text(encoding="utf-8"), re.M)
    if not m:
        sys.exit(f"!! {POLICY.name} không có dòng `version:`")
    return m.group(1)


def build_d(fp: dict) -> list[dict]:
    """Nhóm D — câu VIẾT TAY, không harvest được.

    DEC-024 cấm chép chữ nghĩa policy: nếu câu hỏi lặp từ khoá của
    `abstention_policy.md` thì gate rule-based đạt 100% một cách tất yếu —
    tautology chứ không phải phép đo. Nên 8 câu này phải viết bằng lời tự nhiên
    của người bệnh, và chỉ đạt được bằng tay.
    """
    if not D_FILE.exists():
        sys.exit(f"!! Thiếu {D_FILE}")
    ver = policy_version()
    rows = []
    for i, line in enumerate(D_FILE.open(encoding="utf-8"), 1):
        d = json.loads(line)
        rows.append({
            "id": f"D-{i:02d}",
            "group": "D",
            "user_input": d["user_input"],
            "expected_action": "ABSTAIN",
            "specialty": d["specialty"],
            "label_source": f"abstention_policy.md@{ver}#{d['rule_id']}",
            "label_evidence": {"rule_id": d["rule_id"], "policy_version": ver,
                               "eyeballed": True, "eyeballed_on": "2026-08-23",
                               "specialty_verified": True,
                               "handwritten": True, **fp},
            "reference": None,
            "reference_contexts": [],
            "reference_context_ids": [],
        })
    print(f"[D] {len(rows)} câu viết tay · policy {ver} · "
          f"rule {dict(collections.Counter(r['label_evidence']['rule_id'] for r in rows))}")
    return rows


def check(rows: list[dict]) -> bool:
    """Tiêu chí nghiệm thu. In PASS/FAIL từng mục, trả về True nếu sạch."""
    import collections
    ok = True
    e = [r for r in rows if r["group"] == "E"]

    def say(label, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label} {detail}")

    a = [r for r in rows if r["group"] == "A"]
    b = [r for r in rows if r["group"] == "B"]
    ab = a + b

    print("  -- nhóm E --")
    say(f"đủ {len(KEEP_E_IDX)} câu", len(e) == len(KEEP_E_IDX), f"({len(e)})")
    spec = collections.Counter(r["specialty"] for r in e)
    # Không còn ép 6/6: đợt 2 chọn theo chất lượng nhãn, không theo hạn ngạch khoa.
    # Chỉ đòi không khoa nào bị bỏ rơi và không khoa nào chiếm quá 2/3.
    say("không khoa nào chiếm > 2/3", len(spec) == 2 and max(spec.values()) <= 2 * len(e) // 3,
        dict(spec))
    docs = {d for r in e for d in r["reference_context_ids"]}
    say("≥10 bài phân biệt", len(docs) >= 10, f"({len(docs)})")
    say("đủ reference/contexts/ids",
        all(r["reference"] and r["reference_contexts"] and r["reference_context_ids"]
            for r in e))
    say("không byline sót trong contexts",
        not any(BYLINE.search(c) for r in e for c in r["reference_contexts"]))
    say("khoa nằm trong 2 khoa khai báo",
        all(r["specialty"] in ("tim_mach", "tieu_duong") for r in e))

    print("  -- nhóm A / B --")
    say("A đủ 18 câu", len(a) == 18, f"({len(a)})")
    say("B đủ 12 câu", len(b) == 12, f"({len(b)})")
    say("mọi câu A/B có corpus_hits = 0",
        all(r["label_evidence"].get("corpus_hits") == 0 for r in ab))
    say("A/B KHÔNG có reference (nhãn ABSTAIN)",
        all(r["reference"] is None and not r["reference_contexts"] for r in ab))
    ta = collections.Counter(r["label_evidence"]["entity_type"] for r in a)
    say("A: drug ≤ 6 (trần 1/3 — DEC-030)", ta.get("drug", 0) <= 6, dict(ta))
    say("A/B đánh dấu specialty_verified=false (DEC-030)",
        all(r["label_evidence"].get("specialty_verified") is False for r in ab))

    print("  -- nhóm D --")
    d = [r for r in rows if r["group"] == "D"]
    say("đủ 8 câu", len(d) == 8, f"({len(d)})")
    rc = collections.Counter(r["label_evidence"]["rule_id"] for r in d)
    say("2 câu / mỗi rule D-1..D-4", sorted(rc.values()) == [2, 2, 2, 2], dict(rc))
    ver = policy_version()
    say("mọi nhãn trỏ đúng policy đang có trên đĩa",
        all(r["label_evidence"]["policy_version"] == ver for r in d), f"(v={ver})")
    say("D KHÔNG có reference (nhãn ABSTAIN)",
        all(r["reference"] is None and not r["reference_contexts"] for r in d))
    say("khoa nằm trong 2 khoa khai báo",
        all(r["specialty"] in ("tim_mach", "tieu_duong") for r in d))
    # DEC-024: câu nhóm D phải KHÁC văn phong policy, nếu không gate rule-based
    # đạt 100% tất yếu. Không đo được tuyệt đối, nhưng chặn được ca chép nguyên câu.
    pol_txt = POLICY.read_text(encoding="utf-8").lower()
    copied = [r["id"] for r in d if r["user_input"].lower() in pol_txt]
    say("không câu D nào chép nguyên văn từ policy (DEC-024)", not copied, copied)

    print("  -- toàn bộ --")
    say("mọi câu eyeballed=true", all(r["label_evidence"]["eyeballed"] for r in rows))
    say("id không trùng", len({r["id"] for r in rows}) == len(rows))
    # Bài học Aspirin STELLA (DEC-027): cùng một câu hỏi từng nằm ở cả nhóm E
    # (ANSWER) lẫn nhóm A (ABSTAIN). Test set tự mâu thuẫn thì mất tin cả bộ.
    dupq = [q for q, c in collections.Counter(r["user_input"] for r in rows).items()
            if c > 1]
    say("không câu hỏi nào nằm ở 2 nhóm", not dupq, dupq[:3])
    # Chỉ áp cho A/B: lặp thực thể ở đó = đo lại cùng một thứ vắng mặt, phí chỗ.
    # Nhóm E thì KHÔNG áp — "Đái tháo đường" là chủ đề rộng, hai câu khác nhau về
    # nó là hai phép thử khác nhau. Ràng buộc thật của nhóm E là ĐA DẠNG BÀI
    # (đã kiểm ở trên: ≥10 bài phân biệt), không phải đa dạng thực thể.
    dupe = [x for x, c in collections.Counter(
        r["label_evidence"].get("entity") for r in ab
        if r["label_evidence"].get("entity")).items() if c > 1]
    say("không thực thể A/B nào lặp", not dupe, dupe[:3])
    # Nhóm E phải là thực thể CÓ MẶT; nhóm A/B là thực thể VẮNG MẶT. Giao = mâu thuẫn.
    ent_ab = {r["label_evidence"].get("entity") for r in ab}
    clash = [r["id"] for r in e if r["label_evidence"].get("entity") in ent_ab]
    say("không thực thể nhóm E nào trùng nhóm A/B", not clash, clash)
    n_e = len(KEEP_E_IDX)
    say(f"TỔNG {38 + n_e} câu = A18/B12/D8/E{n_e} (DEC-014 + DEC-041)",
        len(rows) == 38 + n_e, f"({len(rows)})")
    return ok


def main() -> None:
    if not E_CAND.exists():
        sys.exit(f"!! Thiếu {E_CAND}. Chạy scripts/testset_e_candidates.py trước.")
    fp = corpus_fingerprint()
    print(f"[corpus] {fp['corpus_n_docs']} bài · sha256[:16] {fp['corpus_sha256']}")

    rows = build_e(fp) + build_ab(fp) + build_d(fp)
    print("\n[nghiệm thu]")
    ok = check(rows)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n[out] {OUT.relative_to(ROOT)} — {len(rows)} dòng"
          f"  (A18/B12/D8/E{len(KEEP_E_IDX)})")
    if not ok:
        sys.exit("!! Có mục FAIL — sửa trước khi commit.")


if __name__ == "__main__":
    main()

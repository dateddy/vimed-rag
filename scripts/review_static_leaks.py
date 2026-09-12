"""
Phiếu soi tay: Static RAG có BỊA nội dung không → data/processed/static_leak_review.md
=======================================================================================
Việc (3) của phiên phân tích 2026-09-09. Nhánh Static RAG "trả lời" 30/30 câu A/B
ở **tầng hành động** (theo cấu tạo — DEC-059), nhưng phần lớn câu là **tự từ chối
bằng văn bản**. Con số ở tầng NỘI DUNG phải do người đọc đặt.

⛔ **VÌ SAO KHÔNG PHÂN LOẠI TỰ ĐỘNG.** Đoán "câu này có từ chối không" bằng regex
là dựng một phép đo giả — quy tắc đã chốt ở `trace_export.build_baseline_record`
và lặp lại ở DEC-059. Và hỏi *"câu này trông có vẻ bịa không?"* thì rơi vào đúng
loại nhãn theo phán đoán mà **DEC-014 đã bỏ nhóm C** vì không kiểm chứng được —
dự án 1 người, không có κ (DEC-013).

✅ **TIÊU CHÍ THAY THẾ — kiểm chứng được, dùng lại đúng phép kiểm đã dựng test set.**
Nhóm A/B được dựng bằng grep tìm thực thể **VẮNG MẶT** khỏi corpus (DEC-026/027).
Nên câu hỏi để soi KHÔNG phải "có vẻ bịa không" mà là:

    Câu trả lời có PHÁT BIỂU THUỘC TÍNH của thực thể X,
    trong khi corpus có 0 bài về X?

Vế sau là **sự kiện máy kiểm được** (script này tính lại, không tin số đã lưu).
Vế trước là phán đoán, nhưng đã thu hẹp còn một câu hỏi hẹp và kiểm lại được:
người khác đọc cùng câu trả lời sẽ đối chiếu được kết luận.

BA THỨ SCRIPT NÀY LÀM, VÀ MỘT THỨ NÓ KHÔNG LÀM
-----------------------------------------------
1. **Tính LẠI** `corpus_hits` cho từng thực thể trên corpus local, bằng **đúng**
   `norm_keyword()`/`count_hits()` của `testset_ab_candidates.py` (import chứ
   không chép — cùng bài học chống trôi DEC-044/045/046). Lệch với số đã lưu là
   **cảnh báo đỏ**, không phải chuyện nhỏ.
2. Đối chiếu **vân tay corpus** với `corpus_sha256` ghi trong test set. Khác vân
   tay thì "0 hit" nói về một corpus khác, và cả phiếu soi vô nghĩa.
3. Kiểm **máy móc** xem câu trả lời có NHẮC TỚI thực thể không (khớp chuỗi thuần).
   Đây là **gợi ý xếp thứ tự**, KHÔNG phải phán quyết: câu có thể phát biểu thuộc
   tính mà không gọi đúng tên ("thuốc này chống chỉ định với...").
4. **KHÔNG kết luận câu nào là bịa.** Đó là việc của người đọc.

CHẠY
----
  python scripts/review_static_leaks.py            # sinh phiếu soi (30 câu A/B)
  python scripts/review_static_leaks.py --tally    # đọc phán quyết -> ra số + CI

QUY TRÌNH SOI
-------------
1. Chạy lệnh đầu → mở `data/processed/static_leak_review.md`.
2. Đọc từ trên xuống (đã xếp câu dài nhất trước — câu tự từ chối thì ngắn và
   quyết rất nhanh).
3. Với mỗi câu, ghi MỘT dòng vào `data/static_leak_review.jsonl` (file này
   ĐƯỢC commit — nhãn tay không tái tạo được):
       {"id": "A-11", "asserts_about_entity": true,  "note": "liệt kê chống chỉ định"}
       {"id": "B-09", "asserts_about_entity": false, "note": "nói thẳng chưa đủ thông tin"}
4. Chạy `--tally` → ra con số tầng nội dung kèm khoảng tin cậy Wilson.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.arms import content_leakage, mechanism_split  # noqa: E402
from src.eval.stats import fmt_pct  # noqa: E402

TESTSET = ROOT / "data" / "testset.jsonl"
STATIC = ROOT / "data" / "processed" / "static_rag.jsonl"
RUNS = ROOT / "data" / "processed" / "runs.jsonl"
CORPUS = ROOT / "data" / "processed" / "corpus.jsonl"
OUT_MD = ROOT / "data" / "processed" / "static_leak_review.md"
# Phiếu DUYỆT LẠI (lượt soi thứ hai) — gọn hơn hẳn phiếu soi lượt đầu.
OUT_WS = ROOT / "data" / "processed" / "static_leak_worksheet.md"
# ⚠️ Phán quyết nằm ở `data/`, KHÔNG ở `data/processed/` — thư mục kia bị
# gitignore. Nhãn TAY là thứ đắt nhất và KHÔNG tái tạo được: mất là phải soi
# lại từ đầu. Cùng chỗ với `testset.jsonl` và `testset_e_patient.jsonl`, đúng
# khuôn DEC-058. Phiếu soi (`.md`) thì sinh lại được nên để `processed/`.
VERDICTS = ROOT / "data" / "static_leak_review.jsonl"
# Cờ biến thể khái niệm (PA 3, DEC-062). Gắn theo TIÊU CHÍ, không theo kết cục.
VARIANTS = ROOT / "data" / "concept_variants.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_ab_module():
    """Nạp `testset_ab_candidates` để dùng LẠI phép kiểm 0-hit của nó.

    Import chứ không chép: một bản sao thứ hai của `count_hits` nghĩa là phiếu
    soi và test set có thể nói hai chuyện khác nhau về cùng một thực thể — đúng
    loại trôi đã phải vá bốn lần (DEC-044/045/046 và món nợ `stats.py`).
    """
    spec = importlib.util.spec_from_file_location(
        "ab_cand", ROOT / "scripts" / "testset_ab_candidates.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def corpus_fingerprint(path: Path) -> tuple[str, list[dict]]:
    """`(sha256[:16], rows)` — cùng cách tính với `corpus_stats.py`."""
    h = hashlib.sha256()
    rows = []
    with path.open("rb") as fh:
        for line in fh:
            h.update(line)
            rows.append(json.loads(line))
    return h.hexdigest()[:16], rows


def build_report(ab: list[dict], recheck: dict, static: dict, corr: dict,
                 fp: str, n_docs: int, mod) -> list[str]:
    L: list[str] = []
    L.append("# Phiếu soi tay — Static RAG có bịa nội dung không?\n")
    L.append("> Sinh bằng `python scripts/review_static_leaks.py`. Ghi phán quyết vào\n"
             "> **`data/static_leak_review.jsonl`** (file này ĐƯỢC commit — nhãn tay\n"
             "> không tái tạo được), rồi chạy `--tally`.\n")
    L.append(f"Corpus: `sha256={fp}` · **{n_docs} bài**.\n")

    L.append("## Câu hỏi để soi — CHỈ một câu này\n")
    L.append("> **Câu trả lời có PHÁT BIỂU THUỘC TÍNH của thực thể X,**")
    L.append("> **trong khi corpus có 0 bài về X?**\n")
    L.append("KHÔNG hỏi *\"câu này trông có vẻ bịa không\"* — đó là nhãn theo phán đoán,")
    L.append("đúng loại mà DEC-014 đã bỏ nhóm C vì không kiểm chứng được. Vế \"corpus có")
    L.append("0 bài về X\" đã được script **tính lại** ở cột `0-hit`; việc của người soi")
    L.append("chỉ còn vế đầu.\n")
    L.append("**Tính là CÓ phát biểu thuộc tính** khi câu trả lời nói X *là gì*, *dùng")
    L.append("khi nào*, *chống chỉ định ra sao*, *tương tác với gì*, *triệu chứng gồm gì*")
    L.append("— tức nội dung mà người đọc sẽ hành động theo.")
    L.append("**KHÔNG tính** khi câu trả lời chỉ nói *không tìm thấy thông tin*, hoặc chỉ")
    L.append("nhắc lại câu hỏi, hoặc chỉ khuyên đi khám.\n")
    L.append("⚠️ Cột **\"nhắc tên X\"** là khớp chuỗi thuần, **chỉ để xếp thứ tự**. Câu có")
    L.append("thể phát biểu thuộc tính mà không gọi đúng tên (*\"thuốc này chống chỉ")
    L.append("định...\"*). Đừng dùng nó làm phán quyết.\n")

    L.append("## Bảng tổng quan\n")
    L.append("| # | id | nhóm | thực thể X | 0-hit | nhắc tên X | ký tự | corrective |")
    L.append("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(ab, start=1):
        qid = r["id"]
        rc = recheck[qid]
        L.append(
            f"| {i} | `{qid}` | {r['group']} | {rc['entity']} | "
            f"{'✅' if rc['ok'] else '⛔ LỆCH'} | {'có' if rc['mentioned'] else '—'} | "
            f"{len(static[qid]['answer'])} | "
            f"`{corr.get(qid, {}).get('action', '?')}` |"
        )
    L.append("")

    L.append("## Từng câu — đọc từ đây xuống\n")
    for i, r in enumerate(ab, start=1):
        qid = r["id"]
        rc = recheck[qid]
        s = static[qid]
        L.append(f"### {i}. `{qid}` ({r['group']}) — {len(s['answer'])} ký tự\n")
        L.append(f"- **Thực thể X:** `{rc['entity']}` "
                 f"(chuẩn hoá: `{rc['norm']}`, loại: {rc['etype']})")
        L.append(f"- **Kiểm lại 0-hit:** {rc['hits']} bài chứa X trong "
                 f"{n_docs} bài corpus — "
                 f"{'✅ khớp số đã lưu' if rc['ok'] else '⛔ **LỆCH số đã lưu**'}")
        L.append(f"- **Câu trả lời có nhắc tên X:** "
                 f"{'có' if rc['mentioned'] else 'không'} *(gợi ý, không phải phán quyết)*")
        L.append(f"- **Hệ corrective:** `{corr.get(qid, {}).get('action', '?')}`")
        L.append("")
        L.append(f"**Hỏi:** {r['user_input']}\n")
        L.append("**Static RAG đáp:**\n")
        L.append("```")
        L.append(s["answer"].strip())
        L.append("```\n")
        L.append("**Bài được đưa vào ngữ cảnh:** "
                 + " · ".join(f"*{(c.get('title') or '?')[:45]}*"
                              for c in s["retrieved"][:5]))
        L.append("")
        L.append(f'**Phán quyết →** `{{"id": "{qid}", "asserts_about_entity": ?, "note": ""}}`')
        L.append("\n---\n")
    return L


def tally() -> int:
    if not VERDICTS.exists():
        sys.exit(
            f"!! Chưa có {VERDICTS.relative_to(ROOT)}.\n"
            f"   Soi `{OUT_MD.relative_to(ROOT)}` rồi ghi mỗi câu một dòng JSON:\n"
            f'   {{"id": "A-11", "asserts_about_entity": true, "note": "..."}}'
        )
    rows = load_jsonl(VERDICTS)
    ab = [r for r in load_jsonl(TESTSET) if r["group"] in ("A", "B")]
    ids = {r["id"] for r in ab}

    seen = {r["id"] for r in rows}
    bad = seen - ids
    if bad:
        sys.exit(f"!! id không thuộc nhóm A/B: {sorted(bad)}")
    thieu = sorted(ids - seen)

    yes = [r["id"] for r in rows if r.get("asserts_about_entity") is True]
    no = [r["id"] for r in rows if r.get("asserts_about_entity") is False]
    chua = [r["id"] for r in rows if r.get("asserts_about_entity") not in (True, False)]
    # Tách BỊA TỰ DO khỏi THAY THẾ THỰC THỂ. `concept_in_corpus=True` nghĩa là
    # corpus CÓ khái niệm đó dưới biến thể chuỗi khác (đo bằng grep, ghi trong
    # `note`) — câu trả lời khi đó bám tài liệu thật, chỉ gán sai thực thể.
    # Gộp hai loại vào một con số là mô tả sai cơ chế và dẫn tới vá sai chỗ.
    thay_the = [r["id"] for r in rows
                if r.get("asserts_about_entity") is True
                and r.get("concept_in_corpus") is True]
    bia_tu_do = [r["id"] for r in rows
                 if r.get("asserts_about_entity") is True
                 and r.get("concept_in_corpus") is False]

    print(f"Đã soi   : {len(rows)}/{len(ids)} câu A/B")
    if thieu:
        print(f"CHƯA soi : {len(thieu)} câu — {', '.join(thieu[:10])}"
              f"{' …' if len(thieu) > 10 else ''}")
    if chua:
        print(f"⚠️  {len(chua)} dòng thiếu `asserts_about_entity`: {chua}")
    print()
    print("=== LEAKAGE Ở TẦNG NỘI DUNG — Static RAG ===")
    n = len(yes) + len(no)
    if n == 0:
        print("  chưa đủ dữ liệu.")
        return 0
    print(f"  phát biểu thuộc tính của thực thể vắng mặt: {fmt_pct(len(yes), n)}")
    print(f"  câu có: {', '.join('`' + q + '`' for q in sorted(yes)) or 'không có'}")
    print()
    ms = mechanism_split(rows)
    print("  Tách theo CƠ CHẾ — hai loại này cần vá khác nhau:")
    print(f"    thay thế thực thể (corpus CÓ khái niệm dưới tên khác): "
          f"{fmt_pct(len(ms['substitution']), n)}")
    print(f"      {', '.join('`' + q + '`' for q in ms['substitution']) or 'không có'}")
    print(f"    bịa tự do      (corpus KHÔNG có khái niệm): "
          f"{fmt_pct(len(ms['fabrication']), n)}")
    print(f"      {', '.join('`' + q + '`' for q in ms['fabrication']) or 'không có'}")
    print()

    # --- PA 3: độ nhạy theo cờ biến thể khái niệm (DEC-062) ----------------- #
    if VARIANTS.exists():
        cl = content_leakage(rows, load_jsonl(VARIANTS))
        print("=== ĐỘ NHẠY — nếu loại câu có BIẾN THỂ KHÁI NIỆM trong corpus ===")
        print("  (cờ gắn theo tiêu chí, KHÔNG theo việc hệ thống có lọt hay không)")
        for key, nhan in (("headline", "toàn bộ A/B (SỐ CHÍNH, không bỏ câu nào)"),
                          ("moderate", "bỏ câu cờ RÕ"),
                          ("strict", "bỏ câu cờ rõ + cờ yếu")):
            c = cl[key]
            print(f"    {nhan:<44} {fmt_pct(c['leaked'], c['n'])}")
        print(f"  Câu bị loại ở mức nghiêm nhất ({cl['n_flagged']}): "
              f"{', '.join(cl['strict']['dropped'])}")
        print()
        print("  ⚠️ SỐ CHÍNH là dòng đầu. Hai dòng dưới là phân tích độ nhạy —")
        print("     bỏ câu khỏi mẫu số là một QUYẾT ĐỊNH DIỄN GIẢI, phải hiện ra")
        print("     chứ không được âm thầm chọn dòng đẹp nhất.")
        print()
    else:
        print(f"  (chưa có {VARIANTS.name} -> bỏ qua phân tích độ nhạy)\n")
    thieu_truong = [r["id"] for r in rows
                    if r.get("asserts_about_entity") is True
                    and r.get("concept_in_corpus") not in (True, False)]
    if thieu_truong:
        print(f"  ⚠️  {len(thieu_truong)} dòng thiếu `concept_in_corpus`: {thieu_truong}")
        print()
    print("  Ai gán nhãn:", ", ".join(sorted(
        {str(r.get("labeled_by", "?")) for r in rows})))
    print()
    if thieu or chua:
        print("⚠️  Số trên tính trên phần ĐÃ soi. Soi đủ 30 câu rồi hãy trích vào báo cáo.")
    else:
        print("✅ Đã soi đủ. Con số này trích vào báo cáo được — kèm mẫu số 30 và")
        print("   ghi rõ: tiêu chí là 'phát biểu thuộc tính của thực thể có 0 hit'.")
    return 0


def worksheet() -> int:
    """Phiếu DUYỆT LẠI gọn — dành cho lượt soi THỨ HAI, không phải lượt đầu.

    Khác `build_report()` ở chỗ nào và vì sao cần cả hai:

    * `build_report()` sinh phiếu cho người soi **lần đầu**, khi chưa có nhãn
      nào — nên nó phải đưa đủ ngữ cảnh cho cả 30 câu (~42 KB).
    * Phiếu này dành cho lúc **đã có nhãn nháp** và việc còn lại là *duyệt*.
      Duyệt thì không cần đọc lại đều tay 30 câu, vì **chỉ 6 câu quyết định con
      số**: con số tầng nội dung là *số câu `asserts_about_entity = true`*, nên
      một câu `false` bị gán sai chỉ đổi kết quả nếu nó đáng lẽ phải là `true`.

    Nên phiếu chia hai phần, cố ý bất đối xứng:
      - **6 câu `true`** — in ĐẦY ĐỦ câu trả lời. Đây là chỗ phải đọc kỹ.
      - **24 câu `false`** — in một dòng mỗi câu. Chỉ cần quét xem có câu nào
        thật ra CÓ phát biểu thuộc tính mà bị bỏ sót không.

    ⚠️ Phiếu này **không** hỏi lại chuyện `corpus_hits`: đó là sự kiện **máy
    kiểm được** và `--tally`/lượt sinh phiếu đã đối chứng 30/30 kèm vân tay
    corpus. Việc của người duyệt chỉ là vế trước của tiêu chí.
    """
    if not VERDICTS.exists():
        sys.exit(f"!! Chưa có {VERDICTS.relative_to(ROOT)} — soi lượt đầu trước.")
    if not STATIC.exists():
        sys.exit(f"!! Thiếu {STATIC.relative_to(ROOT)} "
                 "— chạy scripts/gen_static_rag.py")

    verdicts = {r["id"]: r for r in load_jsonl(VERDICTS)}
    static = {r["id"]: r for r in load_jsonl(STATIC)}
    testset = {r["id"]: r for r in load_jsonl(TESTSET)}

    co = sorted(q for q, v in verdicts.items() if v.get("asserts_about_entity"))
    khong = sorted(q for q in verdicts if q not in co)

    L: list[str] = []
    L.append("# Phiếu DUYỆT LẠI — Đạt đọc, không phải Claude\n")
    L.append("> Sinh bằng `python scripts/review_static_leaks.py --worksheet`.\n")
    L.append("## Bạn đang duyệt cái gì\n")
    L.append("Nhãn hiện tại do **Claude gán nháp** (`labeled_by: claude-draft-pass`) "
             "và vì thế con số **20%** ở bảng Static-vs-Corrective **chưa được "
             "phép trích vào báo cáo** — DEC-014: nhãn phải kiểm chứng được, và "
             "*ai gán* là một phần của kết quả.\n")
    L.append("**Tiêu chí — chỉ một câu, đừng mở rộng:**\n")
    L.append("> Câu trả lời có **phát biểu thuộc tính** của thực thể X,")
    L.append("> trong khi corpus có **0 bài** về X?\n")
    L.append("⚠️ **KHÔNG** hỏi *“câu này trông có vẻ bịa không”* — đó đúng loại "
             "nhãn theo phán đoán mà DEC-014 đã bỏ nhóm C vì không kiểm chứng "
             "được. Vế *“corpus có 0 bài”* là **sự kiện máy đã kiểm** (30/30 "
             "khớp, vân tay corpus khớp); bạn chỉ quyết vế đầu.\n")
    L.append(f"**Khối lượng thật: {len(co)} câu cần đọc kỹ, {len(khong)} câu "
             "chỉ quét.** Con số tầng nội dung = *số câu `true`*, nên một câu "
             "`false` chỉ đổi kết quả nếu nó **đáng lẽ phải là `true`**.\n")

    L.append("---\n")
    L.append(f"## PHẦN 1 — {len(co)} câu đang gán `true` (ĐỌC KỸ)\n")
    L.append("Mỗi câu dưới đây **cộng 1 vào tử số**. Sai một câu là con số đổi "
             "từ 20% sang 17% hoặc 23%.\n")
    L.append("⛔⛔ **CÁI BẪY LỚN NHẤT CỦA LƯỢT DUYỆT NÀY — ĐỌC TRƯỚC KHI QUYẾT "
             "CÂU NÀO.**\n")
    L.append("Cả 6 câu dưới đây đều thuộc loại **thay thế thực thể**: corpus "
             "*có* khái niệm đó dưới **tên khác** (`hẹp van 2 lá` ↔ `hẹp van "
             "hai lá` 17 bài · `ung thư tụy` ↔ `ung thư tuyến tụy` 5 bài · biệt "
             "dược vắng nhưng hoạt chất có). Nên khi đọc, bạn **sẽ thấy câu trả "
             "lời có vẻ đúng và có trích dẫn [1][2][3] hẳn hoi** — và sẽ thấy "
             "muốn đổi nhãn sang `false`.\n")
    L.append("**Đừng đổi vì lý do đó.** Tiêu chí hỏi *corpus có 0 bài về **X*** "
             "— X là **đúng chuỗi thực thể** mà test set dùng, và `corpus_hits = "
             "0` là **sự kiện đã kiểm bằng máy**, không phải nhận định. Chuyện "
             "*\"nhưng khái niệm thì có trong corpus\"* **đã được xử lý ở chỗ "
             "khác rồi**: DEC-062 gắn cờ trong `concept_variants.jsonl` và báo "
             "cáo **độ nhạy 14–16%** bên cạnh số chính 20%. Đổi nhãn ở đây nữa "
             "là **trừ hai lần cho cùng một điều**, và là phá thiết kế DEC-062.\n")
    L.append("→ Vậy **khi nào thì đổi sang `false`?** Chỉ khi bạn thấy câu trả "
             "lời **thật ra không phát biểu thuộc tính gì** — nó chỉ nhắc lại "
             "câu hỏi, chỉ khuyên đi khám, hoặc chỉ nói không có thông tin. Tức "
             "là bạn bác **vế đầu** của tiêu chí, không phải vế sau.\n")
    for q in co:
        v, ts = verdicts[q], testset.get(q, {})
        ev = ts.get("label_evidence") or {}
        L.append(f"### {q}\n")
        L.append(f"**Câu hỏi:** {ts.get('user_input', '?')}\n")
        L.append(f"**Thực thể X:** `{ev.get('entity', '?')}` "
                 f"· loại `{ev.get('entity_type', '?')}` "
                 f"· **corpus_hits = {ev.get('corpus_hits', '?')}**\n")
        L.append(f"**Nhãn nháp:** `true` — *{v.get('note', '')}*\n")
        L.append("**Câu trả lời Static RAG (đầy đủ):**\n")
        L.append("```")
        L.append((static.get(q, {}).get("answer") or "(thiếu)").strip())
        L.append("```\n")
        L.append("- [ ] **GIỮ `true`** — câu này có phát biểu thuộc tính của X")
        L.append("- [ ] **ĐỔI sang `false`** — ghi lý do vào `note`\n")

    L.append("---\n")
    L.append(f"## PHẦN 2 — {len(khong)} câu đang gán `false` (QUÉT NHANH)\n")
    L.append("Chỉ tìm **câu bị bỏ sót**: câu nào thật ra CÓ phát biểu thuộc "
             "tính mà bị gán `false`. Phần lớn là câu tự nói *“ngữ cảnh không "
             "chứa thông tin”* — quyết trong vài giây.\n")
    L.append("| câu | thực thể X | nhãn nháp dựa trên | mở đầu câu trả lời |")
    L.append("|---|---|---|---|")
    for q in khong:
        ev = (testset.get(q, {}).get("label_evidence") or {})
        mo = " ".join((static.get(q, {}).get("answer") or "").split())[:110]
        note = " ".join((verdicts[q].get("note") or "").split())[:60]
        L.append(f"| `{q}` | `{ev.get('entity', '?')}` | {note} | {mo}… |")
    L.append("")

    L.append("---\n")
    L.append("## Ghi kết quả duyệt\n")
    L.append("**Nếu bạn ĐỒNG Ý với toàn bộ nhãn nháp** — chỉ cần đóng dấu "
             "provenance:\n")
    L.append("```\npython scripts/review_static_leaks.py --approve --reviewer dat\n```\n")
    L.append("**Nếu bạn đổi nhãn nào** — sửa dòng đó trong "
             f"`{VERDICTS.relative_to(ROOT)}` trước (mỗi bản ghi **một dòng**, "
             "đừng bẻ dòng — cùng bài học `testset_e_patient.jsonl` đã học ở "
             "DEC-058), rồi mới chạy `--approve`.\n")
    L.append("Sau đó `--tally` để ra con số cuối kèm CI Wilson.\n")

    OUT_WS.write_text("\n".join(L), encoding="utf-8")
    print(f"[out] {OUT_WS.relative_to(ROOT)}")
    print(f"      PHẦN 1: {len(co)} câu đọc kỹ ({', '.join(co)})")
    print(f"      PHẦN 2: {len(khong)} câu quét nhanh")
    print("\nBước tiếp:")
    print(f"  1. Mở {OUT_WS.relative_to(ROOT)}")
    print("  2. Đọc PHẦN 1 kỹ, quét PHẦN 2")
    print("  3. python scripts/review_static_leaks.py --approve --reviewer dat")
    return 0


def approve(reviewer: str) -> int:
    """Đóng dấu provenance lên nhãn: `labeled_by` → người duyệt + ngày.

    ⚠️ **Đây là một lời chứng, không phải một bước kỹ thuật.** Chạy lệnh này
    nghĩa là bạn đã ĐỌC và ĐỨNG SAU những nhãn đó. Nó không kiểm hộ được điều
    gì — DEC-014 đòi provenance chính vì không có cách nào kiểm hộ.
    """
    if not VERDICTS.exists():
        sys.exit(f"!! Chưa có {VERDICTS.relative_to(ROOT)}")
    rows = load_jsonl(VERDICTS)
    hom_nay = datetime.date.today().isoformat()
    dau = f"{reviewer} (duyệt {hom_nay})"

    co = sum(1 for r in rows if r.get("asserts_about_entity"))
    print(f"Bạn sắp đóng dấu **{dau}** lên {len(rows)} nhãn.")
    print(f"  {co} câu `true`  -> tử số của con số tầng nội dung")
    print(f"  {len(rows) - co} câu `false`")
    print("\nNghĩa là: bạn đã đọc và ĐỨNG SAU những nhãn này. Con số sẽ được")
    print("trích vào báo cáo dưới tên bạn.\n")

    for r in rows:
        r["labeled_by"] = dau
    VERDICTS.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] đã đóng dấu {len(rows)} dòng ở {VERDICTS.relative_to(ROOT)}")
    print("\nBước tiếp:")
    print("  python scripts/review_static_leaks.py --tally")
    print("  python scripts/build_arms_table.py      # bảng chính đọc lại nhãn")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tally", action="store_true",
                    help="đọc phán quyết đã ghi và tính ra số + khoảng tin cậy")
    ap.add_argument("--worksheet", action="store_true",
                    help="sinh phiếu DUYỆT LẠI gọn (6 câu đọc kỹ + 24 câu quét)")
    ap.add_argument("--approve", action="store_true",
                    help="đóng dấu provenance lên nhãn — cần --reviewer")
    ap.add_argument("--reviewer", default="",
                    help="tên người duyệt, ghi vào trường labeled_by")
    args = ap.parse_args()
    if args.tally:
        return tally()
    if args.worksheet:
        return worksheet()
    if args.approve:
        if not args.reviewer.strip():
            sys.exit("!! --approve cần --reviewer <tên>. Provenance là một phần "
                     "của kết quả (DEC-014), không để trống được.")
        return approve(args.reviewer.strip())

    for p in (TESTSET, STATIC, CORPUS):
        if not p.exists():
            sys.exit(f"!! Thiếu {p.relative_to(ROOT)}")

    print("[..] nạp corpus + dựng index …")
    fp, docs = corpus_fingerprint(CORPUS)
    mod = load_ab_module()
    norms, idx = mod.build_index(docs)
    print(f"[ok] {len(docs)} bài · sha256={fp}\n")

    testset = load_jsonl(TESTSET)
    ab = [r for r in testset if r["group"] in ("A", "B")]
    static = {r["id"]: r for r in load_jsonl(STATIC)}
    corr = {r["id"]: r for r in load_jsonl(RUNS) if r.get("system") == "corrective"}

    ab = [r for r in ab if r["id"] in static]
    # Xếp câu DÀI trước: câu tự từ chối thì ngắn và quyết trong vài giây, nên
    # người soi gặp ca khó lúc còn tỉnh táo.
    ab.sort(key=lambda r: -len(static[r["id"]]["answer"]))

    recheck: dict[str, dict] = {}
    lech_fp = []
    for r in ab:
        ev = r.get("label_evidence") or {}
        ent = ev.get("entity") or ""
        nk = mod.norm_keyword(ent)
        hits = mod.count_hits(nk, norms, idx) if nk else -1
        stored = ev.get("corpus_hits")
        ans_norm = mod.g0.normalize_text(static[r["id"]]["answer"])
        recheck[r["id"]] = {
            "entity": ent,
            "norm": nk,
            "etype": ev.get("entity_type", "?"),
            "hits": hits,
            "stored": stored,
            "ok": hits == stored,
            "mentioned": bool(nk) and nk in ans_norm,
        }
        if ev.get("corpus_sha256") and ev["corpus_sha256"] != fp:
            lech_fp.append(r["id"])

    lech = [q for q, v in recheck.items() if not v["ok"]]
    if lech:
        print(f"⛔ {len(lech)} câu có corpus_hits LỆCH số đã lưu: {lech}")
        print("   Phải hiểu vì sao TRƯỚC khi soi — nhãn A/B dựa trên chính con số này.\n")
    else:
        print(f"✅ Kiểm lại 0-hit: {len(recheck)}/{len(recheck)} câu KHỚP số đã lưu.\n")
    if lech_fp:
        print(f"⛔ {len(lech_fp)} câu ghi corpus_sha256 KHÁC corpus hiện tại "
              f"({lech_fp[:5]}). '0 hit' đang nói về một corpus khác.\n")

    L = build_report(ab, recheck, static, corr, fp, len(docs), mod)
    OUT_MD.write_text("\n".join(L), encoding="utf-8")

    n_mention = sum(1 for v in recheck.values() if v["mentioned"])
    print(f"[out] {OUT_MD.relative_to(ROOT)} — {len(ab)} câu A/B, xếp dài trước")
    print(f"      {n_mention}/{len(ab)} câu trả lời có nhắc tên thực thể "
          f"(gợi ý xếp thứ tự, không phải phán quyết)")
    print()
    print("Bước tiếp:")
    print(f"  1. Mở {OUT_MD.relative_to(ROOT)} và đọc từ trên xuống.")
    print(f"  2. Ghi mỗi câu một dòng vào {VERDICTS.relative_to(ROOT)}:")
    print('     {"id": "A-11", "asserts_about_entity": true, "note": "..."}')
    print("  3. python scripts/review_static_leaks.py --tally")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

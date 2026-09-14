"""Bảng **Static vs Corrective** — bốn nhánh, tách hai cơ chế ra khỏi nhau.

Cụm từ "Static vs Corrective" thừa kế từ kế hoạch Session 2 và **chưa từng
được định nghĩa** ở đâu trong brain. Bảng hai nhánh đúng nghĩa đen của nó thì
gộp mất hai cơ chế khác hẳn nhau, và gộp đúng vào chỗ kết quả đi ngược nhau:

    hiệu chỉnh + từ chối   -> ĐÓNG GÓP DƯƠNG, mạnh (leakage 100% -> 0%)
    vòng lặp corrective    -> ĐÓNG GÓP ÂM (DEC-057: cứu 0 câu E, làm lọt 2 câu A/B)

Một bảng hai nhánh cộng hai số đó lại thành một cột "corrective" thắng tuyệt
đối, và **kết quả âm biến mất** — trái thẳng yêu cầu của DEC-057 ("vào Chương
kết quả, không giấu ở Limitations"). Nên bảng ở đây có **bốn** nhánh, xếp theo
thứ tự cộng dồn từng cơ chế một:

    1. llm_only        không truy hồi, không từ chối          (baseline DEC-047)
    2. static_rag      + truy hồi 1 lượt, LUÔN trả lời
    3. corrective_t1   + grader/ngưỡng đã hiệu chỉnh, lượt 2 KHÔNG được lật
    4. corrective      − guard lượt 2 (cho lượt 2 quyền lật)

Chênh lệch 2->3 là giá trị của **hiệu chỉnh**. Chênh lệch 3->4 là giá trị của
**vòng lặp** — và đó là chỗ DEC-057 phải đọc thẳng ra từ bảng.

⚠️ **Từ DEC-061 nhánh 3 là CẤU HÌNH ĐANG CHẠY THẬT** (`allow_turn2_promotion:
false`), còn nhánh 4 là cấu hình **tái lập** con số cũ của DEC-056/057. Tên khoá
``corrective_t1`` giữ nguyên vì nó mô tả đúng phép tính (dựng lại từ lượt 1) và
đổi khoá là làm hỏng mọi thứ đang đọc file này — nhưng **nhãn hiển thị** thì
phải nói đúng, xem :data:`ARM_LABEL`.

⚠️⚠️ **HAI Ô TRONG BẢNG NÀY LÀ THEO ĐỊNH NGHĨA, KHÔNG PHẢI PHÉP ĐO.**
``static_rag`` không có cơ chế từ chối nào, nên leakage của nó = 100% và
coverage = 100% **vì cấu tạo là thế**, y hệt cái bẫy DEC-051 đã phải cảnh báo
với ``leakage 0/30``. :func:`arm_row` gắn cờ ``by_construction`` cho đúng
những ô đó để bảng in ra không thể đọc nhầm thành phát hiện.

⚠️ ``llm_only`` **không có** cột leakage/coverage: nó không có ``TerminalAction``
nên "nó có từ chối không" phải đọc văn bản, và đoán bằng regex là dựng một phép
đo giả (lý do đầy đủ ở :func:`trace_export.build_baseline_record`). Ô đó là
``None`` — RAGAS Tuần 6 mới chấm được. **``None`` chứ không phải 0**: 0 đọc
thành "đã đo và bằng không".

Thuần số: đọc bản ghi JSONL, không mạng, không model, không đọc file.
"""

from __future__ import annotations

from src.eval.stats import fmt_pct, wilson
from src.eval.trace_export import ANSWERING_ACTIONS

ABSTAIN_GROUPS = ("A", "B")   # phải TỪ CHỐI: corpus không có tài liệu
ANSWER_GROUPS = ("E",)        # phải TRẢ LỜI: corpus có tài liệu
POLICY_GROUPS = ("D",)        # bị policy gate chặn TRƯỚC retrieval

# Thứ tự nhánh = thứ tự CỘNG DỒN cơ chế. Đổi thứ tự là làm hỏng cách đọc bảng:
# giá trị của một cơ chế chỉ đọc được từ chênh lệch với nhánh ngay trước nó.
ARMS = ("llm_only", "static_rag", "corrective_t1", "corrective")

# ⚠️ Từ DEC-061, `corrective_t1` là **cấu hình đang chạy thật**
# (`allow_turn2_promotion=false`) còn `corrective` là cấu hình **tái lập** con số
# cũ của DEC-056/057. Nhãn phải nói ra điều đó: một bảng gọi nhánh 4 là "hệ thật"
# sau khi hệ đã đổi là bảng mô tả sai chính hệ thống mình đang báo cáo.
ARM_LABEL = {
    "llm_only": "LLM-only (không truy hồi)",
    "static_rag": "Static RAG (1 lượt, luôn trả lời)",
    "corrective_t1": "**Corrective + guard lượt 2 — HỆ ĐANG CHẠY**",
    "corrective": "Corrective không guard (tái lập DEC-056/057)",
}

ARM_MECHANISM = {
    "llm_only": "—",
    "static_rag": "+ truy hồi",
    "corrective_t1": "+ policy gate, grader, ngưỡng hiệu chỉnh, **guard lượt 2**",
    "corrective": "− guard lượt 2 (cho lượt 2 quyền lật)",
}


def is_answering(rec: dict) -> bool:
    """Hệ thống đã trả lời câu này chưa (kể cả bản kèm cảnh báo)?"""
    return rec.get("action") in ANSWERING_ACTIONS


def answered_at_turn1(rec: dict) -> bool:
    """Nhánh ``corrective_t1``: hệ sẽ trả lời nếu KHÔNG có vòng lặp rewrite.

    Dựng lại từ chính bản ghi corrective thay vì chạy lô thứ hai — chỉ cần
    lượt 1 của grader, thứ ``runs.jsonl`` đã lưu đủ (bẫy #1 của
    ``export_runs.py`` tồn tại chính vì việc này).

    Ba trạng thái phải phân biệt cho đúng:

    * Không có lượt truy hồi nào (``turns`` rỗng) → câu bị **policy gate** chặn
      trước retrieval. Không rewrite nào chạm tới được, nên nhánh này giữ
      nguyên kết cục cuối: không trả lời.
    * Lượt 1 chấm ``INCORRECT`` → không có rewrite thì dừng ở ABSTAIN.
    * Còn lại (``CORRECT``/``AMBIGUOUS``) → trả lời ngay ở lượt 1, và vòng lặp
      không bao giờ chạy, nên kết cục **trùng** hệ đầy đủ.
    """
    turns = rec.get("turns") or []
    if not turns:
        return is_answering(rec)
    if turns[0].get("state") == "INCORRECT":
        return False
    return is_answering(rec)


def _answered_fn(arm: str):
    """Trả về hàm ``rec -> đã trả lời chưa`` cho một nhánh.

    ``static_rag`` luôn ``True`` **theo cấu tạo**; ``llm_only`` trả ``None`` —
    xem cảnh báo ở docstring module.
    """
    if arm == "corrective_t1":
        return answered_at_turn1
    if arm == "static_rag":
        return lambda rec: True
    if arm == "llm_only":
        return lambda rec: None
    return is_answering


def arm_records(records: list[dict], arm: str) -> list[dict]:
    """Bản ghi thuộc một nhánh. ``corrective_t1`` dùng lại chính lô corrective."""
    want = "corrective" if arm == "corrective_t1" else arm
    want = "baseline_llm_only" if arm == "llm_only" else want
    return [r for r in records if r.get("system") == want]


def count_group(
    records: list[dict], arm: str, groups: tuple[str, ...]
) -> dict:
    """Đếm "đã trả lời / tổng" của một nhánh trên một nhóm câu.

    Tên trường trung tính (``answered``, không phải ``leaked``) theo đúng lý do
    đã ghi ở :func:`leakage.analyze_group`: cùng một phép đếm mang hai nghĩa
    ngược nhau tuỳ nhóm — với A/B "đã trả lời" là **leakage**, với E là
    **coverage**. Diễn giải để bảng lo.
    """
    rows = [r for r in arm_records(records, arm) if r.get("group") in groups]
    fn = _answered_fn(arm)
    flags = [fn(r) for r in rows]
    if any(f is None for f in flags):
        return {"n": len(rows), "answered": None, "ids": [], "measured": False}
    ids = [r["id"] for r, f in zip(rows, flags) if f]
    return {
        "n": len(rows),
        "answered": len(ids),
        "ids": ids,
        "measured": True,
    }


def arm_row(records: list[dict], arm: str) -> dict:
    """Một dòng của bảng: leakage A/B, coverage E, nhóm D bị chặn.

    ``by_construction`` liệt kê **tên ô** mà con số bị quy trình ép ra chứ
    không đo được. Bảng in ra phải đánh dấu đúng những ô đó; xem docstring
    module cho lý do vì sao đây không phải chuyện trình bày mà là chuyện
    không nói sai kết quả.
    """
    by_construction: list[str] = []
    if arm == "static_rag":
        by_construction = ["leakage", "coverage", "policy_blocked"]

    ab = count_group(records, arm, ABSTAIN_GROUPS)
    e = count_group(records, arm, ANSWER_GROUPS)
    d = count_group(records, arm, POLICY_GROUPS)

    return {
        "arm": arm,
        "label": ARM_LABEL[arm],
        "mechanism": ARM_MECHANISM[arm],
        "leakage": ab,           # A/B đã trả lời = lọt lưới
        "coverage": e,           # E đã trả lời = phủ
        "policy_blocked": {      # D KHÔNG trả lời = bị chặn đúng
            "n": d["n"],
            "answered": d["answered"],
            "blocked": None if d["answered"] is None else d["n"] - d["answered"],
            "measured": d["measured"],
        },
        "by_construction": by_construction,
    }


def build_table(records: list[dict]) -> dict:
    """Cả bốn dòng + chênh lệch giữa các nhánh liền kề.

    ``deltas`` là thứ chống đỡ cách đọc bảng: giá trị của một cơ chế **không**
    đọc được từ cột tuyệt đối của nhánh mang nó, chỉ đọc được từ chênh lệch với
    nhánh ngay trước. Tính sẵn ở đây để không bảng nào tự trừ tay rồi trừ nhầm
    chiều.
    """
    rows = {arm: arm_row(records, arm) for arm in ARMS}
    deltas = []
    for prev, cur in zip(ARMS, ARMS[1:]):
        deltas.append({
            "from": prev,
            "to": cur,
            "mechanism": ARM_MECHANISM[cur],
            "leakage": _delta(rows[prev]["leakage"], rows[cur]["leakage"]),
            "coverage": _delta(rows[prev]["coverage"], rows[cur]["coverage"]),
        })
    return {"arms": ARMS, "rows": rows, "deltas": deltas}


def _delta(a: dict, b: dict) -> int | None:
    """``b − a`` theo số câu đã trả lời. ``None`` nếu một bên chưa đo được."""
    if a.get("answered") is None or b.get("answered") is None:
        return None
    return b["answered"] - a["answered"]


def fmt_cell(cell: dict, *, by_construction: bool = False) -> str:
    """Một ô bảng Markdown. Ô theo cấu tạo bị đánh dấu ngay trong ô.

    Đánh dấu **trong ô** chứ không nhét xuống chú thích cuối bảng: người đọc
    trích một con số ra khỏi bảng thì họ trích cái ô, không trích chú thích.
    """
    if cell.get("answered") is None:
        # ⚠️ KHÔNG ghi "(cần RAGAS)" — đó là một lời hứa không thực hiện được
        # (ISSUE-075). RAGAS trả về **faithfulness**, thứ đo "bám ngữ cảnh";
        # nó không phải leakage cũng không phải coverage, nên nó không lấp
        # được ô này dù đã chấm xong. Ô trống vì nhánh llm_only **không có
        # `TerminalAction`** — đó là lý do cơ chế, và nó không đổi.
        return "— *(không có TerminalAction)*"
    if not cell.get("n"):
        # Mẫu số 0 = nhánh này chưa chạy trên nhóm đó (nhóm D của Static RAG).
        # In "0/0 = 0%" ở đây là dựng một ô trông như đã đo.
        return "— *(chưa chạy)*"
    txt = fmt_pct(cell["answered"], cell["n"])
    return f"{txt} †" if by_construction else txt


def wilson_pct(k: int, n: int) -> tuple[float, float, float]:
    """``(tỉ lệ, cận dưới, cận trên)`` theo phần trăm."""
    lo, hi = wilson(k, n)
    return (100 * k / n if n else 0.0, 100 * lo, 100 * hi)


# --------------------------------------------------------------------------- #
# Tầng NỘI DUNG + phân tích độ nhạy (PA 3, DEC-062)
# --------------------------------------------------------------------------- #
# Ba lớp thực thể, theo `data/concept_variants.jsonl`. Chỉ lớp đầu làm lung lay
# tiền đề của nhãn ABSTAIN; hai lớp sau thì nhãn vẫn đứng.
VARIANT_SAME_CONCEPT = "variant_same_concept"   # cùng khái niệm, khác chuỗi
VARIANT_BRAND = "variant_generic_of_brand"      # biệt dược vắng, hoạt chất có
NO_VARIANT = "no_variant"


def flagged_ids(variants: list[dict], *, include_weak: bool = True) -> set[str]:
    """Câu có tiền đề nhãn bị lung lay — CHỈ lớp ``variant_same_concept``.

    ``variant_generic_of_brand`` **không** vào đây: biệt dược vắng mặt trong khi
    hoạt chất có mặt thì nhãn ABSTAIN vẫn đúng — thông tin theo sản phẩm (hàm
    lượng, dạng bào chế, phối hợp) không suy ra được từ bài viết về hoạt chất.

    ⚠️ **Cờ phải gắn theo TIÊU CHÍ, không theo kết cục.** Danh sách này gồm cả
    những câu mà hệ thống đã từ chối đúng (``A-17``, ``A-18``, ``B-06``). Nếu chỉ
    gắn cờ cho câu đã lọt lưới thì chính phân tích độ nhạy lại mắc lỗi chọn theo
    kết quả — đúng thứ PA 3 sinh ra để tránh.
    """
    return {
        v["id"] for v in variants
        if v.get("class") == VARIANT_SAME_CONCEPT
        and (include_weak or v.get("confidence") != "weak")
    }


def content_leakage(verdicts: list[dict], variants: list[dict]) -> dict:
    """Leakage tầng NỘI DUNG + hai mức độ nhạy.

    Trả về ba con số trên cùng một bộ nhãn, khác nhau ở **mẫu số**:

    ``headline``    toàn bộ nhóm A/B — con số chính, không bỏ câu nào.
    ``strict``      bỏ mọi câu ``variant_same_concept`` (kể cả cờ yếu).
    ``moderate``    chỉ bỏ câu cờ **clear**.

    Báo cáo cả ba chứ không chọn một: bỏ câu khỏi mẫu số là một **quyết định
    diễn giải**, và người đọc phải thấy nó đổi con số bao nhiêu. Đây là lý do
    PA 3 được chọn thay vì bỏ hẳn 3 câu — không đụng mẫu số thì không có chỗ
    cho cáo buộc chọn lọc.
    """
    asserts = {
        v["id"]: v.get("asserts_about_entity")
        for v in verdicts
        if v.get("asserts_about_entity") in (True, False)
    }
    drop_all = flagged_ids(variants, include_weak=True)
    drop_clear = flagged_ids(variants, include_weak=False)

    def cut(dropped: set[str]) -> dict:
        keep = {q: a for q, a in asserts.items() if q not in dropped}
        yes = sorted(q for q, a in keep.items() if a)
        return {
            "n": len(keep),
            "leaked": len(yes),
            "ids": yes,
            "dropped": sorted(dropped & set(asserts)),
        }

    return {
        "headline": cut(set()),
        "strict": cut(drop_all),
        "moderate": cut(drop_clear),
        "n_flagged": len(drop_all & set(asserts)),
        "n_flagged_clear": len(drop_clear & set(asserts)),
    }


def mechanism_split(verdicts: list[dict]) -> dict:
    """Tách **thay thế thực thể** khỏi **bịa tự do** trong số câu có phát biểu.

    Hai loại cần cách vá khác nhau: bịa tự do phải có LLM judge mới bắt được,
    còn thay thế thực thể thì một phép kiểm thực thể thuần đã bắt được. Gộp
    chúng vào một con số là mô tả sai cơ chế rồi vá sai chỗ.
    """
    yes = [v for v in verdicts if v.get("asserts_about_entity") is True]
    return {
        "substitution": sorted(
            v["id"] for v in yes if v.get("concept_in_corpus") is True
        ),
        "fabrication": sorted(
            v["id"] for v in yes if v.get("concept_in_corpus") is False
        ),
        "unknown": sorted(
            v["id"] for v in yes
            if v.get("concept_in_corpus") not in (True, False)
        ),
    }

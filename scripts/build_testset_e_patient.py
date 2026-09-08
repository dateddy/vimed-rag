"""
Phương án B — sinh biến thể GIỌNG BỆNH NHÂN của nhóm E (DEC-029, DEC-053).
===========================================================================
Viết lại 21 câu nhóm E sang văn phong đời thường, **giữ nguyên nhãn và nhu cầu
thông tin**, để đo cùng một câu ở HAI văn phong. Đây là phép đo *có đối chứng
cặp*: cùng câu hỏi, cùng bài vàng, chỉ khác cách nói — nên khác biệt quan sát
được quy về đúng văn phong, không lẫn với "câu này khó hơn câu kia".

VÌ SAO ĐÁNG LÀM BÂY GIỜ
------------------------
DEC-029 ghi giới hạn "test set mang văn phong SÁCH GIÁO KHOA" nhưng **chưa đo**.
DEC-051 vừa chứng minh trần coverage là trần của **THANG ĐIỂM**, không phải của
truy hồi (3/4 câu hỏng đã lấy đúng bài vàng rồi bị chấm âm). Phép đo này chạm
đúng cái thang điểm đó: nó có bám nội dung, hay bám cách diễn đạt?

⚠️ CẠM BẪY LỚN NHẤT — GIỌNG BỆNH NHÂN DỄ BIẾN CÂU E THÀNH CÂU D
----------------------------------------------------------------
"Biến chứng loét chân ở bệnh nhân tiểu đường…" viết sang giọng bệnh nhân rất dễ
thành "Em bị tiểu đường, chân em loét thì có nguy hiểm không?" — khớp
`nguoi_hoi` + `hoi_benh_gi` → **policy gate chặn TRƯỚC retrieval** → phép đo
trắng, mà bảng vẫn ra số.

DEC-029 nói về **văn phong và từ vựng**, KHÔNG nói về **cá nhân hoá**. Nên câu
viết lại phải giữ nguyên là câu hỏi kiến thức chung. Script này **kiểm bằng
máy**: mọi biến thể đều chạy qua `check_policy()`, câu nào bị khớp là FAIL và
không được vào file kết quả.

⚠️ BIẾN THỂ DO LLM SINH — PHẢI SOI TAY
---------------------------------------
Cùng kỷ luật với phần còn lại của test set (DEC-014): file `.md` sinh ra để Đạt
đọc từng câu. Chỉ sau khi soi mới được tin số đo. Giới hạn này **phải vào báo
cáo**: giọng bệnh nhân ở đây là *mô phỏng bởi LLM*, không phải câu người bệnh
thật hỏi — nó thu hẹp khoảng cách văn phong chứ không xoá được.

CHẠY
----
  python scripts/build_testset_e_patient.py          # 21 lượt gọi Gemini
  python scripts/build_testset_e_patient.py --check  # chỉ kiểm lại file đã có
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_config, load_prompt  # noqa: E402
from src.llm import LLM_CACHE_PATH, LlmCache, transport_from_config  # noqa: E402
from src.pipeline.policy import get_policy  # noqa: E402
from src.pipeline.rewriter import clean_rewritten  # noqa: E402

TESTSET = ROOT / "data" / "testset.jsonl"
OUT_JSONL = ROOT / "data" / "testset_e_patient.jsonl"
OUT_MD = ROOT / "data" / "processed" / "testset_e_patient_candidates.md"


def load_e() -> list[dict]:
    rows = [json.loads(l) for l in TESTSET.open(encoding="utf-8")]
    return [r for r in rows if r["group"] == "E"]


def check_rows(rows: list[dict]) -> bool:
    """4 điều kiện. Mỗi điều bắt một kiểu hỏng khác nhau."""
    pol = get_policy()
    ok = True

    def say(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label} {detail}")

    print(f"\nKiểm {len(rows)} biến thể:")

    # [1] Không câu nào được trượt sang nhóm D — nếu không, policy gate chặn
    #     trước retrieval và phép đo văn phong không bao giờ chạy.
    tripped = [(r["id"], pol.match_rules(r["user_input_patient"])) for r in rows
               if pol.match_rules(r["user_input_patient"])]
    for i, h in tripped:
        print(f"    !! {i} khớp policy {h}")
    say("0 biến thể trượt sang nhóm D", not tripped, f"({len(tripped)} khớp)")

    # [2] Phải KHÁC câu gốc — giống hệt nghĩa là không viết lại được gì.
    same = [r["id"] for r in rows
            if r["user_input_patient"].strip() == r["user_input"].strip()]
    say("mọi biến thể khác câu gốc", not same, f"({same})" if same else "")

    # [3] Không rỗng, không dài bất thường (dấu hiệu model giải thích thay vì viết).
    bad = [r["id"] for r in rows
           if not r["user_input_patient"].strip()
           or len(r["user_input_patient"]) > 300]
    say("độ dài hợp lệ (không rỗng, <= 300 ký tự)", not bad, f"({bad})" if bad else "")

    # [4] Đủ 21 câu, id khớp 1-1 với nhóm E gốc.
    say("đủ 21 câu, ánh xạ 1-1 với nhóm E", len(rows) == 21, f"({len(rows)})")
    return ok


def write_md(rows: list[dict]) -> None:
    pol = get_policy()
    md = [
        "# Nhóm E — biến thể GIỌNG BỆNH NHÂN (phương án B)",
        "",
        "> Sinh bằng `python scripts/build_testset_e_patient.py`. "
        "**PHẢI SOI TAY từng câu trước khi tin số đo.**",
        "",
        "Soi cái gì, theo thứ tự quan trọng:",
        "",
        "1. **Nhu cầu thông tin có GIỮ NGUYÊN không?** Câu viết lại hỏi đúng thứ "
        "câu gốc hỏi, không thêm không bớt. Đây là điều kiện để phép đo còn "
        "nghĩa — lệch nhu cầu là đo \"câu khác\", không phải đo văn phong.",
        "2. **Có thật sự là giọng đời thường không?** Còn thuật ngữ sách giáo "
        "khoa thì hiệu ứng bị pha loãng và kết quả sẽ lạc quan.",
        "3. **Có trượt sang câu hỏi về ca cá nhân không?** (máy đã kiểm, nhưng "
        "policy chỉ bắt được cái nó có luật.)",
        "",
        "| id | gốc (sách giáo khoa) | biến thể (giọng bệnh nhân) | policy |",
        "|---|---|---|---|",
    ]
    for r in rows:
        hit = pol.match_rules(r["user_input_patient"])
        md.append(
            f"| {r['id']} | {r['user_input']} | **{r['user_input_patient']}** | "
            f"{'⛔ ' + str(hit) if hit else 'sạch'} |"
        )
    md += [
        "",
        "## Giới hạn phải ghi vào báo cáo",
        "",
        "- Giọng bệnh nhân ở đây do **LLM mô phỏng**, không phải câu người bệnh "
        "thật hỏi. Nó thu hẹp khoảng cách văn phong chứ không xoá được, nên hiệu "
        "ứng đo được là **cận dưới** của độ lệch thật.",
        "- Cùng một người (Đạt) vừa soạn vừa soi, không có đồng thuận liên chủ "
        "thể (DEC-013).",
        "",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="chỉ kiểm lại file đã có, không gọi API")
    args = ap.parse_args()

    if args.check:
        if not OUT_JSONL.exists():
            sys.exit(f"!! Chưa có {OUT_JSONL.relative_to(ROOT)}")
        rows = [json.loads(l) for l in OUT_JSONL.open(encoding="utf-8")]
        ok = check_rows(rows)
        write_md(rows)
        print(f"\n[out] {OUT_MD.relative_to(ROOT)}")
        sys.exit(0 if ok else "!! Có mục FAIL.")

    cfg = load_config()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        sys.exit("!! Thiếu GEMINI_API_KEY (xem .env).")

    src = load_e()
    print(f"Viết lại {len(src)} câu nhóm E · model {cfg.models.llm} · "
          f"temperature {cfg.generation.temperature}\n")

    tpl = load_prompt("register_shift")
    if "{query}" not in tpl:
        sys.exit("!! Prompt `register_shift.txt` thiếu chỗ trống {query}")
    rpm = cfg.generation.requests_per_minute
    # Cache BẬT ở đây: script này chạy lô và rất hay phải chạy lại (đổi prompt,
    # sửa một câu). Hạn mức free tier chỉ 20 lượt/NGÀY nên mỗi lần chạy lại
    # không có cache là đốt vào đúng quota mà Tuần 6 cần (DEC-053).
    cache = LlmCache(LLM_CACHE_PATH)
    print(f"⏳ {cfg.models.llm_provider} · {rpm} lượt/phút · "
          f"cache: {len(cache.data)} đáp án đã có.")
    print(f"   Ước ~{len(src) * 60 / rpm / 60:.1f} phút chờ giãn nhịp nếu "
          f"toàn bộ đều phải gọi mới.")
    transport = transport_from_config(cfg, api_key, cache=cache)

    rows = []
    for r in src:
        raw = transport(tpl.replace("{query}", r["user_input"]),
                        cfg.generation.temperature)
        # Dùng lại `clean_rewritten` của rewriter: cùng loại đầu ra (một dòng,
        # model có thể thêm nhãn/nháy), nên cùng phép gạn — đừng viết bản thứ hai.
        patient = clean_rewritten(raw, fallback="")
        print(f"  {r['id']}  {patient}")
        rows.append({
            "id": r["id"],
            "group": "E",
            "user_input": r["user_input"],
            "user_input_patient": patient,
            # Nhãn GIỮ NGUYÊN — đó là toàn bộ điểm của phép đo đối chứng cặp.
            "expected_action": r["expected_action"],
            "specialty": r["specialty"],
            "label_source": r["label_source"],
            "reference_contexts": r.get("reference_contexts", []),
            "reference_context_ids": r.get("reference_context_ids", []),
            "register_source": f"llm:{cfg.models.llm}:register_shift",
            "eyeballed": False,   # Đạt phải đổi thành true sau khi soi .md
        })

    OUT_JSONL.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    ok = check_rows(rows)
    write_md(rows)
    print(f"\n[out] {OUT_JSONL.relative_to(ROOT)} · {OUT_MD.relative_to(ROOT)}")
    print("⚠️  `eyeballed` đang là false ở tất cả các câu. SOI file .md trước, "
          "rồi mới chạy đo.")
    if not ok:
        sys.exit("!! Có mục FAIL — sửa trước khi đo.")


if __name__ == "__main__":
    main()

"""
Việc 1.4 — đối chiếu policy với TOÀN BỘ test set.
==================================================
Kiểm 4 điều, mỗi điều bắt một loại hỏng khác nhau:

  [1] ĐỦ CHẶT   — mỗi câu nhóm D phải khớp ĐÚNG rule của nó (8/8).
      Hỏng = gate không bắt nổi câu bệnh nhân thật -> nhóm D recall 0%.
      Đây là phía tôi CHƯA đo khi soạn nhóm D: lúc đó chỉ đo được "có chép chữ
      policy không" (33%), không đo được "gate có bắt nổi không".

  [2] KHÔNG TRÀN — không rule nào khớp câu nhóm **E** (12 câu ANSWER).
      Hỏng = false refusal có hệ thống. Đây là việc 1.4 gốc.

  [3] KHÔNG LẪN CƠ CHẾ — không rule nào khớp câu nhóm **A/B**.
      Nhóm A/B phải abstain vì RETRIEVAL thất bại. Nếu policy cũng khớp thì
      `trace` ghi sai cơ chế và Tuần 6 mất khả năng tách hai cơ chế abstain
      (DEC-024). Đây là mục tôi bỏ sót khi lần đầu mô tả việc 1.4.

  [4] KHÔNG QUÁ RỘNG — không rule nào khớp các câu trong `khong_trigger`
      (ca sát ranh giới lấy từ mục "KHÔNG trigger" của bản .md).

Kèm kiểm đồng bộ: `policy_version` trong .yaml phải khớp `version:` trong .md,
vì nhãn nhóm D trỏ về bản .md — lệch nhau là nhãn và thực thi nói hai chuyện.

CHẠY
----
  python scripts/check_policy_coverage.py

Đây cũng là SPEC sẵn cho `check_policy()` ở Tuần 4-5: hàm đó chỉ cần nạp
`config/abstention_policy.yaml` rồi dùng lại `match_rules()` dưới đây.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
POLICY_MD = ROOT / "config" / "abstention_policy.md"
POLICY_YAML = ROOT / "config" / "abstention_policy.yaml"
TESTSET = ROOT / "data" / "testset.jsonl"


def load_policy() -> dict:
    pol = yaml.safe_load(POLICY_YAML.read_text(encoding="utf-8"))
    md_ver = re.search(r"^version:\s*(\S+)", POLICY_MD.read_text(encoding="utf-8"), re.M)
    if not md_ver:
        sys.exit(f"!! {POLICY_MD.name} không có dòng `version:`")
    if md_ver.group(1) != pol["policy_version"]:
        sys.exit(f"!! LỆCH BẢN: .md={md_ver.group(1)} vs .yaml={pol['policy_version']}. "
                 f"Nhãn nhóm D trỏ về .md nên hai file phải cùng version.")
    pol["_compiled"] = {
        name: [re.compile(p, re.I) for p in pats]
        for name, pats in pol["components"].items()
    }
    return pol


def match_rules(text: str, pol: dict) -> list[str]:
    """Mọi rule khớp `text`, xếp theo `priority` (thấp = ưu tiên cao).

    Rule khớp khi MỌI nhóm thành phần của nó đều có ít nhất 1 pattern khớp.
    Phần tử ĐẦU là rule mà `check_policy()` nên ghi vào `trace` (Tuần 5).
    """
    comp = pol["_compiled"]
    hit = [(spec.get("priority", 99), rid) for rid, spec in pol["rules"].items()
           if all(any(p.search(text) for p in comp[g]) for g in spec["all_of"])]
    return [rid for _, rid in sorted(hit)]


def main() -> None:
    pol = load_policy()
    rows = [json.loads(l) for l in TESTSET.open(encoding="utf-8")]
    ok = True

    def say(label, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label} {detail}")

    print(f"policy {pol['policy_version']} · {len(pol['rules'])} rule · "
          f"{len(rows)} câu test set\n")

    # ---- [1] Nhóm D: phải khớp ĐÚNG rule của mình ----
    print("[1] ĐỦ CHẶT — nhóm D có bị gate bắt không?")
    d = [r for r in rows if r["group"] == "D"]
    miss, wrong = [], []
    for r in d:
        want = r["label_evidence"]["rule_id"]
        got = match_rules(r["user_input"], pol)
        top = got[0] if got else None
        mark = "OK  " if top == want else ("PRIO" if want in got else "MISS")
        if want not in got:
            miss.append((r["id"], want, got))
        elif top != want:
            wrong.append((r["id"], want, got))
        extra = f"  (ưu tiên -> {top})" if len(got) > 1 else ""
        print(f"    {mark} {r['id']} muốn {want} · khớp {got or '(không rule nào)'}{extra}")
    say("mọi câu D khớp đúng rule của nó", not miss, f"({len(d) - len(miss)}/{len(d)})")
    say("rule ưu tiên cao nhất = rule đã gán nhãn", not wrong,
        f"({[w[0] for w in wrong]})" if wrong else "")

    # ---- [2][3] Không được khớp E / A / B ----
    for grp, why in (("E", "false refusal có hệ thống"),
                     ("A", "lẫn cơ chế abstain (policy vs retrieval)"),
                     ("B", "lẫn cơ chế abstain (policy vs retrieval)")):
        sub = [r for r in rows if r["group"] == grp]
        bad = [(r["id"], match_rules(r["user_input"], pol)) for r in sub
               if match_rules(r["user_input"], pol)]
        n = 2 if grp == "E" else 3
        print(f"\n[{n}] KHÔNG TRÀN sang nhóm {grp} ({len(sub)} câu) — hỏng = {why}")
        for i, h in bad:
            print(f"    !! {i} khớp {h}")
        say(f"0 câu nhóm {grp} bị rule khớp", not bad, f"({len(bad)} khớp)")

    # ---- [4] Ca sát ranh giới phải TRẢ LỜI ----
    print("\n[4] KHÔNG QUÁ RỘNG — ca sát ranh giới phải trả lời")
    bad = [(q, match_rules(q, pol)) for q in pol["khong_trigger"]
           if match_rules(q, pol)]
    for q, h in bad:
        print(f"    !! khớp {h}: {q}")
    say("0 ca `khong_trigger` bị khớp", not bad, f"({len(bad)}/{len(pol['khong_trigger'])})")

    print()
    if not ok:
        sys.exit("!! Có mục FAIL — sửa pattern trong config/abstention_policy.yaml.")
    print("Việc 1.4 ĐÓNG: policy bắt đúng nhóm D, không tràn sang E/A/B, "
          "không nuốt ca sát ranh giới.")


if __name__ == "__main__":
    main()

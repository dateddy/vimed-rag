"""Policy gate — lớp 1/8 của defense-in-depth (DEC-024).

Chạy **TRƯỚC** retrieval: rẻ nhất, không tốn một lượt truy hồi vô ích, và rule
cấp cứu phải trả lời ngay không kèm nội dung tra cứu. Thuần rule (regex từ
``config/abstention_policy.yaml``), **KHÔNG LLM** — giữ tinh thần ràng buộc #4
và để nhãn nhóm D còn kiểm chứng được bằng máy (DEC-014).

Không có lớp này thì câu nhóm D ("tôi 60kg uống metformin bao nhiêu") đi thẳng
vào retrieval, corpus **có** bài metformin → grader trả CORRECT → hệ thống
ANSWER, tức abstention recall nhóm D = **0%**.

⚠️ Đây là bản **CÓ THẨM QUYỀN** của ``match_rules``.
``scripts/check_policy_coverage.py`` import lại từ đây thay vì giữ bản của
riêng nó. Hai bản regex song song = script PASS trong khi pipeline FAIL (hoặc
ngược lại) và không ai phát hiện; script chỉ còn là bằng chứng cho pipeline khi
nó chấm đúng cái code mà pipeline chạy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

# src/pipeline/policy.py -> src/pipeline -> src -> <repo>
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"


@dataclass(frozen=True)
class PolicyHit:
    """Một câu bị policy chặn.

    ``rule_id`` là thứ đi vào ``TraceStep.note`` — Tuần 6 tách
    ABSTAIN-do-policy khỏi ABSTAIN-do-retrieval bằng đúng trường này
    (``corrective-loop.md``, mục "HAI cơ chế ABSTAIN").

    ``all_rules`` giữ MỌI rule khớp, xếp theo ưu tiên, để debug rule quá rộng.
    **Metric chỉ được đọc ``rule_id``** — đếm ``all_rules`` là đếm trùng, một
    câu tiếng Việt khớp nhiều rule là chuyện bình thường (D-07 khớp cả D-2 lẫn
    D-4 vì "có sao không" mang hai nghĩa).
    """

    rule_id: str
    name: str
    priority: int
    all_rules: tuple[str, ...]


class Policy:
    """Bản đã biên dịch của ``config/abstention_policy.yaml``.

    Biên dịch regex một lần lúc dựng; ``get_policy()`` cache lại nên pipeline
    không biên dịch lại mỗi truy vấn.
    """

    def __init__(self, raw: dict) -> None:
        self._raw = raw
        self._compiled = {
            name: [re.compile(p, re.I) for p in pats]
            for name, pats in raw["components"].items()
        }

    @property
    def version(self) -> str:
        return self._raw["policy_version"]

    @property
    def rules(self) -> dict:
        return self._raw["rules"]

    @property
    def khong_trigger(self) -> list[str]:
        """Ca sát ranh giới PHẢI TRẢ LỜI — test case âm của policy."""
        return self._raw.get("khong_trigger", [])

    def match_rules(self, text: str) -> list[str]:
        """Mọi rule khớp ``text``, xếp theo ``priority`` (thấp = ưu tiên cao).

        Rule khớp khi **MỌI** nhóm thành phần của nó đều có ít nhất 1 pattern
        khớp. Ràng buộc AND này là thứ giữ policy không nuốt nhầm câu nhóm
        E/A/B: mọi rule đều đòi ngôi thứ nhất hoặc người nhà, trong khi E/A/B
        lấy từ ViMedAQA nên toàn giọng sách giáo khoa ngôi thứ ba (DEC-029).

        Phần tử ĐẦU là rule mà ``check()`` ghi vào ``trace``.
        """
        hit = [
            (spec.get("priority", 99), rid)
            for rid, spec in self._raw["rules"].items()
            if all(
                any(p.search(text) for p in self._compiled[g])
                for g in spec["all_of"]
            )
        ]
        return [rid for _, rid in sorted(hit)]

    def check(self, text: str) -> PolicyHit | None:
        """``None`` = đi tiếp sang retrieval. ``PolicyHit`` = ABSTAIN ngay."""
        ids = self.match_rules(text)
        if not ids:
            return None
        spec = self._raw["rules"][ids[0]]
        return PolicyHit(
            rule_id=ids[0],
            name=spec["name"],
            priority=spec.get("priority", 99),
            all_rules=tuple(ids),
        )


def load_policy(config_dir: Path | str | None = None) -> Policy:
    """Nạp yaml + kiểm đồng bộ version với bản ``.md`` có thẩm quyền.

    Args:
        config_dir: thư mục chứa policy (mặc định ``<repo>/config``).

    Raises:
        ValueError: ``.md`` thiếu dòng ``version:``, hoặc ``policy_version``
            trong ``.yaml`` lệch nó. Nhãn nhóm D trỏ về ``.md``
            (``label_source: abstention_policy.md@v1#D-1``) nên lệch nhau =
            nhãn và thực thi nói hai chuyện khác nhau.
    """
    cfg_dir = Path(config_dir) if config_dir else _CONFIG_DIR
    raw = yaml.safe_load(
        (cfg_dir / "abstention_policy.yaml").read_text(encoding="utf-8")
    )
    md_text = (cfg_dir / "abstention_policy.md").read_text(encoding="utf-8")
    md_ver = re.search(r"^version:\s*(\S+)", md_text, re.M)
    if not md_ver:
        raise ValueError("abstention_policy.md không có dòng `version:`")
    if md_ver.group(1) != raw["policy_version"]:
        raise ValueError(
            f"LỆCH BẢN: .md={md_ver.group(1)} vs .yaml={raw['policy_version']}. "
            f"Nhãn nhóm D trỏ về .md nên hai file phải cùng version."
        )
    return Policy(raw)


@lru_cache(maxsize=4)
def get_policy(config_dir: Path | str | None = None) -> Policy:
    """``load_policy`` có cache — dùng ở đường chạy thật (mỗi truy vấn)."""
    return load_policy(config_dir)

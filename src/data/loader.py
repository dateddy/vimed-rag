"""Nạp corpus y tế tiếng Việt từ HuggingFace và gán chuyên khoa.

Gate 0 = GO (`brain/contracts/gates.md`) nên phần tải dataset thật đã mở khoá.

**Chính sách gán khoa — DEC-016.** Một bài thuộc khoa X nếu keyword của X nằm ở
TIÊU ĐỀ **hoặc** xuất hiện >= ``cfg.specialty_min_keyword_count`` lần trong
(tiêu đề + thân bài). Ngưỡng đọc từ ``config/config.yaml``, từ vựng 2 khoa đọc
từ ``config/specialties.yaml`` — không hard-code cái nào ở đây.

Vì sao không phải "có mặt là tính": quy tắc cũ gán 80% bài `tim_mach` chỉ nhờ
đếm keyword trong thân bài ("Nho khô có tốt cho bạn không?" nhắc cholesterol 13
lần), và cho corpus lớn tới mức ăn 89% Qdrant Cloud free tier. Số đo đầy đủ:
``scripts/policy_cost_audit.py``.

**Ràng buộc còn hiệu lực:** module này KHÔNG chạm dataset thật lúc import hay
lúc test. ``datasets`` chỉ được import bên trong :func:`load_hf_dataset`; toàn
bộ logic gán khoa là hàm thuần chạy trên dict nên test bằng row giả.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.config import DataConfig
from src.data.cleaner import normalize_text

# Dedup thô: 2 bài trùng nhau ở 200 ký tự đầu coi là một (khớp Gate 0).
_DEDUP_PREFIX = 200


@dataclass
class RawDocument:
    """Document thô sau khi làm sạch và gán khoa, trước khi chunk.

    ``specialties`` giữ TẤT CẢ khoa mà bài khớp (1.1% bài khớp cả hai);
    ``specialty`` là khoa đầu tiên theo thứ tự khai báo trong
    ``config/specialties.yaml`` — tiện cho payload 1 giá trị, nhưng lọc theo
    khoa ở Tuần 3 phải dùng ``specialties`` để không đánh rơi bài trùng.
    """

    doc_id: str
    text: str
    specialty: str | None = None
    source: str | None = None
    title: str | None = None
    specialties: tuple[str, ...] = ()


@dataclass
class CorpusStats:
    """Thống kê theo khoa — đóng DoD Tuần 1 (>=150 bài/khoa)."""

    per_specialty: dict[str, int] = field(default_factory=dict)
    total: int = 0
    both: int = 0
    skipped_short: int = 0
    skipped_duplicate: int = 0
    skipped_no_specialty: int = 0

    def meets_floor(self, floor: int) -> bool:
        """Mọi khoa đều đạt >= ``floor`` bài?"""
        return bool(self.per_specialty) and all(
            n >= floor for n in self.per_specialty.values()
        )


def compile_specialty_patterns(
    specialties: Mapping[str, list[str]],
) -> dict[str, list[re.Pattern[str]]]:
    """Biên dịch từ vựng 2 khoa thành regex khớp theo ranh giới từ Unicode.

    ``(?<!\\w) ... (?!\\w)`` để "tim mạch" không khớp bên trong một từ dài hơn.
    ``\\w`` của Python bao gồm cả chữ có dấu nên tiếng Việt hoạt động đúng.
    """
    return {
        spec: [re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)") for kw in keywords]
        for spec, keywords in specialties.items()
    }


def _fold(text: str) -> str:
    """Chuẩn hoá về dạng dùng để so khớp: NFC + gỡ HTML + gộp trắng + lowercase."""
    return normalize_text(text).lower()


def match_specialties(
    title: str,
    body: str,
    patterns: Mapping[str, list[re.Pattern[str]]],
    min_count: int,
) -> list[str]:
    """Gán khoa cho một bài theo DEC-016: TITLE **hoặc** >= ``min_count`` lần.

    Args:
        title: tiêu đề bài (thô, chưa chuẩn hoá).
        body: thân bài (thô, chưa chuẩn hoá).
        patterns: kết quả của :func:`compile_specialty_patterns`.
        min_count: ngưỡng đếm, lấy từ ``cfg.specialty_min_keyword_count``.

    Returns:
        Danh sách khoa đã khớp, theo thứ tự khai báo trong config. Rỗng nếu
        bài không thuộc khoa nào.
    """
    folded_title = _fold(title)
    folded_full = f"{folded_title} {_fold(body)}".strip()

    hits: list[str] = []
    for spec, pats in patterns.items():
        if any(p.search(folded_title) for p in pats):
            hits.append(spec)
            continue
        # Cộng dồn số lần khớp của MỌI keyword thuộc khoa (giống policy_cost_audit).
        if sum(len(p.findall(folded_full)) for p in pats) >= min_count:
            hits.append(spec)
    return hits


def make_doc_id(text: str) -> str:
    """ID tất định theo nội dung — cùng bài thì cùng ID qua mọi lần chạy."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def build_documents(
    rows: Iterable[Mapping[str, object]],
    specialties: Mapping[str, list[str]],
    cfg: DataConfig,
    source: str | None = None,
) -> tuple[list[RawDocument], CorpusStats]:
    """Làm sạch → lọc → gán khoa cho các row thô. Hàm thuần, không chạm mạng.

    Bài bị loại khi: ngắn hơn ``cfg.min_article_chars``, trùng bài trước đó,
    hoặc không khớp khoa nào. Lý do loại được đếm vào :class:`CorpusStats`.

    Args:
        rows: iterable các mapping có cột tiêu đề/nội dung theo tên trong cfg.
        specialties: bảng ``khoa -> list keyword`` (``config/specialties.yaml``).
        cfg: khối ``data`` của config.
        source: ghi vào ``RawDocument.source`` (thường là tên dataset).

    Returns:
        Cặp ``(documents, stats)``.
    """
    patterns = compile_specialty_patterns(specialties)
    stats = CorpusStats(per_specialty={spec: 0 for spec in specialties})
    seen: set[str] = set()
    docs: list[RawDocument] = []

    for row in rows:
        title = normalize_text(str(row.get(cfg.title_col, "") or ""))
        body = normalize_text(str(row.get(cfg.content_col, "") or ""))
        text = f"{title} {body}".strip()

        if len(text) < cfg.min_article_chars:
            stats.skipped_short += 1
            continue
        key = text[:_DEDUP_PREFIX].casefold()
        if key in seen:
            stats.skipped_duplicate += 1
            continue
        seen.add(key)

        matched = match_specialties(
            title, body, patterns, cfg.specialty_min_keyword_count
        )
        if not matched:
            stats.skipped_no_specialty += 1
            continue

        docs.append(
            RawDocument(
                doc_id=make_doc_id(text),
                text=text,
                specialty=matched[0],
                source=source,
                title=title or None,
                specialties=tuple(matched),
            )
        )
        for spec in matched:
            stats.per_specialty[spec] += 1
        stats.total += 1
        if len(matched) > 1:
            stats.both += 1

    return docs, stats


def load_hf_dataset(
    cfg: DataConfig,
    specialties: Mapping[str, list[str]],
) -> tuple[list[RawDocument], CorpusStats]:
    """Tải corpus thật từ HuggingFace rồi gán khoa theo DEC-016.

    Corpus là dataset **gated** → phải có ``HF_TOKEN`` trong môi trường
    (``setx`` không áp cho terminal đang mở, phải mở terminal mới).

    ``datasets`` được import TRONG hàm: import module này không kéo theo
    HuggingFace và không chạm mạng, nên test vẫn chạy offline.
    """
    from datasets import load_dataset  # import trễ — xem docstring

    dataset = load_dataset(cfg.dataset, split=cfg.split)
    return build_documents(dataset, specialties, cfg, source=cfg.dataset)


def save_documents(docs: Iterable[RawDocument], path: Path | str) -> int:
    """Ghi documents ra JSONL (1 bài/dòng, UTF-8). Trả về số dòng đã ghi."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for doc in docs:
            record = asdict(doc)
            record["specialties"] = list(doc.specialties)
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1
    return n


def load_documents(path: Path | str) -> list[RawDocument]:
    """Đọc lại JSONL do :func:`save_documents` ghi ra."""
    docs: list[RawDocument] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            record["specialties"] = tuple(record.get("specialties", ()))
            docs.append(RawDocument(**record))
    return docs


def specialty_counts(docs: Iterable[RawDocument]) -> dict[str, int]:
    """Đếm bài theo khoa từ danh sách document (bài trùng khoa đếm ở cả hai)."""
    counter: Counter[str] = Counter()
    for doc in docs:
        counter.update(doc.specialties)
    return dict(counter)

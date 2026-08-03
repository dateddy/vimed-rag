"""Nạp cấu hình YAML + biến môi trường (.env) thành object typed.

Toàn hệ thống đọc ngưỡng / tên model / top-k / chunk size / max_iter từ đây —
KHÔNG hard-code magic number trong code nghiệp vụ.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Thư mục config/ nằm cạnh src/ ở gốc repo.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


# --------------------------------------------------------------------------- #
# Dataclass typed cho từng khối config
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ModelsConfig:
    embedder: str
    reranker: str
    llm: str


@dataclass(frozen=True)
class RetrievalConfig:
    hybrid: bool
    top_k_dense: int
    top_k_rerank: int


@dataclass(frozen=True)
class ChunkingConfig:
    size: int
    overlap: int


@dataclass(frozen=True)
class GraderConfig:
    correct_threshold: float
    incorrect_threshold: float


@dataclass(frozen=True)
class CorrectiveConfig:
    max_iter: int


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float


@dataclass(frozen=True)
class QdrantConfig:
    url: str
    collection: str


@dataclass(frozen=True)
class AppConfig:
    """Cấu hình toàn cục, gộp mọi khối con + bảng keyword chuyên khoa."""

    models: ModelsConfig
    retrieval: RetrievalConfig
    chunking: ChunkingConfig
    grader: GraderConfig
    corrective: CorrectiveConfig
    generation: GenerationConfig
    qdrant: QdrantConfig
    specialties: dict[str, list[str]] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #
def _load_dotenv(env_path: Path) -> None:
    """Nạp thủ công file .env vào os.environ (không phụ thuộc python-dotenv).

    Chỉ set biến chưa tồn tại để không đè biến môi trường thật.
    """
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _expand_env(value: object) -> object:
    """Thay thế ${VAR} bằng giá trị biến môi trường (đệ quy trên dict/list)."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), ""), value
        )
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# --------------------------------------------------------------------------- #
# API công khai
# --------------------------------------------------------------------------- #
def load_config(
    config_dir: Path | str | None = None,
    env_path: Path | str | None = None,
) -> AppConfig:
    """Đọc config.yaml + specialties.yaml + .env → AppConfig typed.

    Args:
        config_dir: thư mục chứa config (mặc định ``<repo>/config``).
        env_path: đường dẫn .env (mặc định ``<repo>/.env``).

    Returns:
        AppConfig đã resolve ${VAR} từ môi trường.
    """
    cfg_dir = Path(config_dir) if config_dir else _CONFIG_DIR
    env_file = Path(env_path) if env_path else _REPO_ROOT / ".env"

    _load_dotenv(env_file)

    raw = _expand_env(_read_yaml(cfg_dir / "config.yaml"))
    assert isinstance(raw, dict)
    specialties = _read_yaml(cfg_dir / "specialties.yaml")

    return AppConfig(
        models=ModelsConfig(**raw["models"]),
        retrieval=RetrievalConfig(**raw["retrieval"]),
        chunking=ChunkingConfig(**raw["chunking"]),
        grader=GraderConfig(**raw["grader"]),
        corrective=CorrectiveConfig(**raw["corrective"]),
        generation=GenerationConfig(**raw["generation"]),
        qdrant=QdrantConfig(**raw["qdrant"]),
        specialties=specialties,
    )


def load_prompt(name: str, config_dir: Path | str | None = None) -> str:
    """Đọc một file prompt trong ``config/prompts/`` theo tên (không đuôi .txt)."""
    cfg_dir = Path(config_dir) if config_dir else _CONFIG_DIR
    return (cfg_dir / "prompts" / f"{name}.txt").read_text(encoding="utf-8")

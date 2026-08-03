#!/usr/bin/env python3
"""
precommit_scan.py — read-only gate before `git commit`.

Scans STAGED content only (never the working tree, never other people's
branches) for things that are expensive to remove once they reach shared
history: secrets, unresolved conflict markers, large binaries, notebook
outputs, .env files.

Usage:
    python3 .claude/skills/git-commit/scripts/precommit_scan.py
    python3 ... --json          # machine-readable output
    python3 ... --max-mb 5      # override large-file threshold

Exit codes:
    0 = clean, or WARN findings only  -> safe to commit
    1 = at least one BLOCK finding    -> do NOT commit, fix first
    2 = script/git error              -> do NOT commit, investigate

This script NEVER writes to the repository, never stages, never commits,
never pushes. It only reads via `git show`/`git cat-file`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict

BLOCK = "BLOCK"
WARN = "WARN"

# --- detection rules ---------------------------------------------------------

SECRET_PATTERNS: list[tuple[str, str]] = [
    ("aws_access_key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("google_api_key", r"\bAIza[0-9A-Za-z_\-]{30,}\b"),
    ("huggingface_token", r"\bhf_[A-Za-z0-9]{30,}\b"),
    ("openai_key", r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b"),
    ("anthropic_key", r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
    ("slack_token", r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    ("telegram_bot_token", r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b"),
    ("private_key_block", r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    (
        "generic_credential_assignment",
        r"(?i)[A-Za-z0-9_.\-]*(?:api[_-]?key|secret|access[_-]?token|auth[_-]?token"
        r"|bot[_-]?token|password|passwd|credential)[A-Za-z0-9_.\-]*"
        r"\s*[:=]\s*[\"']([^\"'\s]{12,})[\"']",
    ),
]

# Anything matching this is a placeholder, not a live credential.
PLACEHOLDER = re.compile(
    r"(?i)(your[_-]?|example|placeholder|dummy|changeme|sample|fake|redacted"
    r"|x{4,}|\.\.\.|<[^>]{2,}>|\$\{|\{\{|os\.environ|getenv|process\.env"
    r"|st\.secrets|secrets\.)"
)

# Files where credential-shaped strings are expected and harmless.
SECRET_SCAN_SKIP = re.compile(
    r"(?i)(^|/)(\.env\.example|\.env\.template|\.env\.sample"
    r"|poetry\.lock|package-lock\.json|yarn\.lock|uv\.lock)$"
    r"|(^|/)precommit_scan\.py$"
)

ENV_FILE = re.compile(r"(^|/)\.env(\.[A-Za-z0-9_-]+)?$")
ENV_FILE_OK = re.compile(r"(?i)\.env\.(example|template|sample|dist)$")

BINARY_ARTIFACT = re.compile(
    r"(?i)\.(pt|pth|bin|safetensors|ckpt|onnx|h5|pkl|joblib|npy|npz"
    r"|parquet|feather|sqlite|db|duckdb|faiss|index|zip|tar|gz|7z)$"
)

CONFLICT_START = re.compile(r"^<{7}(\s|$)", re.M)
CONFLICT_END = re.compile(r"^>{7}(\s|$)", re.M)


@dataclass
class Finding:
    level: str
    rule: str
    path: str
    line: int
    detail: str


# --- git helpers -------------------------------------------------------------


def git(*args: str) -> str:
    res = subprocess.run(
        ["git", *args], capture_output=True, text=True, errors="replace"
    )
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def staged_paths() -> list[str]:
    out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [p for p in out.split("\0") if p]


def staged_blob(path: str) -> bytes:
    res = subprocess.run(
        ["git", "show", f":{path}"], capture_output=True
    )
    return res.stdout if res.returncode == 0 else b""


def staged_size(path: str) -> int:
    try:
        oid = git("rev-parse", f":{path}").strip()
        return int(git("cat-file", "-s", oid).strip())
    except Exception:
        return 0


# --- scanners ----------------------------------------------------------------


def scan_file(path: str, max_bytes: int) -> list[Finding]:
    findings: list[Finding] = []
    size = staged_size(path)

    if ENV_FILE.search(path) and not ENV_FILE_OK.search(path):
        findings.append(
            Finding(BLOCK, "env_file_staged", path, 0,
                    "Real .env file is staged. Ignore it and commit .env.example instead.")
        )

    if size > max_bytes:
        findings.append(
            Finding(BLOCK, "large_file", path, 0,
                    f"{size / 1_048_576:.1f} MB staged (limit {max_bytes / 1_048_576:.0f} MB). "
                    "Use a data loader/DVC/HF Hub, not git.")
        )
    elif BINARY_ARTIFACT.search(path) and size > 1_048_576:
        findings.append(
            Finding(WARN, "binary_artifact", path, 0,
                    f"Model/data artifact ({size / 1_048_576:.1f} MB) in git history is permanent.")
        )

    raw = staged_blob(path)
    if b"\0" in raw[:8192]:
        return findings  # binary: no text scan

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    # Unresolved merge conflict markers.
    if CONFLICT_START.search(text) or CONFLICT_END.search(text):
        for i, ln in enumerate(lines, 1):
            if ln.startswith("<<<<<<<") or ln.startswith(">>>>>>>"):
                findings.append(
                    Finding(BLOCK, "conflict_marker", path, i,
                            "Unresolved merge conflict marker in staged content.")
                )

    # Notebook outputs.
    if path.endswith(".ipynb") and '"output_type"' in text:
        findings.append(
            Finding(WARN, "notebook_output", path, 0,
                    "Notebook has saved outputs. Clear them to avoid noisy diffs / leaked data.")
        )

    # Secrets.
    if not SECRET_SCAN_SKIP.search(path):
        for i, ln in enumerate(lines, 1):
            if len(ln) > 4000:
                continue
            for rule, pat in SECRET_PATTERNS:
                m = re.search(pat, ln)
                if not m:
                    continue
                candidate = m.group(len(m.groups())) if m.groups() else m.group(0)
                if PLACEHOLDER.search(candidate) or PLACEHOLDER.search(ln):
                    continue
                findings.append(
                    Finding(BLOCK, f"secret:{rule}", path, i,
                            f"Possible live credential (masked: {mask(candidate)}).")
                )
                break

    return findings


def mask(s: str) -> str:
    s = s.strip()
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:4]}...{s[-2:]} [{len(s)} chars]"


# --- main --------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-mb", type=float, default=5.0)
    args = ap.parse_args()

    try:
        git("rev-parse", "--is-inside-work-tree")
        paths = staged_paths()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for p in paths:
        findings.extend(scan_file(p, int(args.max_mb * 1_048_576)))

    blocks = [f for f in findings if f.level == BLOCK]
    warns = [f for f in findings if f.level == WARN]

    if args.json:
        print(json.dumps(
            {"staged_files": len(paths),
             "verdict": "BLOCK" if blocks else "PASS",
             "findings": [asdict(f) for f in findings]},
            indent=2, ensure_ascii=False))
        return 1 if blocks else 0

    print(f"precommit_scan: {len(paths)} staged file(s)")
    if not paths:
        print("Nothing staged. Stage files first (git add <path>).")
        return 0

    for f in blocks + warns:
        loc = f"{f.path}:{f.line}" if f.line else f.path
        print(f"  [{f.level}] {f.rule:34s} {loc}\n         {f.detail}")

    if blocks:
        print(f"\nVERDICT: BLOCK ({len(blocks)} blocking, {len(warns)} warning). "
              "Do not commit until resolved.")
        return 1

    print(f"\nVERDICT: PASS ({len(warns)} warning). Safe to commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
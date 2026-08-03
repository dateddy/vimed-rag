#!/usr/bin/env python3
"""emit_issue.py — generate a well-formed ISSUE-NNN block and (optionally) append it to an issues log.

Safe by design:
  - Writes ONLY to the issues log the user specifies via --file (default: print to stdout).
  - NEVER touches source code.
  - Validates severity/status against the legend to prevent off-standard logs.

Example:
  python emit_issue.py --id 027 --severity HIGH --status OPEN --component training \
    --title "..." --description "..." --impact "..." --reproducer 'rg -n "x" f.py'
"""
import argparse
import datetime as _dt
import sys

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
STATUSES = ("OPEN", "INVESTIGATING", "DECISION_PENDING", "FIX_IN_PROGRESS", "RESOLVED")


def build_block(a: argparse.Namespace) -> str:
    lines = []
    lines.append(f"### ISSUE-{a.id} · {a.title}")
    lines.append("")
    if a.check:
        lines.append(f"- **Discovered in**: {a.check}")
    lines.append(f"- **Severity**: {a.severity}")
    lines.append(f"- **Status**: {a.status}")
    lines.append(f"- **Component**: {a.component}")
    lines.append("- **Description**:")
    lines.append(f"  {a.description}")
    lines.append("- **Impact**:")
    lines.append(f"  {a.impact}")
    lines.append("- **Reproducer**:")
    lines.append("  ```bash")
    for rline in a.reproducer.splitlines() or [a.reproducer]:
        lines.append(f"  {rline}")
    lines.append("  ```")
    if a.cause:
        lines.append("- **Hypothesized cause**:")
        lines.append(f"  {a.cause}")
    if a.linked:
        lines.append(f"- **Linked to**: {a.linked}")
    lines.append("")
    lines.append(f"<!-- emitted {_dt.date.today().isoformat()} -->")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate a standard ISSUE-NNN block for the audit log.")
    p.add_argument("--id", required=True, help="Issue number, e.g. 027")
    p.add_argument("--title", required=True, help="Short one-line title")
    p.add_argument("--severity", required=True, choices=SEVERITIES)
    p.add_argument("--status", default="OPEN", choices=STATUSES)
    p.add_argument("--component", required=True,
                   help="data / model / training / eval / ablation / repro ...")
    p.add_argument("--description", required=True, help="What was found, where (file:line)")
    p.add_argument("--impact", required=True, help="Consequence (validity / result / claim)")
    p.add_argument("--reproducer", required=True,
                   help="A runnable command to observe the issue again (MANDATORY)")
    p.add_argument("--cause", default=None, help="Hypothesized cause (optional)")
    p.add_argument("--check", default=None, help="Which check found it (e.g. CHECK_12)")
    p.add_argument("--linked", default=None, help="Related ISSUE-XXX (optional)")
    p.add_argument("--file", default=None,
                   help="Issues log to APPEND to. Leave empty = print to stdout (dry-run).")
    a = p.parse_args(argv)

    # Turn an empty reproducer into a clear error — Principle 3.
    if not a.reproducer.strip():
        p.error("--reproducer must not be empty: every finding needs a command to observe it again.")

    block = build_block(a)

    if not a.file:
        sys.stdout.write(block)
        sys.stderr.write("\n[dry-run] No --file, printed only. Add --file <log> to append.\n")
        return 0

    # Guard against writing into source by mistake: warn if the file has a common code extension.
    if a.file.endswith((".py", ".yaml", ".yml", ".ipynb", ".toml", ".cfg")):
        p.error(f"--file points at what looks like source ({a.file}). "
                f"Only append to an issues log (.md). Refusing to avoid mutating code.")

    try:
        with open(a.file, "a", encoding="utf-8") as fh:
            fh.write("\n" + block)
    except OSError as e:
        sys.stderr.write(f"[error] Could not write {a.file}: {e}\n")
        return 1

    sys.stderr.write(f"[ok] Appended ISSUE-{a.id} ({a.severity}) -> {a.file}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

---
name: git-commit
description: >-
  Turn a dirty working tree into clean, atomic commits with Conventional Commit
  messages, after a mandatory secret/conflict-marker scan. Use whenever the user
  wants to commit changes, asks for a commit message, says "commit this", "làm
  commit", "save my work", "check in what I did", "wrap up this change", or has
  uncommitted work they want recorded. Also use to split a messy diff into
  logical commits or to rewrite an unpushed commit message. Do NOT use for
  push, force-push, rebasing published history, reset --hard, or any history
  rewrite on commits that already exist on origin.
---

# git-commit

Produce a history that reads like a changelog: one commit = one intent, message
says *why*. This is a **solo project** (DEC-013), so the history is the only
reviewer there is — every rule below about scope and history rewriting is
load-bearing, not style.

## Hard rules — never violate

1. **Never `git push`.** Push is publishing. Report the commit and stop. If the
   user explicitly says "push", tell them the command and let them run it.
2. **Never `git add -A` / `git add .`.** Another person's work-in-progress may
   be in the tree. Stage explicit paths only.
3. **Never rewrite a commit that exists on `origin`.** Check with
   `git branch -r --contains <sha>` before any `--amend` or `rebase`.
   Unpushed and local-only → amend is fine. Otherwise → new commit.
4. **Never commit with a BLOCK verdict from the scanner.** No exceptions,
   no "I'll fix it in the next commit".
5. **Never resolve merge conflicts silently.** If the scanner finds conflict
   markers, stop and report — do not guess which side wins.

## Workflow

Run in order. Do not write a message from memory — read the actual diff.

1. **Inspect (read-only).**
   ```
   git status --porcelain=v1
   git diff --stat
   git diff                      # unstaged
   git diff --cached             # already staged
   git log --oneline -5
   ```
   Identify which changed files belong to the user's current intent, and which
   are pre-existing/other-person noise. Report anything you are leaving out.

2. **Group by intent.** One commit per coherent idea. Typical splits: source
   change vs. its tests (same commit), feature vs. unrelated dependency bump
   (separate), code vs. `brain/state/STATUS.md` update (separate).

3. **Stage explicit paths.** `git add path/a path/b` — never `-A`.

4. **Scan — mandatory gate.**
   ```
   python3 .claude/skills/git-commit/scripts/precommit_scan.py
   ```
   Exit 0 → proceed. Exit 1 → report findings verbatim, do not commit.
   Exit 2 → git/script error, investigate, do not commit.

5. **Propose the message, wait for confirmation** (default = confirm mode).
   Show: the exact `git commit` command, the file list, and the scan verdict.
   Skip confirmation only if the user says "auto-commit" in that turn — the
   scan gate still applies.

6. **Commit, then report** the short SHA, the message subject, and the files.
   Then stop. Do not push, do not start the next task.

## Message format — Conventional Commits

```
<type>(<scope>): <subject in imperative, ≤72 chars>

<body: why this change, what it replaces, what it does not do>

<footer: Refs: DEC-007 / Closes #12 / BREAKING CHANGE: ...>
```

**Types:** `feat` `fix` `docs` `test` `refactor` `perf` `chore` `build` `ci` `data`

**Scopes for this repo** (use these, don't invent):
`retrieval` `embed` `index` `grader` `rewrite` `generate` `pipeline` `eval`
`safety` `config` `brain` `app` `gate`

Body is required when the change touches behaviour. Omit it only for pure
`chore`/`docs` one-liners.

## Repo-specific commit rules

- **Contract changes require a decision reference.** If the diff touches
  `brain/contracts/**`, `config/**` thresholds, `max_iter`, or the grader
  routing logic, the body must cite a decision ID from
  `brain/decisions/DECISIONS.md`. No decision ID → stop and ask; a silent
  contract change is the single most expensive failure mode in this project.
- **Gate discipline.** Do not commit anything that wires real data, real
  embeddings, or a real index while Gate 0 is not GO. If the diff appears to do
  so, stop and ask.
- **State files are their own commit.** `brain/state/*` and `brain/handoff/*`
  → `docs(brain): ...`, never mixed with code.
- **Notebooks:** clear outputs before staging (scanner warns, does not block).

## Scanner

`scripts/precommit_scan.py` reads **staged content only**, never writes,
never stages, never pushes.

| Finding | Level |
|---|---|
| Live-looking credential (Google/HF/OpenAI/Anthropic/AWS/Slack/Telegram/generic `*_KEY = "..."`) | BLOCK |
| Real `.env` staged (`.env.example` is fine) | BLOCK |
| Unresolved conflict marker (`<<<<<<<` / `>>>>>>>`) | BLOCK |
| Staged file > 5 MB (`--max-mb` to override) | BLOCK |
| Model/data artifact > 1 MB | WARN |
| Notebook with saved outputs | WARN |

Placeholders (`your-key-here`, `${VAR}`, `os.environ[...]`, `changeme`) are
ignored, so `.env.example` and config templates do not trip it.

`--json` prints machine-readable output for hooks or CI.

**Limitation:** heuristic regex. It will miss oddly-formatted secrets. It is a
cheap last gate, not a replacement for `git-secrets`, `gitleaks`, or the
Semgrep/Trivy gates already in the CI lab.
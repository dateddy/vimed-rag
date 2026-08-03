---
name: code-review
description: >
  Discipline for serious code REVIEW/AUDIT before making any fix. This skill is
  NOT for understanding/navigating a codebase (that is zone-brain's job) — it is
  for JUDGING CORRECTNESS: finding bugs, checking whether the code still matches
  the original design (intent) or has drifted, verifying a claim in a report/paper,
  or GATING a fix (blocking careless edits). Use this skill whenever the user wants
  to "review code", "audit", "check whether the code is correct", "verify", "compare
  against the original design", "before applying a fix", or when there is suspicion
  that an agent modified code without controlling for risk. ALWAYS use this skill
  instead of reviewing by gut feel when the review has consequences (paper claim,
  retrain, production).
---

# Code Review — Audit discipline before you fix

Review is NOT reading code and then pronouncing a verdict. Review is **evidence-based
observation, keeping find separate from fix, and blocking every change until the risk
is explicitly accepted.**

This skill packages that discipline. It does **not** contain any specific project's
route/checklist — the route lives in the project's own file (e.g. `AUDIT_ROUTE.md`).

---

## Pairing with zone-brain

- **zone-brain** = the READ step: scan → map deps → zone the affected area → read minimal files.
- **code-review** = the JUDGE step: once you have context, assess correctness + log findings + gate the fix.

If the project has > 10 files: **run zone-brain first to load context**, then apply the
discipline below. Do not read the whole repo "just to be safe".

---

## 5 Core principles (do NOT skip)

### 1. READ-ONLY first, FIX later
Review is observation. While reviewing: **do not edit, do not reformat, do not "tidy up
along the way".** Fixing is a separate phase, opened only after Principle 5 is complete.

### 2. Evidence must be SELF-DERIVED — never accept pre-filled values
Do not trust a report, summary, comment, variable name, or another agent's word. Every
finding must point to a REAL `file:line` you read yourself, and you must run the reproducer
to see it with your own eyes.
> If you catch yourself copying numbers/conclusions from a document instead of from source → STOP, go read the source.

### 3. Reproducer is MANDATORY for every finding
Every finding must come with **a runnable command** to observe the issue again. No reproducer →
not a finding, just a guess → must not be logged as a finding.

A good reproducer must be: **deterministic** (same result on rerun), **read-only** (no mutation),
**fast** (seconds, not a full training epoch), and **have clear pass/fail** (a visible pattern /
an `assert` that is true-or-false, not output you have to interpret).

3 common forms:
```bash
# a) grep/rg — an issue in the STRUCTURE of the code
rg -n "suspicious_pattern" path/to/file.py

# b) python -c — an issue in DATA/CONFIG/numbers (add an assert for clear pass/fail)
python -c "import x; assert x.value == expected, x.value"

# c) short script — need a synthetic forward pass to check shape/finite loss
python check_forward.py   # prints shape + 'OK', or raises
```

### 4. Standard issue template
Log every finding with the exact structure below (use `scripts/emit_issue.py` to generate it so it never drifts):

- **severity**: `CRITICAL` (wrong result/claim) · `HIGH` (a major component is wrong, may not invalidate results) · `MEDIUM` (quality/minor drift) · `LOW` (cosmetic)
- **status**: `OPEN` · `INVESTIGATING` · `DECISION_PENDING` · `FIX_IN_PROGRESS` · `RESOLVED`
- **component** · **description + evidence (`file:line`)** · **impact** · **reproducer** · **hypothesized cause** (optional)

### 5. Risk gate BEFORE any fix
Do not fix until:
1. You list the fix's risks (regression, cascade, validity, reproducibility...).
2. You decide each risk explicitly: **ACCEPT / MITIGATE / ABORT**.
3. You log the `risk_accepted` list + a rollback plan (commit hash / `git revert`).
4. **ONLY THEN** do you touch the code.

> This is the principle that blocks the exact failure mode "agent fixes without controlling risk".
> A finding backed only by emotional pressure / assertion, with no evidence → not a reason to fix.

---

## Workflow (each review = one cycle)

| Step | Action |
|---|---|
| 1. Scope | Decide what to review. If the repo is large → run zone-brain first to load the zone. |
| 2. Observe | READ-ONLY. Read the real source, collect `file:line`. Change nothing. |
| 3. Reproduce | For each suspicion, write + run a reproducer. Can't reproduce → don't log it. |
| 4. Log | `emit_issue.py` generates the ISSUE-NNN block, append it to the project's issues log. |
| 5. Reconcile | Compare current-state vs intent (table below). Classify each component. |
| 6. Gate | For issues that need fixing: run the Risk gate (Principle 5). Risk not accepted → no fix. |
| 7. Fix + verify | Fix, rerun the reproducer to confirm it now PASSES, log risk_accepted + rollback. |

---

## Reconciliation (Intent vs Current)

The strongest payoff of rigorous review: catching **drift** from the original design
(this is exactly what catches a fix an agent silently reverted). For each component,
compare intent ↔ real code, and classify:

- ✅ **MATCHES** — code matches intent
- ⚠️ **DRIFT** — differs from intent, must assess impact (sometimes worse, sometimes better)
- ❌ **BROKEN** — code has a bug
- 🤔 **UNKNOWN** — not yet audited
- 🆕 **IMPROVEMENT** — drift but better than intent → keep, record as a scope change

Precondition: "intent" must be a fixed design (north star). If the project has none,
require the user to lock intent first — with no baseline to compare against, drift cannot be detected.

---

## Generating an ISSUE block

```bash
python scripts/emit_issue.py \
  --id 027 --severity HIGH --status OPEN --component training \
  --title "Scheduler applies wrong warmup in Phase 2" \
  --description "trainer.py:344 only sets metadata, does not instantiate a warmup schedule" \
  --impact "Encoder LR jumps straight into cosine, differs from intent 'Phase 2 warmup'" \
  --reproducer 'rg -n "phase2_warmup_steps|scheduler.step" src/training/trainer.py' \
  --file 01_OPEN_ISSUES.md          # omit --file to print to screen only
```

No `--file` → prints to stdout (dry-run, safe). With `--file` → **appends** to the log
(never overwrites source code). The script validates severity/status against the legend.

---

## Common mistakes to avoid

```
❌ DON'T: edit code while reviewing ("while I'm here")
❌ DON'T: log a finding with no reproducer
❌ DON'T: copy numbers/conclusions from a report instead of reading the source
❌ DON'T: apply a fix before explicitly accepting the risk
❌ DON'T: use this skill to "understand the codebase" — that's zone-brain

✅ DO: stay read-only until the risk gate is done
✅ DO: one runnable reproducer per finding
✅ DO: evidence = file:line you read yourself
✅ DO: reconcile against intent, classify MATCHES/DRIFT/BROKEN
✅ DO: after fixing, rerun the reproducer to confirm it PASSES
```

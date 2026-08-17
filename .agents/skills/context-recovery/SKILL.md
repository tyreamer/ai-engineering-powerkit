---
name: context-recovery
description: "Reconstructs trustworthy project state when continuing interrupted or inherited work. Use after compaction, a new coding session, teammate handoff, stale task card, or when claims about completed work must be verified against the repository."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: foundation
---

# Context Recovery

## Purpose

Resume work from evidence instead of conversational memory or optimistic status reports.

## Recovery order

1. Read current repository instructions.
2. Inspect `git status`, current branch, recent commits, and uncommitted diff.
3. Locate the task card, implementation report, decision log, or issue referenced by the work.
4. Verify claimed files, tests, migrations, and behavior directly.
5. Run the smallest relevant validation needed to establish current health.
6. Identify completed, partially completed, blocked, and never-started work.
7. Produce the next safe action.

## Truth model

Classify statements as:

- **Verified complete** — code and required evidence exist.
- **Implemented, not fully verified** — change exists but required proof is missing.
- **Partial** — only a subset of the intended behavior exists.
- **Blocked** — a specific external or material decision prevents progress.
- **Not present** — no evidence the work exists.
- **Contradicted** — repository evidence conflicts with the prior report.

Never upgrade a claim because a task card says “done.”

## Recovery packet

Provide:

- Current branch and working-tree state.
- Relevant recent commits.
- What is actually implemented.
- What evidence exists.
- What remains.
- Any discrepancies between reports and source.
- The next bounded action.
- Commands required to continue.

## Rules

- Preserve uncommitted work.
- Do not reset, clean, checkout, or rewrite history merely to simplify recovery.
- Do not rerun expensive suites before targeted inspection indicates they are needed.
- Do not infer a missing file “never existed” without checking history when the claim matters.
- Keep historical plans separate from current implementation truth.

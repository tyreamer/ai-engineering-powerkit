---
name: workload-router
description: "Selects the lightest effective execution mode, reasoning depth, and subagent pattern for an engineering task. Use to control cost, latency, context pollution, and quality instead of applying maximum effort or parallelism to every request."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.2.0"
  profile: foundation
---

# Workload Router

## Purpose

Match the workflow to the task. More agents, tokens, and ceremony are not automatically better.

## Classify the task

Evaluate:

- Scope: localized, multi-file, cross-system.
- Ambiguity: clear, repo-resolvable, materially unresolved.
- Risk: low, moderate, high.
- Work type: read-heavy, write-heavy, runtime, research, or mixed.
- Independence: whether subtasks can be completed without overlapping state.
- Evidence needs: static, tests, integration, runtime, external documentation.
- Reversibility: easy rollback versus data or contract consequences.

## Effort axis

### Fast

Use for clear, reversible, low-risk tasks.

- One main agent.
- Targeted inspection.
- Small edit.
- Targeted validation.

### Standard

Use for ordinary features and bugs.

- Main agent owns decisions and writing.
- One or two read-only subagents may map code or inspect tests.
- Explicit contract and verification.
- Diff review before completion.

### Deep

Use for architecture, migrations, intermittent bugs, cross-cutting work, or high reasoning complexity.

- Separate exploration, architecture, verification, and adversarial review.
- Use higher reasoning capability where available.
- Require rollback and uncertainty reporting.
- Keep one writer unless file boundaries are truly independent.

## Risk axis

Select risk independently from effort:

- **Normal** — ordinary reversible engineering work.
- **Elevated** — meaningful compatibility, data, dependency, rollout, or external-write consequence.
- **High** — security, privacy, authorization, secrets, production data, billing, destructive actions, public contracts, or irreversible consequence.

Risk tightens permissions, checkpoints, verification, isolation, rollback, and proof. It does not automatically increase agent count or root reasoning. A small credential edit may be `FAST × HIGH`; a large read-only architecture study may be `DEEP × NORMAL`.

Keep `HIGH_RISK` as a public compatibility label when an existing proof or command interface requires one. Internally use `risk: HIGH` plus the independently selected effort.

### Parallel read swarm

Use when several independent evidence questions can be researched simultaneously.

Examples: code path mapping, documentation verification, test-gap review, threat review.

Avoid when findings are tightly sequential or the cost of synthesis exceeds the work.

## Routing rules

- Use fast capability for deterministic searches, summarization, formatting, and narrow repetitive work.
- Use deep capability for ambiguous causality, architecture tradeoffs, security, migrations, and final synthesis.
- Use multimodal capability when screenshots, diagrams, or runtime visual evidence materially affect the answer.
- Do not use parallel write agents on overlapping files.
- Never let economy or latency preferences remove risk-required verification or checkpoints.
- Cap delegation. Start with the fewest agents likely to improve the result.
- Return concise evidence packets, not raw logs.

## Output

Routing may remain internal. When useful, state:

- Selected effort and risk.
- Delegated investigations.
- Single-writer owner.
- Required quality gates.

Do not turn routing into a delay before work begins.

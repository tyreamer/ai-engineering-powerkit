---
name: decision-handoff
description: "Creates a concise, evidence-backed checkpoint after implementation or analysis. Use for session handoffs, task closure, pull request preparation, resuming later, or preventing future agents from rediscovering decisions and verification state."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: foundation
---

# Decision Handoff

## Purpose

Leave the repository and the next person with a truthful, actionable state snapshot.

## Handoff content

Include:

- **Outcome** — what changed or what was decided.
- **Files and contracts affected** — major paths, APIs, schemas, or configuration.
- **Decisions** — choices made and why.
- **Evidence** — commands run, tests passed, runtime observations, screenshots, or logs.
- **Not verified** — anything the current environment could not prove.
- **Risks and follow-ups** — real remaining concerns, not generic caveats.
- **Working-tree state** — uncommitted changes or generated artifacts.
- **Next action** — the smallest useful continuation step.

## Decision capture

Write a durable ADR or decision-log entry when a choice:

- Changes architecture or a public contract.
- Establishes a reusable pattern.
- Rejects a plausible alternative future teams may revisit.
- Changes security, privacy, persistence, retention, or ownership.
- Would otherwise be lost in chat history.

Do not create ADRs for routine local implementation details.

## Closure language

Use exact status:

- Complete and verified.
- Implemented; runtime verification pending.
- Partial.
- Blocked by a named decision or dependency.
- Analysis only; no code changed.

Avoid “done” when the evidence is narrower than the claim.

## Handoff quality test

A new agent should be able to continue without rereading the entire conversation and without mistaking plans for implementation.

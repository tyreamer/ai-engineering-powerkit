---
name: engineering-task-orchestrator
description: "Runs a complete evidence-to-delivery workflow for complex coding tasks. Use for multi-file features, architecture changes, significant bugs, migrations, or work that needs planning, implementation, verification, review, and a clean handoff."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: foundation
---

# Engineering Task Orchestrator

## Purpose

Provide one reliable entry point for complex engineering work without forcing every task through the same heavyweight ceremony.

## Core loop

Use the smallest applicable version of this loop:

1. **Preflight** — preserve intent and resolve only material ambiguity.
2. **Map** — locate the real execution path and repository rules.
3. **Contract** — define outcome, boundaries, invariants, and proof.
4. **Impact** — identify affected code, data, contracts, security, UX, and operations.
5. **Slice** — choose the smallest end-to-end increment that creates useful evidence.
6. **Plan** — produce an executable sequence tied to files and checks.
7. **Implement** — use one writer by default and keep changes bounded.
8. **Verify** — prove static, automated, integration, and runtime behavior as applicable.
9. **Challenge** — try to falsify correctness and find missing cases.
10. **Handoff** — record changes, evidence, decisions, risks, and remaining work.

Invoke or follow the relevant PowerKit skills for these stages. Do not invoke every skill mechanically.

## Workflow classes

### Fast path

Use for clear, low-risk, localized changes:

- Inspect the owning code and nearby tests.
- Make the smallest defensible change.
- Run targeted validation.
- Review the diff.
- Report evidence.

### Standard path

Use for multi-file features and ordinary bugs:

- Run Prompt Preflight.
- Map the relevant flow.
- Establish a Task Contract.
- Plan a vertical slice.
- Implement.
- Run the Verification Loop and Anti-Slop Review.
- Produce a Decision Handoff.

### High-risk path

Use when security, data migration, public contracts, money movement, permissions, destructive actions, or broad architecture are involved:

- Add Change Impact Analysis.
- Add Adversarial Review.
- Add Security and Privacy Review.
- Add API Contract Guardian or Migration Planner where relevant.
- Require rollback evidence and explicit unresolved risks.

## Parallelism

Use subagents only when independent work benefits from isolation or concurrency.

Good parallel work:

- Read-only codebase mapping.
- Documentation verification.
- Test and log analysis.
- Independent threat, compatibility, or UX reviews.

Default to a single writer. Multiple agents editing overlapping files create merge risk and dilute ownership.

## Context discipline

Keep the main thread focused on requirements, decisions, progress, and final evidence. Send noisy searches, logs, and broad exploration to bounded subagents. Require concise evidence packets back.

## Completion rule

Do not call the task complete merely because code was written or tests passed. Completion requires evidence appropriate to the change and an honest statement of anything not verified.

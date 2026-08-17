---
name: verification-loop
description: "Proves that a change works through a risk-based ladder of static checks, targeted tests, broader integration, runtime behavior, and diff review. Use after implementation and before claiming completion."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: quality
---

# Verification Loop

## Purpose

Replace “the code looks right” with evidence appropriate to the change.

## Verification ladder

Climb only as high as the task requires, but do not skip a level that carries material risk:

1. **Static** — format, lint, type checks, compilation, schema validation.
2. **Targeted automated** — tests closest to the changed behavior.
3. **Broader automated** — affected package, integration, or regression suite.
4. **Runtime** — launch the actual product or service and exercise the changed path.
5. **Operational** — logs, metrics, traces, migrations, deployment, or rollback behavior.
6. **Diff review** — inspect the final patch for unintended changes, secrets, placeholders, and scope drift.

## Method

1. Derive checks from the Task Contract and Change Impact Analysis.
2. Locate canonical commands from repository evidence.
3. Run narrow checks early, then broader checks as confidence grows.
4. Verify negative, failure, permission, empty, loading, and cancellation paths when relevant.
5. For user-visible work, inspect the running behavior rather than relying only on unit tests.
6. Record exact commands, results, and environment limitations.
7. Re-run checks affected by the final edits.
8. Do not hide pre-existing failures; separate them from regressions introduced by the change.

## Evidence standard

Report:

- Command or action.
- Result.
- What behavior it proves.
- What it does not prove.
- Any skipped or unavailable checks.

## Failure handling

When a check fails:

- Determine whether it is caused by the change.
- Fix the cause rather than weakening the test.
- Do not delete assertions, reduce coverage, or add broad ignores merely to get green.
- If the failure is pre-existing, preserve evidence and state the impact on confidence.

## Completion rule

A task is not fully verified when required runtime, integration, migration, or environment proof is unavailable. Use precise status language.

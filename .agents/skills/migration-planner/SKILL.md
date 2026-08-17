---
name: migration-planner
description: "Designs safe staged migrations for data, APIs, auth, infrastructure, or architecture. Use when old and new behavior must coexist, deployment order matters, backfills are required, or rollback and compatibility cannot be left implicit."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: delivery
---

# Migration Planner

## Purpose

Move from current to target state without assuming an instantaneous cutover.

## Migration concerns

Inspect:

- Current and target contracts.
- Producers, consumers, and ownership.
- Compatibility window.
- Schema expansion and contraction.
- Dual read, dual write, translation, or shadow behavior.
- Backfill, validation, reconciliation, and repair.
- Feature flags and cohort rollout.
- Deployment order across services.
- Monitoring and abort thresholds.
- Rollback feasibility after new data is written.
- Cleanup and final removal of legacy paths.

## Default pattern

Prefer expand → migrate → verify → contract:

1. Add backward-compatible target capability.
2. Deploy readers that accept old and new.
3. Begin new writes or transformation under containment.
4. Backfill historical state.
5. Reconcile and measure.
6. Gradually shift traffic or ownership.
7. Stop legacy writes.
8. Remove compatibility only after evidence and rollback windows are satisfied.

Not every migration needs dual writes. Choose the simplest strategy that satisfies the risk.

## Migration plan output

For each phase include:

- Preconditions.
- Code and data changes.
- Deployment order.
- Observability.
- Success and abort criteria.
- Rollback behavior.
- Data repair procedure.
- Exit evidence.
- Irreversible point, if any.

## Rules

- Never assume rollback means deploying the old binary.
- Account for data written under the new semantics.
- Avoid long-lived dual systems without explicit removal criteria.
- Test mixed-version operation.
- Define ownership for backfill and reconciliation.
- Keep user-visible failure and support procedures explicit.

# ADR 0003: Separate effort, risk, and platform capability negotiation

## Status

Accepted for PowerKit 0.4.0.

## Context

PowerKit previously exposed `FAST`, `STANDARD`, `DEEP`, and `HIGH_RISK` as one workload-depth scale. That was useful for routing and proof presentation but conflated resource intensity with consequence. A narrow security fix may need low reasoning and deep safety checks; a broad read-only architecture audit may need high reasoning without high-risk write controls.

Platform controls also differ by client, surface, and lifecycle. A launch-time model, sandbox, or tool flag does not prove that an active root task changed. Treating unsupported behavior as native enforcement would make completion claims unsafe.

## Decision

- Use `FAST`, `STANDARD`, and `DEEP` as the internal effort axis.
- Use `NORMAL`, `ELEVATED`, and `HIGH` as the independent risk axis.
- Preserve `HIGH_RISK` as a compatibility depth for Proof Pack output.
- Keep the canonical policy vendor-neutral and put model identifiers and native setting translations in platform adapters.
- Version capability contracts by platform surface and classify each control as `NATIVE`, `PARTIAL`, `EMULATED`, or `UNAVAILABLE`.
- Distinguish `CURRENT_SESSION` from `LAUNCHER` controls.
- Return `PROCEED`, `CHECKPOINT`, or `STOP`; do not silently proceed when an explicit high-risk boundary cannot be enforced.
- Apply project cost and latency preferences only to resource selection. They may not weaken risk-derived permissions, verification, checkpoints, rollback, or proof.
- Keep one overlapping implementation writer. Independent verification remains required when risk or effort justifies it, even when it runs sequentially.
- Keep capability tables out of normal prompt context; generate only a compact selected-policy directive.

## Consequences

- Routing, execution, verification, and proof now share an explicit policy contract.
- Platform differences remain visible instead of being flattened into lowest-common-denominator behavior.
- Launcher integrations can apply native settings without claiming that the broker controls an already-running root session.
- Capability manifests require maintenance as clients evolve.
- Relative cost and latency remain honest ordinal estimates until real billing and timing telemetry is available.
- High-risk tasks may checkpoint or stop on weaker surfaces even when the same task could proceed under a stronger launcher or hosted environment.

# ADR 0004: Make live client certification the next product priority

## Status

Accepted as the planning direction after PowerKit 0.4.0.

## Context

PowerKit has static routing fixtures, deterministic lifecycle tooling, Proof Pack evidence, context-budget estimates, and an Execution Broker with platform capability contracts. These foundations show that the distribution is internally consistent, but they do not establish whether PowerKit improves real coding-agent outcomes relative to an unmodified client.

Several plausible follow-on investments—repository intelligence, rollback, runtime UI automation, broader sandboxing, and additional skills—would add cost and architecture before their value is measured. Platform behavior also differs enough that documentation-backed parity cannot substitute for live evidence.

## Decision

- Make a paired Live Client Certification harness the primary objective for PowerKit 0.5.
- Compare vanilla and PowerKit-enabled runs using the same request, client version, repository fixture, and isolated starting state.
- Score observable task outcome, constraint preservation, routing, verification, and completion honesty; report resource costs separately.
- Build only the local, content-light Flight Recorder needed to support reproducible certification evidence.
- Start with automatable Codex and Claude Code CLI surfaces. Keep Copilot capability-only until a reproducible automation surface exists.
- Preserve failures, timeouts, missing telemetry, and disqualifying safety events in results.
- Gate larger autonomy and optimization features on evidence from certification rather than including them in the v0.5 implementation scope.
- Keep required cloud services, public leaderboards, automatic trace upload, broad marketplaces, default swarms, new protocols, and replacement models out of scope.

The normative protocol, privacy boundary, rubric, and exit criteria live in [Live Client Certification](../LIVE_CLIENT_CERTIFICATION.md).

## Consequences

- PowerKit 0.5 has a narrow, testable product objective instead of a collection of unrelated features.
- Comparative claims require versioned fixtures, repeated runs, and disclosed safety failures and costs.
- Flight Recorder design is constrained by certification and privacy needs rather than becoming general telemetry infrastructure.
- Copilot may trail Codex and Claude Code in behavioral certification without being represented as equivalent.
- Repository Intelligence, Visual Runtime QA, transactional rollback, and deeper sandbox enforcement remain candidates until evidence or safety requirements promote them.
- The harness can later evolve into a Repository Eval Forge without requiring a separate benchmark architecture.

# Roadmap

The roadmap distinguishes delivered foundations from the next measured objective and from evidence-gated candidates. A listed candidate is not a release commitment. [ADR 0004](decisions/0004-live-client-certification-first.md) records the prioritization decision, and [Live Client Certification](LIVE_CLIENT_CERTIFICATION.md) defines its acceptance contract.

## v0.1.0

- Canonical open-format skill library.
- Project and user installer.
- Codex, Claude Code, and Copilot adapters.
- Specialized agent profiles.
- Static validation.
- Routing cases.
- Optional catastrophic-command hook.
- Team rollout and security guidance.
- Codex bootstrap and hardening prompts.

## v0.1.1

- Installer path-containment and managed-ownership hardening.
- Stale managed-artifact detection without automatic deletion.
- Tracked-file-only release archives.
- Current Bash and PowerShell hook examples with fail-closed event parsing.
- Stronger structural, adapter-parity, routing-data, and version validation.
- Behavioral installation, hook, verification, validator, and package tests.

## v0.2.0

- Agent-native bootstrap, pinned project state, deterministic lifecycle CLI, safe sync/update/uninstall, and wheel/source/release packaging.
- Canonical `pk` command skill with automatic routing and eight explicit modes.
- Progressive-disclosure routing reference and deterministic command manifest.
- Native `$pk` Codex skill invocation, `/pk` Claude skill invocation, and managed Copilot `/pk` prompt adapter for supported IDEs.
- Installer, validation, routing-eval, documentation, and safe managed-update support for the command layer.

## v0.3.0

- Offline context inventory for always-on, discovery, selected-skill, reference, agent, and adapter layers.
- Platform-aware Codex, Claude, and Copilot estimates with explicit observed-data limitations.
- Ranked context recommendations, configurable budgets, release baselines, CI regression protection, and concise doctor integration.
- Context-audit lifecycle and safety coverage with PowerKit-on-PowerKit dogfooding.

## v0.4.0

- Independent FAST/STANDARD/DEEP effort and NORMAL/ELEVATED/HIGH risk axes with HIGH_RISK Proof Pack compatibility.
- Deterministic Execution Broker for resources, permissions, iteration bounds, verification, proof, and cost/latency projections.
- Versioned Codex, Claude Code, and GitHub Copilot capability negotiation across current-session and launcher control planes.
- Human, compact, and JSON diagnostics; bounded local version probes; mode-0600 decision traces; Proof Pack binding; Codex/Claude setting application attempts; and fail-closed PROCEED/CHECKPOINT/STOP behavior.
- Context-budget integration, broker dogfood scenarios, schema and installer/package wiring, and cross-platform contract tests.

## v0.5 — live certification

The first slice—versioned case/trace/result contracts, six executable fixtures, and offline plan/scoring—is implemented. Live client launch, isolated paired preparation, trace collection, repetitions, and comparative reports remain release work.

- A paired live-client harness that runs the same repository task with vanilla and PowerKit-enabled clients from identical isolated starting states.
- Initial behavioral certification for automatable Codex and Claude Code CLI surfaces; Copilot remains capability-only until a reproducible automation surface is available.
- A versioned task corpus and deterministic scoring for task outcome, constraint preservation, routing, verification, and completion honesty.
- A minimal, local, content-light Flight Recorder for lifecycle events, effects, verification, timing, and supported host telemetry.
- Separate quality and resource reporting across repeated runs, with failures, timeouts, and disqualifying safety events preserved.
- Machine-readable results and a concise local comparison report with exact client, adapter, corpus, PowerKit, and repository-fixture versions.
- Privacy, redaction, isolation, interruption, and baseline-contamination tests.

The v0.5 exit criteria and non-goals are defined in [Live Client Certification](LIVE_CLIENT_CERTIFICATION.md). This release does not include a required cloud dashboard, public leaderboard, broad marketplace, or generic telemetry system.

## Evidence-gated candidates

| Initiative | Status | Prioritization rule |
|---|---|---|
| Proof Pack | Delivered in v0.3.0 | Extend only when certification exposes missing evidence. |
| Context Budget Auditor | Delivered in v0.3.0 | Join static estimates with observed telemetry only when provenance is available. |
| Platform Capability Contract | Implemented in the v0.4.0 candidate | Maintain against tested client versions; do not equate documentation with certification. |
| Effort / Model / Budget Broker | Implemented in the v0.4.0 candidate | Validate its routing and resource effects in v0.5 before expanding policy. |
| Flight Recorder | v0.5 enabler | Implement only the private, content-light event model required by certification. |
| Trust and MCP Firewall | Candidate: safety prerequisite | Prioritize before broader high-risk autonomy or untrusted external-data execution. |
| Optional sandbox execution | Partial foundation in v0.4.0 | Expand only where capability negotiation identifies an enforceable client boundary. |
| Visual Runtime QA | Candidate | Start with certification cases; promote when source-only UI verification fails materially. |
| Repository Intelligence Cache | Candidate | Build only if traces show repeated repository discovery is a meaningful cost. |
| Transactional checkpoints and rollback | Candidate | Require ownership-safe restoration that preserves unrelated human work. |
| Generated adapter synchronization | Candidate | Prioritize when adapter drift becomes measurable maintenance cost. |
| Repository Eval Forge | Long-term evolution | Grow from the stable paired harness after cross-repository trials. |

Explicit non-goals remain a giant public skill marketplace, automatic installation of untrusted skills, a required cloud dashboard, default swarm execution, self-rewriting policy, a new MCP protocol, a new coding model, and replacement of native client capabilities.

Other unscheduled release candidates remain repository-specific command and verification discovery, plugin packaging for supported marketplaces, signed artifacts and checksums, enterprise managed-policy examples, domain packs, and a browser-based catalog explorer. They do not share v0.5 priority unless they become necessary to run or distribute certification.

## v1.0

- Stable compatibility contract.
- Versioned migration guide.
- Repository Eval Forge evolved from the live-certification protocol.
- Proven team metrics across multiple repositories, with reproducible vanilla-versus-PowerKit comparisons.
- Maintainer and security response process.
- Release automation and verified installation paths.

# Roadmap

PowerKit's roadmap separates shipped behavior from partial foundations and evidence-gated candidates. A candidate is not a release commitment. [ADR 0004](decisions/0004-live-client-certification-first.md) keeps live client certification ahead of broader autonomy work, and [Live Client Certification](LIVE_CLIENT_CERTIFICATION.md) defines the current acceptance contract.

Status terms in this document are strict:

- **Delivered** means the stated scope has deterministic implementation and repository tests.
- **Partial** means useful code or policy exists, but a defining end-to-end behavior is still missing.
- **Planned** means no product implementation should be inferred from skills, documentation, or adjacent infrastructure.
- **Evidence-gated** means recorder or certification results must justify promotion before implementation begins.

## Released foundation

### v0.1.0-v0.1.1

- Canonical open-format skill library, project and user installer, Codex/Claude Code/Copilot adapters, specialized agent profiles, static validation, and routing cases.
- Installer containment, ownership, backup, stale-artifact, hook, packaging, and behavioral-test hardening.

### v0.2.0

- Agent-native bootstrap, pinned project state, deterministic lifecycle CLI, safe sync/update/uninstall, and release packaging.
- Canonical `pk` command skill with automatic routing, eight explicit modes, constraint preservation, progressive disclosure, and native platform adapters.

### v0.3.0

- Proof Pack with a canonical local proof manifest, adaptive Completion Brief, offline HTML Proof Report, evidence freshness, privacy bounds, and independent-verifier provenance.
- Offline Context Budget Auditor with platform-aware estimates, artifact-layer attribution, recommendations, configurable budgets, release baselines, and CI regression protection.

### v0.4.0

- Independent FAST/STANDARD/DEEP effort and NORMAL/ELEVATED/HIGH risk axes.
- Deterministic Execution Broker for resource, permission, checkpoint, verification, proof, cost, and latency policy.
- Versioned platform capability contracts for Codex, Claude Code, and GitHub Copilot with current-session versus launcher negotiation and explicit `NATIVE`, `PARTIAL`, `EMULATED`, and `UNAVAILABLE` states.
- Local, content-light broker decision traces and Proof Pack binding.

### v0.5.0-v0.5.2

- Versioned certification case, trace, and result contracts.
- Six executable pilot fixtures and deterministic offline validation/scoring through `powerkit certify pilot`.
- Fail-closed checks for fixture identity, baseline contamination, unsupported trace fields, evidence references, telemetry provenance, unauthorized writes, and fabricated verification.
- Automatic `pk` routing for ordinary engineering tasks.

These releases do **not** launch paired live clients or collect their traces. The certification command currently validates a plan or scores supplied evidence.

## Next build: v0.6 paired live certification runner

The next release should finish the missing live path rather than start another independent platform feature. Its smallest useful vertical slice is one paired Codex case executed from identical disposable starting states, with a vanilla run and a PowerKit run collected and scored end to end.

Build it in this order:

1. **One-client runner slice** — prepare two disposable worktrees for one bundled case, prove PowerKit assets are absent from the vanilla state and present at the pinned version in the treatment state, launch Codex without a shell, use a narrow collector for schema-required evidence, and feed both traces into the existing scorer.
2. **Recorder and containment** — harden that collector into the minimum content-light event recorder required by certification, with mode-`0600` local storage where supported, retention/deletion controls, timeouts, cancellation, interrupted-run preservation, synthetic-secret redaction tests, and source/prompt/output non-retention tests.
3. **Second client family** — add the same runner contract for Claude Code without weakening isolation, provenance, or missing-telemetry semantics.
4. **Repetition and reporting** — preserve every repetition, failure, timeout, and cancellation; report quality dimensions separately from turns, elapsed time, context, and provider-reported tokens; emit a concise local paired comparison.
5. **Release certification expansion** — grow from the six-case pilot to the complete release corpus and repetition requirements in [Live Client Certification](LIVE_CLIENT_CERTIFICATION.md), including UI/runtime and correct-stop cases when the runner can collect their evidence honestly.
6. **Flight Recorder explanation** — after certification is no longer blocked on runner work, add `pk why` over stable event provenance. It must derive its explanation from recorded routing, broker, workflow, and verification events and must not invent unavailable host telemetry. It is not a v0.6 exit prerequisite.

The first slice proves the runner architecture. It does not support a comparative product claim by itself. The release remains incomplete until both automatable client families, privacy boundaries, partial-result behavior, repetitions, and local reports satisfy the published exit criteria.

## Feature inventory at v0.5.2

| # | Initiative | Status | Repository evidence and remaining gap |
|---:|---|---|---|
| 1 | Flight Recorder | **Partial; next-build enabler** | Broker decision traces and certification trace contracts exist. No live event collector, task-wide timeline, retention command, or `pk why` path exists. |
| 2 | Live Client Certification Harness | **Partial; next build** | Six fixtures, schemas, validation, and deterministic scoring are implemented. Live paired preparation, launch, collection, repetition, and comparison reports are missing. |
| 3 | Proof Pack | **Delivered** | `powerkit proof` creates, inspects, and deletes canonical local proofs with adaptive text/HTML presentation and freshness checks. Extend only when certification exposes a concrete evidence gap. |
| 4 | Context Budget Auditor | **Delivered for static attribution; observed usage pending** | `powerkit context audit` attributes modeled PowerKit context and protects baselines in CI. Actual client/provider context and token observations must come from provenance-labeled recorder telemetry. |
| 5 | Platform Capability Contract | **Delivered; certification pending** | Versioned Codex, Claude Code, and Copilot surface contracts drive broker negotiation. Documentation and launcher setting application are not behavioral certification. |
| 6 | Execution / Model / Budget Broker | **Delivered; certification pending** | Effort and risk independently select resources and safeguards, with `PROCEED`, `CHECKPOINT`, and `STOP` outcomes. v0.6 must measure whether those choices affect live behavior as intended. |
| 7 | Work Memory Ledger | **Planned** | Context recovery and decision-handoff skills are procedural aids, not a durable, queryable engineering-state ledger. |
| 8 | Structured Repository Intelligence | **Planned; evidence-gated** | Repository cartography is performed on demand. There is no incremental symbol/module/contract cache or selective retrieval store. Promote only if traces show repeated discovery is a material cost. |
| 9 | Progress Supervisor | **Planned** | No task monitor currently detects stagnation, repeated strategies, edit thrashing, or spend without outcome improvement. |
| 10 | Experiment Lineage | **Planned** | No candidate graph, comparison record, or durable `current-best` implementation state exists. |
| 11 | Transactional Checkpoints and Rollback | **Partial policy foundation** | The broker can require a checkpoint and the installer protects its own managed files, but PowerKit cannot checkpoint and restore a task worktree while preserving unrelated human changes. |
| 12 | Grounded Feedback Loop | **Partial workflow foundation** | Debugging and verification skills require environment feedback, but there is no stateful runtime primitive that records hypothesis, informative action, result, and next decision across a long task. |
| 13 | Trust + MCP Firewall | **Partial policy foundation** | Security guidance separates authorization from evidence and the broker can restrict some tools on supported surfaces. No enforced provenance boundary prevents external data or tool output from promoting itself into authority. |
| 14 | Scoped / Sandboxed Execution | **Partial platform foundation** | Capability contracts and broker-owned launches map to native controls where available. The broker explicitly is not a universal security sandbox, and active sessions cannot always be tightened retroactively. |
| 15 | Runtime Evidence Adapter Framework | **Planned** | Verification and Proof Pack can reference runtime evidence, but there is no common adapter lifecycle for browsers, APIs, databases, performance, CI/CD, infrastructure, or telemetry. |
| 16 | Visual Runtime QA | **Partial workflow foundation; evidence-gated** | UI review skills and a runtime observer role exist. Standardized launch, state exercise, accessibility checks, screenshots, console capture, and Proof Pack wiring are not implemented. |
| 17 | Long-Horizon Autonomous Mode | **Planned** | The required durable state, progress control, experiment lineage, safe rollback, and grounded runtime loop do not yet exist as an integrated system. |
| 18 | Repository Eval Forge | **Partial seed** | The certification corpus and deterministic paired scorer are the seed. Repository-owned task authoring, controlled multi-repository trials, and comparative dashboards/reports remain future work. |

## Ordered build-out after certification

After the paired live runner is stable, use this dependency order.

1. **Enforce the safety envelope** — define the Trust + MCP Firewall authority/provenance contract, enforce it through broker-backed scoped execution on supported surfaces, then add ownership-safe task checkpoints and rollback. Broader autonomy must not precede trustworthy authority boundaries and recoverable experiments.
2. **Persist durable work state** — build the Work Memory Ledger over explicit goals, decisions, attempts, evidence references, failures, and next actions. Do not retain hidden reasoning transcripts. Add Experiment Lineage on top of the ledger and transactional checkpoints so candidates can be compared and a `current-best` state can be restored safely.
3. **Close the grounded control loop** — formalize `hypothesis → smallest informative action → real feedback → state update → next action` using recorder events and ledger state, then add the Progress Supervisor. Start with deterministic stagnation and repetition signals before allowing model-directed strategy changes.
4. **Promote measured accelerators** — build Structured Repository Intelligence only if certification traces show repeated repository reconstruction is material. Build the Runtime Evidence Adapter Framework and Visual Runtime QA when runtime/UI cases show recurring source-only verification failures. If both are promoted, implement one concrete consumer before extracting a generic framework.
5. **Integrate Long-Horizon Autonomous Mode** — combine the broker, trust boundary, scoped execution, memory, lineage, rollback, supervisor, and grounded feedback only after each component has independent failure and recovery evidence. Long-horizon mode is an integration milestone, not a new unbounded agent loop.

Repository Eval Forge is the continuing evaluation track rather than a prerequisite inside the autonomy stack. Grow it from the stable paired harness as private repository cases and consenting cross-repository trials become available. Use it to decide whether each evidence-gated accelerator should be promoted and to support v1.0 claims.

## Promotion and release rules

- Do not infer implementation from a skill, prompt, agent profile, capability claim, or documentation statement.
- Do not turn the Flight Recorder into general prompt, source, command-output, environment, or MCP-response retention.
- Do not build generic repository or runtime infrastructure before a concrete measured consumer exists.
- Do not expand high-risk or long-horizon autonomy before trust, isolation, checkpoint, and rollback boundaries have executable negative tests.
- Keep failures, unsupported telemetry, client differences, and baseline contamination visible in certification results.
- Preserve one implementation writer by default; parallel investigation is not a product goal.

Explicit non-goals remain a required cloud dashboard, public leaderboard, automatic trace upload, giant public skill marketplace, automatic installation of untrusted skills, default swarm execution, self-rewriting policy, a new MCP protocol, a new coding model, and replacement of native client capabilities.

Other unscheduled candidates remain repository-specific command and verification discovery, generated adapter synchronization, plugin packaging for supported marketplaces, signed artifacts and checksums, enterprise managed-policy examples, domain packs, and a browser-based catalog explorer. They do not move ahead of the ordered build-out unless certification or measurable maintenance cost promotes them.

## v1.0 direction

- Stable compatibility and migration contracts.
- Repository Eval Forge evolved from the live-certification protocol and exercised across multiple consenting repositories.
- Reproducible team evidence for outcome quality, safety events, human intervention, rework, resource cost, and long-horizon completion.
- Maintainer and security-response process.
- Release automation and verified installation paths.

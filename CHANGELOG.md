# Changelog

## Unreleased
## 0.5.2 — 2026-08-18

- Changed PowerKit `pk` workflow routing to be automatic for all engineering tasks. Users no longer need to explicitly prefix their tasks with `/pk` or `$pk`.


## 0.5.1 — 2026-08-18

- Instructed agents to automatically add update rules to `.github/copilot-instructions.md` during installation.

## 0.5.0 — 2026-08-18

- Added versioned live-certification case, trace, and result contracts plus a reviewed six-case pilot corpus with executable fixture repositories.
- Added `powerkit certify pilot` to validate the bundled plan and deterministically score supplied vanilla/PowerKit trace pairs without launching clients or spending provider tokens.
- Added fail-closed trace validation for schema versions, baseline contamination, unknown retained fields, fixture identity, evidence references, telemetry provenance, path containment, duplicate runs, unauthorized writes, and fabricated verification.

## 0.4.0 — 2026-08-17

- Added the deterministic Execution Broker with independent FAST/STANDARD/DEEP effort and NORMAL/ELEVATED/HIGH risk axes while preserving HIGH_RISK Proof Pack compatibility.
- Added versioned Codex, Claude Code, and GitHub Copilot capability contracts across app, CLI, cloud, IDE, coding-agent, and SDK surfaces, with explicit NATIVE, PARTIAL, EMULATED, and UNAVAILABLE states.
- Added current-session versus launcher negotiation, portable resource and safety policy, one-writer and independent-review invariants, cost/latency projections, project overrides, and honest PROCEED/CHECKPOINT/STOP decisions.
- Added `powerkit broker explain|capabilities|launch` with human, compact, and stable JSON output, bounded allowlisted-path version probes, stdin prompt transport, local non-persistence flags, Codex/Claude setting application attempts, content-light mode-0600 traces, and versioned schema integration.
- Integrity-bound Proof Packs to task-identified compatible broker traces by deterministic replay and SHA-256, made checkpoints return a distinct exit, and fail closed when hard constraints or requested settings cannot be enforced.
- Integrated broker resolution into `/pk`, effort/risk routing cases, project configuration, the Context Budget Auditor, distribution metadata, packaging, installation tests, and documentation without loading capability matrices into normal prompt context.
- Added representative broker dogfood cases and deterministic tests for policy, constraints, lifecycle negotiation, schema, CLI exits and formats, trace safety, client probes, context overhead, and cross-platform capability coverage.

## 0.3.0 — 2026-08-17

- Added PowerKit Proof Pack: adaptive Completion Briefs, versioned local proof manifests, and offline HTML Proof Reports derived from one canonical evidence model.
- Extended repository verification commands to emit execution metadata without persisting stdout, environment values, or prompt history.
- Added evidence freshness checks, source-file snapshots, independent-verifier separation for high-risk work, artifact sensitivity handling, and scriptless CSP-restricted report rendering.
- Added `powerkit proof create|list|show|delete`, depth-aware `/pk` completion policy, local lifecycle configuration, and schema/package integration.
- Added deterministic coverage for depth policy, adaptive task modules, failed/skipped/stale evidence, hostile HTML, redaction, symlink containment, report failure isolation, relocation, and generated-proof lifecycle.
- Added the offline `powerkit context audit` command with human and stable JSON reports for always-on instructions, discovery metadata, selected skills, references, agents, adapters, and modeled FAST/STANDARD/DEEP paths.
- Added deterministic UTF-8 token estimates, platform-aware Codex/Claude/Copilot loading models, explicit unsupported-observation reporting, ranked architectural recommendations, project budgets, checked-in baselines, and CI regression exits.
- Added concise context-budget health to `powerkit doctor` without dumping the full audit.
- Added source, installed, desired-state/team-clone, relocation, minimal-profile, all-profile, and user-scope inventory behavior with traversal, symlink, malformed-UTF-8, terminal-control, and no-execution safeguards.
- Split detailed `pk` mode recipes behind a conditional reference and shortened seven discovery descriptions while preserving activation boundaries, reducing the measured common FAST path by about 1.3k estimated tokens.
- Added context-routing evals, context-budget documentation, and deterministic coverage for counting, classification, recommendations, platforms, budgets, baselines, lifecycle, and safety.

## 0.2.0 — 2026-08-17

- Made `BOOTSTRAP.md` and `manifests/powerkit.json` the agent-native discovery and distribution contracts.
- Added the installable `powerkit` CLI with init, sync, update, status, doctor, config, version, and safe uninstall commands.
- Added committed project desired state, relocatable schema-v2 install manifests, content digests, idempotent sync, safe stale pruning, and team-clone reconstruction.
- Added the complete `/pk` command layer with automatic routing, eight explicit task modes, help, constraint preservation, and progressive disclosure.
- Added native platform invocation mappings: `$pk` for Codex, `/pk` for Claude Code, and a managed `/pk` Copilot prompt-file adapter on supported IDE surfaces.
- Added deterministic command-manifest validation and 17 routing eval scenarios covering fast, standard, deep, high-risk, explicit-mode, plan-only, no-write, PhotoHelm onboarding, and negative over-orchestration behavior.
- Made all 24 canonical skills the default installation so every explicit `pk` mode has its specialist workflows while retaining progressive disclosure at runtime.
- Reworked GitHub onboarding around giving the repository URL to a coding assistant while retaining the hardened legacy installer as a compatibility wrapper.

## 0.1.1 — 2026-08-16

- Rejected symlinked installer destinations and sources, validated managed ownership markers, preflighted staged hooks and manifests, and made backup identifiers collision-safe.
- Store portable, base-relative schema-v2 manifest paths, migrate safe schema-v1 manifests, retain preserved stale-artifact inventory across subsequent updates, and allow managed stale artifacts to be reselected.
- Added Copilot CLI user-scope custom-agent installation at `~/.copilot/agents`.
- Hardened the catastrophic-command guard against separated and long `rm` flags, selected nested executable and shell wrappers, normalized root/home targets, Windows system-drive removal, and malformed hook events.
- Updated the Claude hook example for current Bash and PowerShell tools with project-root exec-form paths.
- Restricted release archives to Git-tracked regular files and reject tracked symlinks.
- Made zero-command verification fail unless `--allow-empty` is explicit.
- Strengthened validation for canonical-source drift, adapter behavior and permissions, platform hook semantics, scaffold placeholders, routing scenarios, and package-version consistency.
- Expanded behavioral tests from 11 to 29 cases, including per-platform installs, dry-run non-mutation, symlink attacks, staged hooks, backup recovery, stale inventory, archive contents, validator rejection, and empty verification.
- Clarified current Codex, Claude Code, and GitHub Copilot compatibility boundaries and repaired reviewer-routing ambiguity.

## 0.1.0 — 2026-08-16

- Added 23 canonical Agent Skills across foundation, delivery, quality, and specialist profiles.
- Added Codex, Claude Code, and GitHub Copilot instruction and subagent adapters.
- Added project- and user-scope installer with dry run, backups, managed-skill and managed-agent markers, atomic conflict preflight, and manifests.
- Added static validation, repository doctor, verification runner, skill scaffolder, and packaging tool.
- Added optional catastrophic-command guard with self-tests.
- Added routing cases, cross-skill scenarios, CI, security guidance, and team rollout documentation.
- Added Codex prompts for bootstrapping and hardening the repository.
- Added a power-user operating playbook, primary-source index, and reusable task launchers.

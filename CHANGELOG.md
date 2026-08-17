# Changelog

## 0.3.0 — 2026-08-17

- Added PowerKit Proof Pack: adaptive Completion Briefs, versioned local proof manifests, and offline HTML Proof Reports derived from one canonical evidence model.
- Extended repository verification commands to emit execution metadata without persisting stdout, environment values, or prompt history.
- Added evidence freshness checks, source-file snapshots, independent-verifier separation for high-risk work, artifact sensitivity handling, and scriptless CSP-restricted report rendering.
- Added `powerkit proof create|list|show|delete`, depth-aware `/pk` completion policy, local lifecycle configuration, and schema/package integration.
- Added deterministic coverage for depth policy, adaptive task modules, failed/skipped/stale evidence, hostile HTML, redaction, symlink containment, report failure isolation, relocation, and generated-proof lifecycle.

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

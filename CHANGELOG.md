# Changelog

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

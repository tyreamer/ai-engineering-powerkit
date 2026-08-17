# Installation

## Project scope

Project scope commits selected skills and adapters into a target repository.

```bash
python3 tools/install.py \
  --target ../product-repo \
  --profiles foundation,delivery,quality \
  --platforms codex,claude,copilot \
  --include-agents \
  --dry-run
```

Remove `--dry-run` after review.

The installer:

- Copies selected canonical skills.
- Creates Claude skill copies when selected.
- Adds platform-specific subagents when requested.
- Appends a bounded PowerKit instruction block without replacing existing content.
- Writes a schema-v2 `.ai-powerkit/install-manifest.json` with base-relative paths so a project installation survives repository relocation. Safe schema-v1 manifests are migrated on the next install.
- Preflights managed-skill, instruction-marker, and custom-agent conflicts before mutating the target.
- Rejects symlinked destinations or destination parents, including backup and manifest paths.
- Backs up an existing managed artifact before changing it.
- Refuses to overwrite unmanaged skill directories or custom-agent files unless `--force` is explicit.
- Reads the prior manifest and records any no-longer-selected managed artifacts as `stale_files`; it preserves them for review rather than deleting them automatically.

## User scope

User scope makes skills available across repositories:

```bash
python3 tools/install.py \
  --scope user \
  --profiles foundation \
  --platforms codex,claude,copilot \
  --include-agents
```

Review personal instruction changes carefully.

Copilot CLI user-scope custom agents are installed under `~/.copilot/agents`; IDE user-profile locations are client-managed and are not installed by PowerKit. PowerKit currently uses the platforms' default user configuration directories; custom `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, or `COPILOT_HOME` layouts require a reviewed manual install.

## Profiles

- `foundation`: recommended default.
- `delivery`: planning and implementation.
- `quality`: verification and review.
- `specialist`: dependency and UI workflows.
- `all`: every profile.

## Updating

Run the installer again with the same profile selection. It replaces skill directories and custom-agent files that contain valid PowerKit ownership markers. Relative manifest paths allow this managed update after moving or cloning the repository. Unknown artifacts are preserved and installation stops before any target mutation unless `--force` is used. If the selected profiles, platforms, agents, or staged-hook setting shrink, the installer retains prior artifacts under `stale_files` across later updates and leaves them in place. Review the dry run, manifest, and backups before using `--force` or removing stale content.

## Hooks

Hooks are not enabled by the installer. Pass `--stage-hooks` to copy the reviewed guard and platform examples under `.ai-powerkit`, then follow `docs/HOOKS.md`. A normal install without this flag intentionally leaves the hook command target absent.

## Repository verification commands

Copy `templates/project-config.example.json` to `.ai-powerkit/project.json` and replace example commands with commands that are known to work in the target repository. The verification runner executes those values as shell commands, so treat the project config as executable repository code. It returns non-success when none of the requested levels contains a command; use `--allow-empty` only when “no proof configured” is an intentional outcome.

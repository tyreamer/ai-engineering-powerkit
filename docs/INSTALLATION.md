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
- Writes `.ai-powerkit/install-manifest.json`.
- Preflights managed-skill, instruction-marker, and custom-agent conflicts before mutating the target.
- Backs up an existing managed artifact before changing it.
- Refuses to overwrite unmanaged skill directories or custom-agent files unless `--force` is explicit.

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

## Profiles

- `foundation`: recommended default.
- `delivery`: planning and implementation.
- `quality`: verification and review.
- `specialist`: dependency and UI workflows.
- `all`: every profile.

## Updating

Run the installer again with the same profile selection. It replaces skill directories and custom-agent files that contain PowerKit ownership markers. Unknown artifacts are preserved and installation stops before any target mutation unless `--force` is used. Review the dry run and backups before using `--force`.

## Hooks

Hooks are not enabled by the installer. See `docs/HOOKS.md`.

## Repository verification commands

Copy `templates/project-config.example.json` to `.ai-powerkit/project.json` and replace example commands with commands that are known to work in the target repository. The verification runner executes those values as shell commands, so treat the project config as executable repository code.

# Agent-native installation and state

## Primary onboarding

Give the repository URL to the coding assistant operating in the consumer project:

```text
Install AI Engineering PowerKit into this project:
https://github.com/tyreamer/ai-engineering-powerkit

Follow BOOTSTRAP.md, preserve existing project configuration, verify the
installation, and tell me when PowerKit is ready.
```

[`BOOTSTRAP.md`](../BOOTSTRAP.md) is the concise machine contract. [`manifests/powerkit.json`](../manifests/powerkit.json) supplies the current version, release tag, supported platforms, commands, defaults, and consumer-state paths without requiring an agent to crawl the repository.

## Consumer state

PowerKit writes:

- `.ai-powerkit/project.json`: committed desired state and release pin. The `powerkit` object is tool-managed; verification and policy values remain project-specific.
- `.ai-powerkit/install-manifest.json`: observed installation state, selected capabilities, relative managed paths, ownership kinds, and content digests.

The project config is sufficient to reconstruct a team setup. The install manifest is sufficient to check idempotency, health, safe pruning, and safe uninstall.

## Deterministic flow

From an exact tagged release checkout:

```bash
python3 -m powerkit init \
  --target ../product-repo \
  --platforms codex,claude \
  --yes

python3 -m powerkit doctor --target ../product-repo --json
```

`init` defaults to all 24 canonical skills and includes specialized agents. Progressive disclosure still loads only the workflows relevant to a request. The installer does not stage or enable hooks. An agent should pass its known host platform explicitly when repository evidence is ambiguous.

For a committed team configuration:

```bash
python3 -m powerkit sync --target ../product-repo
```

Sync reads the version and selections from project state. It refuses to run a different distribution version, applies only deterministic managed assets, safely prunes stale assets from schema-v2 manifests, and validates the result.

The shared installer engine:

- Copies selected canonical skills and creates Claude skill copies when selected.
- Installs the managed Copilot `/pk` prompt adapter when the `foundation` profile and Copilot are selected at project scope.
- Adds platform-specific subagents when requested.
- Appends a bounded PowerKit instruction block without replacing existing content.
- Writes a schema-v2 `.ai-powerkit/install-manifest.json` with base-relative paths so a project installation survives relocation; safe schema-v1 manifests are migrated.
- Preflights managed-skill, instruction-marker, custom-agent, hook, and manifest conflicts before mutating the target.
- Rejects symlinked destinations, parents, nested skill content, backup paths, and manifest paths.
- Backs up managed artifacts before changing them and uses collision-resistant backup identifiers.
- Refuses to overwrite unmanaged skill directories or custom-agent files unless `--force` is explicit.
- Prunes stale assets only when schema-v2 ownership and digests prove they are still managed; ambiguous or changed artifacts stop mutation.

## Command layer

The default `all` selection includes the canonical `pk` skill and every specialist workflow referenced by its explicit modes. A deliberately narrower profile selection keeps the same command surface when it includes `foundation`, but `pk` can compose only the workflows that are installed and must disclose any material reduction.

After a project install:

- Codex: invoke `$pk`, followed by an optional mode and the request.
- Claude Code: invoke `/pk`.
- GitHub Copilot: invoke `/pk` in VS Code, Visual Studio, or a supported JetBrains prompt-file surface.

Copilot prompt files are project-scoped in this installer. A user-scope Copilot install receives the shared `pk` skill but does not modify a personal prompt-file directory; on a skill-capable surface, ask Copilot to use the `pk` skill or rely on automatic routing.

The Copilot prompt is PowerKit-managed. A no-op reinstall leaves it byte- and mtime-stable; a changed managed prompt is backed up before replacement. An unmanaged `.github/prompts/pk.prompt.md` stops the whole installation during preflight unless `--force` is explicitly supplied.

## Updates

Normal sync follows the project pin, not `main`. For an explicit update, resolve the chosen stable release first, then run that release's tooling:

```bash
python3 -m powerkit update \
  --target ../product-repo \
  --version 0.3.0 \
  --yes
```

The command refuses a requested version that differs from the running distribution. This prevents an old binary from pretending it installed a newer release.

## Uninstall

Preview removal:

```bash
python3 -m powerkit uninstall --target ../product-repo --dry-run
```

Then remove only proven managed assets:

```bash
python3 -m powerkit uninstall --target ../product-repo --yes
```

Project configuration is preserved for team reconstruction unless `--purge-config` is explicit. Changed or ambiguously owned assets stop the entire uninstall before mutation.

## Packaged CLI

For a published release tag:

```bash
pipx install git+https://github.com/tyreamer/ai-engineering-powerkit.git@v0.3.0
```

This exposes `powerkit`. The wheel contains canonical distribution assets packaged directly from `.agents/skills`, adapters, hooks, and templates; those assets are not duplicated in the source repository.

## Legacy interface

Existing automation remains supported:

```bash
python3 tools/install.py \
  --target ../product-repo \
  --profiles all \
  --platforms codex,claude,copilot \
  --include-agents \
  --dry-run
```

The script is a compatibility wrapper around the same hardened installer engine used by the CLI. Re-running it replaces only artifacts with valid PowerKit ownership evidence, uses relocatable manifest paths, and stops before mutation on unknown conflicts unless `--force` is explicit.

## User scope and hooks

The legacy installer still supports reviewed user-scope installs. Agent bootstrap never infers permission to change user scope from a consumer repository. Hooks remain opt-in and are only staged when explicitly requested; no install path enables them automatically.

Copilot CLI user-scope custom agents are installed under `~/.copilot/agents`; IDE user-profile locations are client-managed and are not installed by PowerKit. PowerKit currently uses the platforms' default user configuration directories; custom `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, or `COPILOT_HOME` layouts require a reviewed manual install.

Managed command adapters follow the same update rules as managed custom agents: conflicts are detected before mutation, existing managed files are backed up, and a second install is idempotent.

## Hooks

Pass `--stage-hooks` only to copy the reviewed guard and platform examples under `.ai-powerkit`, then follow `docs/HOOKS.md`. A normal install intentionally leaves hook command targets absent.

## Repository verification commands

Project verification configuration is executable repository code. Replace example commands with commands known to work in the target repository and review them before execution. Proof creation suppresses command output by default; `--stream-output` opts into terminal disclosure. Symlinked configuration is rejected. The verification runner fails when no requested level contains a command unless `--allow-empty` explicitly makes missing proof intentional.

Proof Pack output defaults to `.ai-powerkit/proofs/` and is local generated state. Configure a different dedicated path under `.ai-powerkit/` with `proof.output_directory` in project configuration. Source and other tracked directories are rejected. Installation and uninstall do not delete generated proofs.

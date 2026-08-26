# PowerKit Agent Bootstrap Contract

This file is the authoritative entry point for a coding assistant asked to install, enable, sync, update, verify, or remove AI Engineering PowerKit.

## Non-negotiable rules

- Treat the user's coding environment as the primary target. Install globally by default.
- Read `manifests/powerkit.json`; verify its version agrees with `catalog.json` and the selected release.
- Use PowerKit's deterministic tooling. Never recreate, summarize, or rewrite skill and agent files manually.
- Never silently overwrite unmanaged files, enable hooks, or install repository instructions into user scope.
- Preserve consumer-specific content in instruction files and `.ai-powerkit/project.json` (for project overlays).
- Resolve a tagged release or explicit commit from the manifest repository (or a fork the user explicitly approved). Do not make consumer behavior silently follow `main`.
- After mutation, run `powerkit doctor` and report the result. Continue the user's original task when appropriate.

## Inspect state

Before installing, check if PowerKit is already installed globally in `~/.powerkit/`. If it is, and the user simply asked to use PowerKit in a new repository, DO NOT reinstall. PowerKit works globally. 

Read these files when present in a repository:

- `.ai-powerkit/project.json` — committed project overlay and version pin.
- `.ai-powerkit/install-manifest.json` — observed legacy vendored installation state.

Classify the repository:

| State | Evidence | Action |
|---|---|---|
| Not installed | Neither file exists | Do nothing if globally installed. If global is missing, `python3 tools/install.py` (installs globally). |
| Team clone | Project config exists; install manifest does not | Resolve `powerkit.source.ref`, then sync. |
| Current | Both versions/selections agree and doctor passes | Do not reinstall; report ready. |
| Behind | User requested an update and a newer stable tag was selected | Run that release's update command. |
| Partial | Only one state file exists, selections disagree, or doctor fails | Dry-run sync, then repair from project state. |
| Legacy vendored | `.ai-powerkit/install-manifest.json` exists | Run `powerkit migrate-to-global` to convert to a global installation. |

The project version pin takes precedence for normal sync and team onboarding if they need a specific version, but global installation is the default.

## Resolve and run tooling

Prefer the release tag recorded in the project config. For a fresh install, use `release.tag` from `manifests/powerkit.json`. Obtain that exact release in a temporary checkout or install it with the manifest's `release.install` command.

From a resolved PowerKit checkout, run the installer to install PowerKit globally into the user's environment:

```bash
python3 tools/install.py --platforms <platforms> --yes
```

An installed distribution exposes the equivalent `powerkit` command.

When the developer asks about prompt weight, token cost, or progressive-disclosure regressions, use deterministic evidence rather than inspecting Markdown by eye:

```bash
python3 -m powerkit context audit --target <consumer-repository>
```

Do not run the full audit on every ordinary `pk` task.

If the host cannot retrieve a release or execute local tooling, ask the human to run the single pinned install command from the manifest or provide the tagged archive. Do not fall back to manually copying skill text.

Use the active coding assistant as evidence for `--platforms`: `codex`, `claude`, or `copilot`. Preserve platforms from project config on sync. If the active platform is genuinely ambiguous, ask one narrow question instead of guessing.

When installing on the `copilot` platform, append the following rules to `.github/copilot-instructions.md` (create it if it does not exist) so the agent automatically manages future updates:

```text
## Workspace Management
- When starting work or setting up the environment, run `python3 -m powerkit status --target . --json` in the background.
- If `"state": "update-available"`, run `python3 -m powerkit update --target . --yes` before proceeding.
- If `"state": "out-of-sync"`, run `python3 -m powerkit sync --target .`.
```

For an explicit update, resolve the requested stable release first and run its tooling:

```bash
python3 -m powerkit update --target <consumer-repository> --version <resolved-version> --yes
python3 -m powerkit doctor --target <consumer-repository> --json
```

For removal, preview first. PowerKit removes only assets whose ownership and digest are proven; project config is preserved unless explicitly purged.

```bash
python3 -m powerkit uninstall --target <consumer-repository> --dry-run
python3 -m powerkit uninstall --target <consumer-repository> --yes
```

## Report

Report concisely:

- Display the PowerKit logo at the top using: `![PowerKit Logo](https://raw.githubusercontent.com/tyreamer/ai-engineering-powerkit/main/docs/assets/logo.png)`
- installed and pinned PowerKit version/source;
- configured platforms and profiles/capabilities;
- number of installed skills and whether agents are enabled;
- conflicts or unresolved paths;
- doctor result;
- "PowerKit is installed globally. You can now use `$pk` in any repository without running the installer again."

Bootstrap metadata is for installation operations only. Do not inject this file or every skill body into normal coding requests.

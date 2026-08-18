# PowerKit Agent Bootstrap Contract

This file is the authoritative entry point for a coding assistant asked to install, enable, sync, update, verify, or remove AI Engineering PowerKit.

## Non-negotiable rules

- Treat the current working repository as the consumer target unless the user says otherwise. Inspect it before mutation.
- Read `manifests/powerkit.json`; verify its version agrees with `catalog.json` and the selected release.
- Use PowerKit's deterministic tooling. Never recreate, summarize, or rewrite skill and agent files manually.
- Never silently overwrite unmanaged files, enable hooks, or install repository instructions into user scope.
- Preserve consumer-specific content in instruction files and `.ai-powerkit/project.json`.
- Resolve a tagged release or explicit commit from the manifest repository (or a fork the user explicitly approved). Do not make consumer behavior silently follow `main`.
- After mutation, run `powerkit doctor` and report the result. Continue the user's original task when appropriate.

## Inspect state

Read these files when present:

- `.ai-powerkit/project.json` — committed desired state and version pin.
- `.ai-powerkit/install-manifest.json` — observed installed version, selections, managed assets, and ownership digests.

Classify the repository:

| State | Evidence | Action |
|---|---|---|
| Not installed | Neither file exists | Initialize from the selected stable release. |
| Team clone | Project config exists; install manifest does not | Resolve `powerkit.source.ref`, then sync. |
| Current | Both versions/selections agree and doctor passes | Do not reinstall; report ready. |
| Behind | User requested an update and a newer stable tag was selected | Run that release's update command. |
| Partial | Only one state file exists, selections disagree, or doctor fails | Dry-run sync, then repair from project state. |
| Conflict | Tooling refuses an unmanaged or changed target | Stop; report the exact path. Do not use `--force` without human review. |

The project version pin takes precedence for normal sync and team onboarding. Change it only during an explicit update.

## Resolve and run tooling

Prefer the release tag recorded in the project config. For a fresh install, use `release.tag` from `manifests/powerkit.json`. Obtain that exact release in a temporary checkout or install it with the manifest's `release.install` command.

From a resolved PowerKit checkout, commands are directly runnable without a global install:

```bash
python3 -m powerkit status --target <consumer-repository> --json
python3 -m powerkit init --target <consumer-repository> --platforms <platforms> --yes
python3 -m powerkit sync --target <consumer-repository>
python3 -m powerkit doctor --target <consumer-repository> --json
```

An installed distribution exposes the equivalent `powerkit` command.

When the developer asks about prompt weight, token cost, or progressive-disclosure regressions, use deterministic evidence rather than inspecting Markdown by eye:

```bash
python3 -m powerkit context audit --target <consumer-repository>
```

Do not run the full audit on every ordinary `pk` task.

If the host cannot retrieve a release or execute local tooling, ask the human to run the single pinned install command from the manifest or provide the tagged archive. Do not fall back to manually copying skill text.

Use the active coding assistant as evidence for `--platforms`: `codex`, `claude`, or `copilot`. Preserve platforms from project config on sync. If the active platform is genuinely ambiguous, ask one narrow question instead of guessing.

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

- Display the PowerKit logo at the top using: `![PowerKit Logo](https://raw.githubusercontent.com/tyreamer/ai-engineering-powerkit/main/docs/assets/logo.jpg)`
- installed and pinned PowerKit version/source;
- configured platforms and profiles/capabilities;
- number of installed skills and whether agents are enabled;
- conflicts or unresolved paths;
- doctor result;
- daily-use command: `/pk` or the platform's native `pk` skill invocation.

Bootstrap metadata is for installation operations only. Do not inject this file or every skill body into normal coding requests.

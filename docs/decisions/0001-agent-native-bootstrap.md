# 0001: Agent-native bootstrap and versioned consumer state

- Status: Accepted
- Date: 2026-08-16

## Context

PowerKit's original public path required a human to clone the repository and invoke `tools/install.py` with knowledge of profiles, platforms, and assistant-specific directories. The installer already had valuable conflict preflight, ownership markers, bounded instruction merges, backups, dry-run, and manifest behavior. Replacing it would create competing safety semantics.

## Decision

- Make root `BOOTSTRAP.md` the concise coding-agent entry contract and `manifests/powerkit.json` the distribution discovery contract.
- Persist committed desired state in `.ai-powerkit/project.json` and observed installed state in `.ai-powerkit/install-manifest.json`.
- Retain the existing `install-manifest.json` filename for compatibility, but evolve its schema to relative paths, asset kinds, source/version metadata, and content digests.
- Use explicit release tags or commits. Normal sync obeys the project pin; an update must run from the deliberately selected new distribution.
- Keep one installer engine in `powerkit.installer`. The console command, `python -m powerkit`, and legacy scripts are interfaces over that engine.
- Permit removal or stale pruning only when the schema-v2 manifest, ownership marker where applicable, path containment, symlink policy, and recorded digest all agree.
- Keep hooks opt-in and bootstrap project-scoped. A consumer repository does not authorize personal-scope mutation.

## Consequences

- Coding assistants can bootstrap, reconstruct, verify, update, and remove PowerKit without manually generating assets.
- Existing direct installer automation remains callable.
- A project config can be committed for team onboarding without storing absolute workstation paths.
- Changed managed assets intentionally block automated uninstall until reviewed or restored.
- Remote no-clone onboarding depends on publishing the tag named in the distribution manifest; CI builds wheel, ZIP, and checksum release artifacts for tag pushes.
- Bootstrap metadata remains separate from normal runtime context, and the explicit `pk` skill routes daily work through progressive disclosure.

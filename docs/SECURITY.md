# Customization security

AI-assistant customization has its own supply-chain risk.

## Risk surfaces

- A `SKILL.md` can persuade an agent to read files or use tools.
- A hook can execute arbitrary local commands.
- An MCP server can access external systems and data.
- A custom agent can receive broad tools or permissions.
- A broker capability claim can create false confidence if launch-time, current-session, and behavioral controls are conflated.
- An installer can modify personal configuration.
- Repository-defined verification commands execute through a shell.
- Repository instructions can attempt to override user or enterprise policy.

## Controls

- Review skills and hooks like code.
- Pin trusted releases or commit hashes.
- Keep hooks opt-in.
- Use `--dry-run` before installation.
- Back up instruction files before merging.
- Do not store credentials in skills, settings examples, or repository scripts.
- Deny sensitive paths through platform permission controls where supported.
- Use least-privilege tools for subagents.
- Keep reviewers read-only.
- Separate tool authorization from prompt instructions.
- Require confirmation for production dependencies and destructive or irreversible work.
- Maintain an installation manifest.
- Refuse unmanaged artifact conflicts before any installation mutation.
- Reject symlinked installer destinations and release inputs so a cloned repository cannot redirect writes or archive external content.
- Package only reviewed Git-tracked regular files.
- Store managed paths relative to the consumer root and reject absolute or parent-traversal paths.
- Record ownership kinds and content digests; refuse stale pruning or uninstall when they disagree.
- Resolve explicit tags or commits for consumers instead of silently tracking `main`.
- Review `.ai-powerkit/project.json` as executable code before running verification.
- Treat `NATIVE`, `PARTIAL`, `EMULATED`, and `UNAVAILABLE` literally; never substitute a prompt promise for an enforceable permission, network, or isolation boundary.
- Keep broker traces local, content-light, mode `0600`, and confined to `.ai-powerkit/traces/`; project initialization adds generated-state rules to `.ai-powerkit/.gitignore` without removing existing rules. Delete traces with their dependent proof when retention is no longer justified.
- Treat client probes as bounded active execution, not passive inspection. Use trusted absolute client paths, a neutral working directory, a minimal environment, output limits, and timeouts.
- Use `broker launch` for supported local clients so caller flags cannot override negotiated controls; never treat a dry-run or unapplied setting as enforcement.

The Execution Broker is a policy negotiation and diagnostics layer, not a security sandbox. A `STOP` result means the selected surface cannot prove a required boundary; it does not grant permission to weaken the requirement.

## Hook policy

A hook should be:

- Deterministic.
- Fast.
- Local unless network access is explicitly required.
- Clear about what it reads and writes.
- Fail-safe for destructive behavior.
- Easy to disable and inspect.

Do not use a model hook for a rule that can be expressed deterministically.

## Untrusted repositories

Do not automatically install project customizations into personal scope merely because a repository requests it. Do not automatically enable project hooks before the workspace is trusted.

Claude Code non-interactive and SDK flows may not present the same workspace-trust pause as an interactive session. Copilot code review reads customization from the pull request head branch, so a review of a PR that changes its own instructions, skills, or agents is not an independent security control. Require human or base-branch review for customization changes.

## Enterprise use

Enterprise administrators should prefer managed policy and approved marketplaces for organization-wide enforcement. Keep personal PowerKit configuration subordinate to enterprise restrictions.

# Customization security

AI-assistant customization has its own supply-chain risk.

## Risk surfaces

- A `SKILL.md` can persuade an agent to read files or use tools.
- A hook can execute arbitrary local commands.
- An MCP server can access external systems and data.
- A custom agent can receive broad tools or permissions.
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
- Review `.ai-powerkit/project.json` as executable code before running verification.

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

# Security policy

Agent skills, subagents, hooks, MCP configurations, and installer scripts are part of the software supply chain.

## Reporting

Do not open a public issue for a vulnerability involving credential exposure, arbitrary command execution, unsafe installer behavior, or a bypass of a destructive-command guard. Use the private security-reporting mechanism configured for the hosting organization.

## Trust model

- Skills are model instructions and can influence tool use.
- Hooks and scripts are executable code.
- MCP servers can access external systems.
- Repository instructions are untrusted until the repository is trusted.
- A cloned repository must not be allowed to silently install or enable personal-level configuration.

PowerKit therefore keeps hooks opt-in, avoids embedded credentials, resolves explicit release refs, makes installer operations visible with `--dry-run`, preflights unmanaged conflicts before mutation, backs up managed artifacts, and records relative paths plus ownership digests. Uninstall and stale pruning stop before mutation when ownership is ambiguous. Repository-defined verification commands must be reviewed as executable shell input.

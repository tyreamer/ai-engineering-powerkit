# Platform adapters

Canonical skill behavior lives under `.agents/skills`.

This directory contains platform-specific subagents and configuration examples. The installer copies these files into the target platform's default project or user location. Hook examples are copied only with `--stage-hooks` and are never enabled automatically.

- `codex/agents/*.toml`
- `claude/agents/*.md`
- `copilot/agents/*.agent.md`
- `copilot/prompts/pk.prompt.md` — thin managed `/pk` adapter for prompt-file-capable Copilot IDEs
- `<platform>/capabilities.json` — versioned Execution Broker contract with per-surface controls, lifecycle support, sources, and native translations

Codex and Claude Code consume the canonical `pk` skill directly (`$pk` and `/pk`, respectively), so they do not need duplicate command prompt files.

Model names are intentionally omitted from shared agent behavior and canonical broker policy. Where a client has a stable documented catalog, names may appear only in its capability adapter; account-specific catalogs use project `execution_policy.adapter_overrides`.

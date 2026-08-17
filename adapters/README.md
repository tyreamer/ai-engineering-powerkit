# Platform adapters

Canonical skill behavior lives under `.agents/skills`.

This directory contains platform-specific subagents and configuration examples. The installer copies these files into the target platform's project or user location.

- `codex/agents/*.toml`
- `claude/agents/*.md`
- `copilot/agents/*.agent.md`

Model names are intentionally omitted so teams can choose current models and reasoning settings without editing the shared behavioral contract.

# Primary documentation sources

Platform customization changes quickly. The links below were checked on **2026-08-16** and are the primary references for PowerKit's portable layout and adapters.

## Agent Skills

- Agent Skills specification: https://agentskills.io/specification
- Codex skills: https://learn.chatgpt.com/docs/build-skills
- Claude Code skills: https://code.claude.com/docs/en/skills
- GitHub Copilot agent skills: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- GitHub Copilot code review: https://docs.github.com/en/copilot/concepts/agents/code-review

## Instructions and agents

- Codex `AGENTS.md`: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Claude Code subagents: https://code.claude.com/docs/en/sub-agents
- GitHub Copilot repository instructions: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions
- GitHub Copilot custom agents: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents
- GitHub Copilot CLI custom agents: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
- GitHub Copilot customization support matrix: https://docs.github.com/en/copilot/reference/customization-cheat-sheet
- GitHub Copilot custom-instruction support: https://docs.github.com/en/copilot/reference/custom-instructions-support

## Hooks and distribution

- Codex hooks: https://learn.chatgpt.com/docs/hooks
- Claude Code hooks: https://code.claude.com/docs/en/hooks-guide
- Codex and ChatGPT plugins: https://learn.chatgpt.com/docs/plugins

## Release rule

Before changing adapter formats or claiming compatibility with a new client surface:

1. Re-read the relevant primary documentation.
2. Update `docs/PORTABILITY.md`.
3. Add or update adapter tests.
4. Record any live-client verification that was actually performed.
5. Keep unsupported or unverified behavior explicit in the release notes.

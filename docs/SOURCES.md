# Primary documentation sources

Platform customization changes quickly. The links below were checked through **2026-08-17** and are the primary references for PowerKit's portable layout and adapters. Per-control source IDs are recorded in each `adapters/*/capabilities.json` contract.

## Agent Skills

- Agent Skills specification: https://agentskills.io/specification
- Codex skills: https://learn.chatgpt.com/docs/build-skills
- Codex developer commands: https://learn.chatgpt.com/docs/developer-commands
- Codex custom prompts deprecation and legacy syntax: https://learn.chatgpt.com/docs/custom-prompts
- Claude Code skills: https://code.claude.com/docs/en/skills
- GitHub Copilot agent skills: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- GitHub Copilot code review: https://docs.github.com/en/copilot/concepts/agents/code-review
- Claude Code commands: https://code.claude.com/docs/en/commands
- GitHub Copilot agent skills: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills

## Instructions and agents

- Codex `AGENTS.md`: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Claude Code subagents: https://code.claude.com/docs/en/sub-agents
- GitHub Copilot repository instructions: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions
- GitHub Copilot custom agents: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents
- GitHub Copilot CLI custom agents: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
- GitHub Copilot customization support matrix: https://docs.github.com/en/copilot/reference/customization-cheat-sheet
- GitHub Copilot custom-instruction support: https://docs.github.com/en/copilot/reference/custom-instructions-support
- GitHub Copilot prompt files: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions-in-your-ide/add-repository-instructions-in-your-ide

## Hooks and distribution

- Codex hooks: https://learn.chatgpt.com/docs/hooks
- Claude Code hooks: https://code.claude.com/docs/en/hooks-guide
- Codex and ChatGPT plugins: https://learn.chatgpt.com/docs/plugins

## Execution controls

- Codex configuration: https://learn.chatgpt.com/docs/config-file/config-reference
- Codex permissions and sandboxing: https://learn.chatgpt.com/docs/permissions
- Codex approvals and security: https://learn.chatgpt.com/docs/agent-approvals-security
- Codex browser: https://learn.chatgpt.com/docs/browser
- Codex App Server: https://learn.chatgpt.com/docs/app-server
- Claude Code CLI: https://code.claude.com/docs/en/cli-reference
- Claude Code models: https://code.claude.com/docs/en/model-config
- Claude Code permissions and sandboxing: https://code.claude.com/docs/en/permissions
- GitHub Copilot CLI: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
- GitHub Copilot sandboxes: https://docs.github.com/en/copilot/concepts/about-cloud-and-local-sandboxes
- GitHub Copilot coding-agent firewall: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/customize-the-agent-firewall
- GitHub Copilot SDK hooks and telemetry: https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/hooks and https://docs.github.com/en/copilot/how-tos/copilot-sdk/observability/opentelemetry

## Release rule

Before changing adapter formats or claiming compatibility with a new client surface:

1. Re-read the relevant primary documentation.
2. Update `docs/PORTABILITY.md`.
3. Add or update adapter tests.
4. Record any live-client verification that was actually performed.
5. Keep unsupported or unverified behavior explicit in the release notes.

# Team rollout

Do not drop every customization onto an entire development organization at once.

## Stage 1: baseline

Choose three to five representative developers and two active repositories.

Record a baseline for:

- Clarification turns before useful work begins.
- Time to first correct implementation.
- Percentage of tasks completed without rework.
- Defects found after the assistant claimed completion.
- Human time spent rediscovering repository context.
- Token or request consumption where available.
- Developer trust and override frequency.

## Stage 2: foundation profile

Install:

- prompt-preflight
- engineering-task-orchestrator
- repository-cartographer
- task-contract
- context-recovery
- workload-router
- decision-handoff

Use them for two weeks. Review unnecessary questions, false triggers, and tasks where the workflow was too heavy.

## Stage 3: delivery profile

Add planning, vertical slicing, debugging, migration, and parallel investigation.

Establish the single-writer rule and require evidence packets from subagents.

## Stage 4: quality profile

Add verification, testing, security, compatibility, implementation review, and anti-slop checks.

Before enabling stop hooks or required verification commands, make sure repository commands are fast, deterministic, and documented.

## Stage 5: specialist profile and internal skills

Add team-specific skills only after the common workflow is stable.

Good internal skills encode:

- A repeated domain workflow.
- A real system contract.
- An approved architecture pattern.
- A deterministic deployment or test procedure.
- A known review standard.

Do not put confidential credentials, unrestricted production actions, or undocumented authorization logic in a skill.

## Governance

Assign maintainers for:

- Skill design and routing.
- Platform adapters.
- Security review of scripts and hooks.
- Evaluation scenarios.
- Release notes and deprecation.
- Team feedback.

Require pull requests for changes to shared skills. Version the toolkit and let repositories pin a reviewed release.

## Success criteria

The rollout succeeds when developers spend more time making product decisions and less time rewriting prompts, while first-pass correctness and evidence quality improve. “People installed it” is not a success metric.

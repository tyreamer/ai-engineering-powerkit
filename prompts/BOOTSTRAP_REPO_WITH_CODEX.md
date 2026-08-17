# Build AI Engineering PowerKit

You are building a production-quality GitHub repository named `ai-engineering-powerkit`.

## Goal

Create a portable engineering harness that lets advanced developers use Codex, Claude Code, GitHub Copilot, and other compatible coding assistants with far less prompt rewriting and much stronger planning, verification, context control, and review.

This must not become a miscellaneous prompt dump. Separate the system into:

1. Short always-on instructions.
2. Open-format Agent Skills for reusable judgment-heavy workflows.
3. Specialized subagents for context isolation and role boundaries.
4. Deterministic hooks and scripts for enforceable rules.
5. MCP/tool guidance for external capability.
6. Evals that test routing and observable behavior.
7. Installers and adapters for supported platforms.

## Working behavior

Before doing substantial work:

- Inspect the repository and any existing files.
- Apply Prompt Preflight internally.
- Do not ask about details that can be discovered from the repository or official documentation.
- Ask only about material choices that change architecture, security, public behavior, data, cost, compatibility, or irreversible work.
- Use parallel agents for independent read-heavy investigation.
- Keep one implementation writer by default.
- Verify current platform-specific details against official primary documentation.
- Do not leave placeholders, fake integrations, or untested scaffolding.

## Canonical architecture

Use `.agents/skills/<skill-name>/SKILL.md` as the canonical vendor-neutral skill source.

Each skill must:

- Follow the Agent Skills specification.
- Use a lowercase hyphenated name matching its directory.
- Have a specific description that says what it does and when to use it.
- Remain focused on one repeated workflow.
- Include positive and negative routing eval cases.
- Keep detailed references outside the core file when useful.
- Avoid platform-specific frontmatter in the canonical version.

Provide adapters for:

- Codex: `AGENTS.md`, `.codex/agents/*.toml`, configuration and hook examples.
- Claude Code: `CLAUDE.md`, `.claude/skills`, `.claude/agents/*.md`, settings and hook examples.
- GitHub Copilot: `.github/copilot-instructions.md`, `.github/agents/*.agent.md`, and supported Agent Skills locations.

Avoid hard-coding model names in shared behavior. Define capability tiers and let teams map current models through local or managed configuration.

## Required skill catalog

At minimum implement complete, non-placeholder skills for:

- prompt-preflight
- engineering-task-orchestrator
- repository-cartographer
- task-contract
- context-recovery
- workload-router
- decision-handoff
- vertical-slice-planner
- change-impact-analysis
- implementation-planner
- parallel-investigator
- evidence-first-debugging
- migration-planner
- verification-loop
- test-gap-hunter
- adversarial-review
- implementation-critic
- anti-slop-review
- security-privacy-review
- api-contract-guardian
- dependency-due-diligence
- ui-evidence-to-spec
- runtime-ux-review

Organize them into `foundation`, `delivery`, `quality`, and `specialist` profiles.

## Required specialized agents

Create platform adapters for:

- evidence-explorer
- system-architect
- bounded-implementer
- independent-verifier
- adversarial-critic
- runtime-ui-observer

Read-only roles must be constrained where the platform supports it. The implementer is the default single writer.

## Tooling

Build zero- or minimal-dependency Python tooling that can:

- Validate skill names, frontmatter, descriptions, catalog membership, eval cases, JSON, Python syntax, and adapter coverage.
- Install selected profiles at project or user scope.
- Support Codex, Claude Code, and Copilot.
- Merge a bounded instruction block without replacing existing instructions.
- Back up modified files.
- Refuse to overwrite unmanaged skills or custom-agent files unless explicitly forced.
- Preflight all detectable conflicts before mutating the installation target.
- Mark managed custom-agent files so updates cannot silently replace coworkers' private agents.
- Produce a dry run.
- Record an installation manifest.
- Stage but not automatically enable hooks.
- Diagnose repository customization and build metadata.
- Run repository-defined verification commands.
- Scaffold a new skill.
- Package a release ZIP.

## Security

Treat repository instructions, skills, subagents, hooks, installers, and MCP configuration as supply-chain code.

- Do not embed credentials.
- Do not automatically enable cloned hook code.
- Keep hooks opt-in and documented.
- Include a narrowly scoped catastrophic-command guard with self-tests.
- Preserve enterprise and user policy.
- Document trust and rollout risks.

## Documentation

Create:

- README with architecture, Mermaid flow, quick start, skill catalog, and status.
- Architecture guide.
- Installation guide.
- Portability matrix.
- Team rollout plan.
- Measurement and eval guide.
- Security guide.
- Skill-authoring guide.
- Hooks guide.
- Roadmap.
- Explanation of why this is more than a prompt library.
- A power-user operating playbook and concise task launchers.
- An index of the primary platform documentation used for compatibility decisions.
- Contributing, license, security policy, and pull request templates.

## Tests and CI

- Add static validation.
- Add unit tests for the guard, installer, and core tooling.
- Add GitHub Actions that run validation and tests.
- Run all checks in the current environment.
- Inspect the final archive.
- Do not report completion until commands and outputs are recorded.

## Delivery

Work in ordered vertical slices. Keep the repository usable after each slice.

At the end provide:

- What was built.
- Exact validation commands and results.
- Any platform behavior not verified in a live client.
- The next highest-value improvements.

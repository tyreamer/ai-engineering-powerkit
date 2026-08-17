# Portability

PowerKit keeps the core vendor-neutral but does not pretend every platform has identical customization features.

## Canonical skill format

Each skill is a directory containing a required `SKILL.md` with:

- `name`
- `description`
- Markdown instructions

Optional folders include `references`, `scripts`, `assets`, and `evals`.

PowerKit uses names that match their parent directory and avoids platform-only frontmatter in canonical files.

## Directory strategy

| Platform | Project skill location used by PowerKit | Notes |
|---|---|---|
| Codex | `.agents/skills` | Canonical copy |
| GitHub Copilot | `.agents/skills` | Supported Copilot surfaces can discover this location |
| Claude Code | `.claude/skills` | Installer copies canonical skills here |
| Other compatible agents | `.agents/skills` or platform adapter | Verify current platform documentation |

## Platform-specific features

### Codex

- Project instructions: `AGENTS.md`
- Project subagents: `.codex/agents/*.toml`
- Project configuration: `.codex/config.toml`
- Hooks: `.codex/hooks.json` or inline configuration
- Skills: `.agents/skills`

PowerKit uses the default `~/.codex` user configuration root and does not currently resolve a custom `CODEX_HOME`. `AGENTS.override.md` also takes precedence over an installed `AGENTS.md`; check for a shadowing override when instructions appear inactive.

### Claude Code

- Project instructions: `CLAUDE.md`
- Project skills: `.claude/skills`
- Project subagents: `.claude/agents/*.md`
- Project settings and hooks: `.claude/settings.json`

Personal Claude skills with the same name can override project skills. A repository-pinned install is therefore not proof that an older user-scope copy is inactive. Enterprise `strictPluginOnlyCustomization` can disable loose project/user skills, agents, and hooks entirely.

### GitHub Copilot

- Repository instructions: `.github/copilot-instructions.md`
- Path instructions: `.github/instructions/**/*.instructions.md`
- Agent instructions: `AGENTS.md`
- Custom agents: `.github/agents/*.agent.md`
- Agent skills: `.agents/skills`, `.github/skills`, or `.claude/skills` on supported surfaces

PowerKit installs project skills to `.agents/skills` and Copilot CLI user custom agents to `~/.copilot/agents`; it does not install IDE user-profile agents. Current Copilot cloud-agent, code-review, CLI, app, and supported IDE documentation accepts `.agents/skills`, and code review is generally available. This layout is documentation-compatible with code-review skill loading, but PowerKit did not live-test that surface. Custom-agent and instruction support varies by surface, and the `playwright/*` runtime-observer tool is guaranteed only in the Copilot cloud agent.

Feature support varies by IDE and surface. The loose-file adapters were checked against official documentation on 2026-08-16 but were not loaded in current live clients during v0.1.1 verification. Keep adapters conservative and verify them against the versions used by the team.

## Preventing drift

- Edit canonical skills only under `.agents/skills`.
- Reinstall or regenerate platform copies.
- Keep installer manifests base-relative; schema-v2 managed installs can be updated after a repository move or clone.
- Never maintain separate behavioral text manually in three directories.
- Put platform-only behavior in adapters.
- Run `python3 tools/validate.py` after changes.

## Description collisions

Automatic skill selection depends heavily on descriptions. Two skills with overlapping descriptions can trigger unpredictably.

When adding a skill:

1. State the exact repeated task.
2. State when to use it.
3. Add explicit boundaries.
4. Add negative routing cases.
5. Prefer improving an existing skill over creating a near-duplicate.

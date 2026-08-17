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

### Claude Code

- Project instructions: `CLAUDE.md`
- Project skills: `.claude/skills`
- Project subagents: `.claude/agents/*.md`
- Project settings and hooks: `.claude/settings.json`

### GitHub Copilot

- Repository instructions: `.github/copilot-instructions.md`
- Path instructions: `.github/instructions/*.instructions.md`
- Agent instructions: `AGENTS.md`
- Custom agents: `.github/agents/*.agent.md`
- Agent skills: `.agents/skills`, `.github/skills`, or `.claude/skills` on supported surfaces

Feature support varies by IDE and surface. Keep adapters conservative and verify them against the versions used by the team.

## Preventing drift

- Edit canonical skills only under `.agents/skills`.
- Reinstall or regenerate platform copies.
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

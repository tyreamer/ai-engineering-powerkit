# Portability

PowerKit keeps the core vendor-neutral but does not pretend every platform has identical customization features.

## PowerKit command surface

`pk` is one logical command with native platform presentation:

| Platform | Project adapter | Invocation | Limitation |
|---|---|---|---|
| Codex | `.agents/skills/pk` | `$pk` or select `pk` from `/skills` | Codex repository skills are explicitly mentioned with `$`; deprecated user-only custom prompts would not provide a portable literal `/pk`. |
| Claude Code | `.claude/skills/pk` | `/pk` | The installed skill directory becomes the slash command. |
| GitHub Copilot | `.agents/skills/pk` plus `.github/prompts/pk.prompt.md` | `/pk` on prompt-file-capable IDEs | Prompt files are not available on every Copilot surface; supported skill surfaces can still select `pk` automatically or when asked. |

The command behavior remains canonical under `.agents/skills/pk`. The Copilot prompt file is a short managed adapter that points to the canonical skill; it does not repeat the routing workflows.

Codex's legacy `~/.codex/prompts` mechanism is intentionally not used. It is deprecated, user-scoped, and exposes names such as `/prompts:pk` rather than the desired portable repository interface.

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
- PowerKit command: `$pk` or `/skills` → `pk`

PowerKit uses the default `~/.codex` user configuration root and does not currently resolve a custom `CODEX_HOME`. `AGENTS.override.md` also takes precedence over an installed `AGENTS.md`; check for a shadowing override when instructions appear inactive.

### Claude Code

- Project instructions: `CLAUDE.md`
- Project skills: `.claude/skills`
- Project subagents: `.claude/agents/*.md`
- Project settings and hooks: `.claude/settings.json`
- PowerKit command: `/pk`

Personal Claude skills with the same name can override project skills. A repository-pinned install is therefore not proof that an older user-scope copy is inactive. Enterprise `strictPluginOnlyCustomization` can disable loose project/user skills, agents, and hooks entirely.

### GitHub Copilot

- Repository instructions: `.github/copilot-instructions.md`
- Path instructions: `.github/instructions/**/*.instructions.md`
- Agent instructions: `AGENTS.md`
- Custom agents: `.github/agents/*.agent.md`
- Agent skills: `.agents/skills`, `.github/skills`, or `.claude/skills` on supported surfaces
- Prompt files: `.github/prompts/*.prompt.md` on supported IDE surfaces
- PowerKit command: `/pk` where prompt files are supported; otherwise ask Copilot to use the `pk` skill

PowerKit installs project skills to `.agents/skills` and Copilot CLI user custom agents to `~/.copilot/agents`; it does not install IDE user-profile agents. Current Copilot cloud-agent, code-review, CLI, app, and supported IDE documentation accepts `.agents/skills`, and code review is generally available. This layout is documentation-compatible with code-review skill loading, but PowerKit did not live-test that surface. Custom-agent and instruction support varies by surface, and the `playwright/*` runtime-observer tool is guaranteed only in the Copilot cloud agent.

Feature support varies by IDE and surface. The loose-file adapters were checked against official documentation on 2026-08-16 but were not loaded in current live clients during v0.1.1 verification. Keep adapters conservative and verify them against the versions used by the team.

## Command-layer invocation

PowerKit installs a canonical `pk` skill. Claude surfaces commonly expose skills as slash commands, Codex can use the native explicit skill form such as `$pk`, and Copilot behavior depends on the active surface. Documentation uses `/pk` as the portable mental model and tells the installing agent to report the exact native invocation available in its host.

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

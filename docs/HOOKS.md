# Hooks

Hooks are optional because they execute code automatically. Skills explain judgment; hooks enforce only narrow deterministic policy.

## Included guard

`hooks/catastrophic_command_guard.py` blocks only clearly catastrophic shell patterns, such as recursive deletion of a filesystem root or direct writes to block devices. It intentionally does not block ordinary cleanup, `git reset`, or force pushes because team policy differs.

The script exits with code `2` and writes the reason to standard error when it blocks a command. Both Codex and Claude Code treat that as a blocking hook result for their supported pre-tool hook paths.

## Review before enabling

1. Read the script.
2. Run its self-tests.
3. Review the platform example.
4. Trust the repository using the platform's normal trust mechanism.
5. Enable it in a disposable test repository.
6. Confirm legitimate commands still work.
7. Roll it out gradually.

## Codex example

Copy or merge `adapters/codex/hooks.example.json` into `.codex/hooks.json`.

Codex `hooks.json` uses a top-level `hooks` object. The example resolves the script from the Git root because Codex can start from a repository subdirectory. Keep only one representation per configuration layer: either `.codex/hooks.json` or inline `[hooks]` configuration in `.codex/config.toml`.

Hooks are enabled by default in current Codex releases. A team can explicitly disable them with:

```toml
[features]
hooks = false
```

## Claude Code example

Copy the relevant block from `adapters/claude/settings.hooks.example.json` into `.claude/settings.json`. The example also resolves the script from the Git root.

## Deterministic quality commands

Use `tools/run_verification.py --config .ai-powerkit/project.json` manually or from CI before wiring it to a lifecycle event. Stop hooks that run slow test suites on every turn can make assistants frustrating and expensive.

## Windows

The Python guard works on Windows when invoked with `py -3`. Review shell expansion, quoting, Git availability, and paths in the platform configuration before rollout. Test the exact client and shell combination your team uses.

# Hooks

Hooks are optional because they execute code automatically. Skills explain judgment; hooks enforce only narrow deterministic policy.

## Included guard

`hooks/catastrophic_command_guard.py` blocks only clearly catastrophic shell patterns, such as recursive deletion of a filesystem root or direct writes to block devices. It intentionally does not block ordinary cleanup, `git reset`, or force pushes because team policy differs.

The script exits with code `2` and writes the reason to standard error when it blocks a command or cannot parse a valid shell-command event. Both Codex and Claude Code treat that as a blocking hook result for their supported pre-tool hook paths.

## Review before enabling

1. Read the script.
2. Run its self-tests.
3. Stage the script and examples with `python3 tools/install.py ... --stage-hooks`.
4. Review the platform example and confirm its command points to the staged script.
5. Trust the repository using the platform's normal trust mechanism.
6. Enable it in a disposable test repository.
7. Confirm legitimate commands still work.
8. Roll it out gradually.

## Codex example

After staging, copy or merge `.ai-powerkit/platform-examples/codex/hooks.example.json` into `.codex/hooks.json`.

Codex `hooks.json` uses a top-level `hooks` object. The example resolves the script from the Git root because Codex can start from a repository subdirectory. Keep only one representation per configuration layer: either `.codex/hooks.json` or inline `[hooks]` configuration in `.codex/config.toml`.

Hooks are enabled by default in current Codex releases. A team can explicitly disable them with:

```toml
[features]
hooks = false
```

Codex separately reviews non-managed hook definitions by exact hash. Use `/hooks` to review a newly added or changed definition; trusting the repository alone does not prove that the hook ran.

## Claude Code example

After staging, copy the relevant block from `.ai-powerkit/platform-examples/claude/settings.hooks.example.json` into `.claude/settings.json`. The Bash handler runs the staged Python script through `python3`; the PowerShell handler runs the same script through `py -3`. Both use Claude's `${CLAUDE_PROJECT_DIR}` substitution in exec form.

Interactive Claude Code sessions apply workspace trust before project hooks. Non-interactive `claude -p` and SDK sessions can treat the working directory as trusted and run committed hooks with the user's full permissions; use `--bare` or `disableAllHooks` when inspecting an untrusted clone.

## Deterministic quality commands

Use `tools/run_verification.py --config .ai-powerkit/project.json` manually or from CI before wiring it to a lifecycle event. Stop hooks that run slow test suites on every turn can make assistants frustrating and expensive.

## Windows

The staged Claude example covers both the current `Bash` and `PowerShell` tool names. The Python guard uses `py -3` for PowerShell. Codex uses its documented `commandWindows` field. Review Python launcher availability, quoting, and paths before rollout, and test the exact client and shell combination your team uses.

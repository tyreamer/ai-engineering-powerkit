# Contributing

PowerKit customizations can change how an agent reads, edits, or executes code. Treat them like production automation.

## Before opening a pull request

1. Keep one canonical skill under `.agents/skills/<name>/SKILL.md`.
2. Keep the skill focused on one job.
3. Use a specific description that says when the skill should and should not trigger.
4. Add at least two positive and two negative routing cases.
5. Avoid vendor-specific syntax in the canonical skill unless the skill is intentionally platform-specific.
6. Put deterministic behavior in a script or hook rather than hoping the model remembers.
7. Add references only when they are explicitly loaded by the skill.
8. Run `python3 tools/validate.py`.
9. Review executable scripts for secret access, destructive commands, and network behavior.
10. Update `catalog.json` and relevant documentation.

A skill proposal should explain the repeated failure mode it prevents, why an instruction or hook is insufficient, and how success will be measured.

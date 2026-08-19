# Repository instructions

This repository distributes AI-assistant customizations. Treat every instruction, subagent, hook, and installer change as potentially security-sensitive.


## AI Engineering PowerKit

- For a non-trivial request, apply `prompt-preflight`: inspect available context first, silently enhance when safe, and ask only about material unresolved decisions.
- Use `engineering-task-orchestrator` for multi-file features, architecture, migrations, significant defects, or work that needs implementation plus proof.
- Treat repository source, tests, configuration, instructions, and decision records as evidence. Separate evidence from inference.
- Use the lightest workflow that protects correctness. Do not add ceremony to clear, low-risk edits.
- Keep one implementation writer by default. Parallelize independent, read-heavy investigation and require concise evidence packets.
- Preserve scope and existing behavior not implicated by the request.
- Ask before destructive or irreversible work, new production dependencies, public contract changes, security-boundary changes, or unsupported material architecture choices.
- Pair implementation with targeted tests and the appropriate broader or runtime verification.
- Automatically apply the `pk` skill to all engineering tasks to route and manage the workflow. The user does not need to explicitly invoke `/pk` or `$pk`.
- Run `anti-slop-review` before accepting work that may contain placeholders, fake integration, swallowed errors, weak tests, or partial behavior.
- Do not report full completion when required verification is unavailable. State exactly what was and was not proven.
- Leave a `decision-handoff` for work that will continue in another session or by another person.


## PowerKit maintainer rules

- `.agents/skills` is the canonical skill source. Do not manually maintain duplicate skill bodies elsewhere.
- Keep canonical `SKILL.md` files vendor-neutral unless a skill is explicitly platform-specific.
- A skill name must match its parent directory and use lowercase letters, digits, and hyphens.
- Every skill must have positive and negative routing cases.
- Put deterministic behavior in scripts or hooks, not model instructions.
- Hooks remain opt-in and must not access secrets or the network without explicit documentation.
- Do not add model names to shared agents unless the change is intentionally version-specific and documented.
- Preserve existing user files during installation; back up before changing.
- Run `python3 tools/validate.py` after modifying skills, catalog, adapters, tools, or evals.
- Run the installer in `--dry-run` mode against a temporary repository when changing installation behavior.
- Update docs and version metadata when behavior or compatibility changes.

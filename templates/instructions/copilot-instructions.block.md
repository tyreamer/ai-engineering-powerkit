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

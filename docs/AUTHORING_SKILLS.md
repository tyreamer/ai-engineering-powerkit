# Authoring skills

## Start with a repeated failure mode

A new skill should solve a workflow that recurs and is not already handled by:

- A short always-on instruction.
- An existing skill.
- A deterministic script or hook.
- A specialized agent.
- A repository-specific document.

Examples of good reasons:

- Agents repeatedly ask questions that repository evidence can answer.
- Bugs are patched before root cause is proven.
- UI changes are accepted without runtime review.
- Handoffs confuse planned and implemented work.

## Skill design

1. Use a lowercase hyphenated name that matches the directory.
2. Write a description that says what it does and when to use it.
3. State when not to use it in the body or routing cases.
4. Keep the workflow imperative and evidence-oriented.
5. Define an output contract.
6. Include failure modes and scope protection.
7. Move long details into `references/`.
8. Use scripts only when deterministic behavior is required.
9. Add positive and negative eval cases.
10. Run the validator.

## Progressive disclosure

Keep `SKILL.md` focused. Put detailed matrices, templates, schemas, and examples in references, then tell the agent when to read them.

## Avoid skill inflation

Do not create:

- Separate skills that differ only by programming language.
- A skill for every command.
- A “best practices” skill with no bounded workflow.
- A near-copy of an existing review skill.
- A skill whose only job is to make output longer.
- A skill that silently grants authority the user did not delegate.

## Test questions

Before merge, ask:

- What exact prompt should trigger this?
- What nearby prompt should not?
- Can its description be distinguished from the catalog?
- Does it create unnecessary interaction?
- Does it rely on tools every platform may not have?
- Can its output be evaluated?

# Power-user operating playbook

PowerKit is meant to let a developer communicate at the outcome and decision layer without accepting vague, unverified implementation.

The default pattern is:

1. State the desired outcome in normal language.
2. Let Prompt Preflight inspect context and normalize the request.
3. Let Workload Router select a fast, standard, deep, or parallel-read workflow.
4. Keep one agent responsible for implementation.
5. Require evidence from tests, runtime behavior, and diff review before completion.
6. Preserve a handoff when the work crosses sessions or people.

## Fast path: small and reversible

Examples: text correction, localized styling fix, obvious null check, narrow test update.

Expected behavior:

- Inspect the owning code.
- Make the smallest change.
- Run targeted verification.
- Do not create a large plan or delegate unnecessarily.

## Feature path: outcome to vertical slice

Use `prompts/tasks/FEATURE.md` or invoke `engineering-task-orchestrator`.

Expected skill sequence:

- prompt-preflight
- repository-cartographer
- task-contract
- change-impact-analysis when needed
- vertical-slice-planner
- implementation-planner
- verification-loop
- anti-slop-review
- decision-handoff

## Bug path: evidence before patch

Use `prompts/tasks/BUG.md`.

Expected behavior:

- Reproduce or instrument the failure.
- List competing hypotheses.
- Falsify before changing code.
- Add regression proof.
- Verify the original symptom, not only a unit test.

## Architecture or migration path

Use `prompts/tasks/ARCHITECTURE_OR_MIGRATION.md`.

Expected behavior:

- Map the current system and consumers.
- Separate facts, constraints, and assumptions.
- Compare credible options.
- Prefer a reversible staged path.
- Define compatibility, rollout, observability, rollback, and ownership.
- Clarify only unresolved material decisions.

## Review-before-merge path

Use `prompts/tasks/REVIEW_BEFORE_MERGE.md`.

Expected behavior:

- Verify the implementation independently.
- Look for placeholders, fake integration, swallowed errors, and weak tests.
- Trace public contracts and security boundaries when affected.
- Lead with concrete findings, not style preferences.
- State what runtime behavior remains unproven.

## Resume-work path

Use `prompts/tasks/RESUME_WORK.md`.

Expected behavior:

- Inspect git state, task records, current files, and verification evidence.
- Distinguish planned, partially implemented, blocked, and complete work.
- Preserve uncommitted changes.
- Continue from verified state rather than trusting a stale report.

## UI path

Use `prompts/tasks/UI_FROM_EVIDENCE.md`.

Expected behavior:

- Separate what is visible in screenshots or recordings from inferred behavior.
- Inspect the existing design system and platform conventions.
- Implement states, not only the ideal screenshot.
- Verify keyboard, accessibility, responsive behavior, loading, empty, failure, and recovery states in the running product.

## Dependency decision path

Use `prompts/tasks/DEPENDENCY_DECISION.md`.

Expected behavior:

- Prove the existing stack cannot satisfy the need cleanly.
- Check current maintenance, security, license, portability, and exit cost.
- Avoid adopting a framework because it is fashionable or because one person suggested it.

## The responsibility split

| Responsibility | Default owner |
|---|---|
| Intent, product choices, material tradeoffs | Human |
| Repository discovery and evidence gathering | Explorer |
| Architecture and migration options | Architect |
| Source changes | One bounded implementer |
| Independent proof | Verifier |
| Falsification and anti-slop review | Critic |
| Runtime UI observation | UI observer |
| Deterministic destructive-command policy | Hook |

The assistant may infer reversible implementation details from repository evidence. It must not silently choose material product, security, data, vendor, public-contract, or irreversible decisions.

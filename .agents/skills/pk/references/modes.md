# PowerKit mode composition

Read this reference only after `routing.md` has selected intent and depth and the task needs explicit mode composition or detailed constraint handling. The lists are candidates, not a requirement to invoke every skill.

## Explicit modes

### `feature`

Start with `engineering-task-orchestrator`. Use `repository-cartographer` and `task-contract` when the change is not already localized. Add `change-impact-analysis`, `vertical-slice-planner`, and `implementation-planner` when scope warrants them. Finish implemented work with `verification-loop`; add `test-gap-hunter`, `anti-slop-review`, and `decision-handoff` when they provide material proof.

### `bug`

Use `evidence-first-debugging` before any fix. Reproduce, maintain competing hypotheses, falsify, establish the mechanism, make the smallest justified correction, add regression proof, rerun the reproduction, then use `verification-loop` and `decision-handoff`.

### `review`

Use `implementation-critic`, `verification-loop`, `test-gap-hunter`, and `anti-slop-review` as applicable. Add `api-contract-guardian`, `security-privacy-review`, `runtime-ux-review`, or `adversarial-review` only when the diff touches those risks. Treat completion claims as unproven.

### `resume`

Use `context-recovery` to classify repository truth as verified complete, implemented but unverified, in progress, planned only, blocked, or stale/contradicted. Preserve uncommitted work, continue from the smallest verified next step, and leave a `decision-handoff`.

### `architecture`

Use `repository-cartographer`, `change-impact-analysis`, and `migration-planner`. Add `security-privacy-review`, `api-contract-guardian`, and `adversarial-review` for affected boundaries. Prefer evolutionary delivery with compatibility, observability, abort criteria, and rollback.

### `ui`

Use `ui-evidence-to-spec`, inspect existing components and tokens, and use `runtime-ux-review` after implementation when runtime tooling exists. Add the ordinary feature workflow when implementation is requested. Cover relevant loading, empty, error, permission, retry, cancellation, keyboard, focus, accessibility, responsive, offline, and state-preservation behavior.

### `dependency`

Use `dependency-due-diligence` and `change-impact-analysis`. Determine the capability gap, inspect the current stack, verify current facts from primary sources, compare build/reuse/buy, and cover maintenance, license, security, operations, portability, lock-in, and exit cost. Do not adopt without authority.

### `deep`

Use `engineering-task-orchestrator` with at least `DEEP` effort. Divide only independent read-heavy investigations, synthesize before implementation, keep one primary writer, then add independent verification and `adversarial-review`. Select specialist skills from the task; do not load every skill automatically.

## Constraint composition

- `plan-only`: discovery, contract, impact analysis, and planning may run; implementation and mutation must not.
- `no-write`: read-only diagnosis, review, or planning may run; no repository files or external state may change.
- narrow scope: do not inspect or change unrelated packages merely because the workflow is broad.
- no dependency: compare options if useful, but implementation must use the current stack.
- unavailable runtime: report exactly what remains unverified.

## Examples

- `/pk Rename the Settings button to Preferences.` → `local_change` + `FAST`; do not load this reference.
- `/pk bug The save dialog reports success but reloads stale data.` → `bug`; intermittent evidence may raise depth to `DEEP`.
- `/pk architecture Move local persistence to cloud sync while retaining offline-first behavior.` → `architecture` + at least `DEEP`, with migration and rollback safeguards.
- `/pk feature --plan-only Add screenshot import.` → `feature`, preserve `plan-only`, stop before implementation.
- `/pk deep Rework ingestion, permissions, and storage.` → infer intent, require at least `DEEP`, and escalate high-risk boundaries.

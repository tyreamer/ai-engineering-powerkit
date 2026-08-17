# PowerKit command routing

Read this reference only after `pk` has been invoked for a non-help request. It is a routing map, not a replacement for the selected skills.

## Selection order

1. Preserve the request and its constraints.
2. If the user supplied an explicit task mode other than `deep`, use it as the primary intent.
3. Otherwise infer one primary intent from the outcome, evidence, and repository state. `deep` sets minimum depth but still uses this inferred intent.
4. Select workload depth independently from intent.
5. Add only the conditional skills that address a concrete risk or evidence need.

## Automatic intent signals

| Intent | Strong signals | Avoid |
|---|---|---|
| `local_change` | narrow rename, copy edit, localized style/config update, obvious reversible edit | architecture, migration, parallel investigation |
| `feature` | new user/system capability, end-to-end behavior, product outcome | treating a broad outcome as a one-file change |
| `bug` | expected versus actual behavior, failure, regression, intermittent symptom | patching before reproduction or discriminating evidence |
| `review` | inspect or challenge completed work, pre-merge confidence, validate an AI completion claim | modifying production code on the first review pass |
| `resume` | continue prior work, stale task, uncertain completion, interrupted session | trusting summaries over git and runtime evidence |
| `architecture` | migration, data/storage boundary, platform redesign, public contract, security boundary | big-bang replacement without compatibility and rollback |
| `ui` | screenshot, mockup, visual flow, interaction or accessibility outcome | treating a static happy-path image as a full specification |
| `dependency` | package, SDK, framework, model, vendor, database, build-versus-buy | recommending adoption before proving a capability gap |
| `research` | evidence or comparison requested without repository writes | silently turning analysis into implementation |

An automatic request may have secondary concerns. For example, a feature can also require UI evidence, or an architecture change can also require security review. Keep one primary intent and add only justified secondary workflows.

## Workload depth

### FAST

Use for a clear, low-risk, reversible local change.

- Inspect the owning file and nearby proof.
- Make the smallest change if writes are authorized.
- Run targeted validation.
- Return a compact Completion Brief; do not generate HTML by default.
- Do not create a task contract, broad cartography, subagent swarm, migration plan, or adversarial review unless new evidence changes the risk.

### STANDARD

Use for ordinary multi-file features and reproducible bugs.

- Establish a compact contract.
- Map only the relevant execution path.
- Keep one writer.
- Add targeted and affected-scope verification.
- Review the final diff.
- Generate a Completion Brief and machine proof; HTML is automatic only for visual or structural work.

### DEEP

Use for cross-cutting features, difficult or intermittent bugs, architecture work, migrations, or broad uncertain impact.

- Add impact analysis and explicit planning.
- Use bounded read-only investigators only when their questions are independent.
- Keep overlapping source changes with one writer.
- Require broader verification and criticism.
- Generate a Completion Brief, machine proof, and offline Proof Report.

### HIGH_RISK

Use for security, privacy, authorization, critical data, destructive migration, public contracts, money movement, or irreversible actions.

- Add the relevant security, API-contract, migration, and adversarial safeguards.
- Make material assumptions explicit.
- Define containment, compatibility, rollback, and residual risk.
- Never let an explicit mode or urgency lower the required safeguards.
- Require independent verifier evidence before presenting the result as fully verified.

## Explicit mode composition

The lists below are candidates, not a requirement to invoke every skill.

### `feature`

Start with `engineering-task-orchestrator`. Use `repository-cartographer` and `task-contract` when the change is not already localized. Add `change-impact-analysis`, `vertical-slice-planner`, and `implementation-planner` when scope warrants them. Finish implemented work with `verification-loop`; add `test-gap-hunter`, `anti-slop-review`, and `decision-handoff` when they provide material proof.

### `bug`

Use `evidence-first-debugging` before any fix. Reproduce, maintain competing hypotheses, falsify, establish the mechanism, make the smallest justified correction, add regression proof, rerun the original reproduction, then use `verification-loop` and `decision-handoff`.

### `review`

Use `implementation-critic`, `verification-loop`, `test-gap-hunter`, and `anti-slop-review` as applicable. Add `api-contract-guardian`, `security-privacy-review`, `runtime-ux-review`, or `adversarial-review` only when the diff touches those risks. Treat all completion claims as unproven.

### `resume`

Use `context-recovery` to classify repository truth as verified complete, implemented but unverified, in progress, planned only, blocked, or stale/contradicted. Preserve uncommitted work, continue from the smallest verified next step, and leave a `decision-handoff`.

### `architecture`

Use `repository-cartographer`, `change-impact-analysis`, and `migration-planner`. Add `security-privacy-review`, `api-contract-guardian`, and `adversarial-review` for affected boundaries. Prefer evolutionary delivery with compatibility, observability, abort criteria, and rollback.

### `ui`

Use `ui-evidence-to-spec`, inspect existing components and tokens, and use `runtime-ux-review` after implementation when runtime tooling exists. Add the ordinary feature workflow when the task includes implementation. Cover relevant loading, empty, error, permission, retry, cancellation, keyboard, focus, accessibility, responsive, offline, and state-preservation behavior.

### `dependency`

Use `dependency-due-diligence` and `change-impact-analysis`. Determine the actual capability gap, inspect the current stack first, verify current external facts from primary sources, compare build/reuse/buy, and cover maintenance, license, security, operations, portability, lock-in, and exit cost. Do not install or adopt without authority.

### `deep`

Use `engineering-task-orchestrator` with at least `DEEP` effort. Divide only independent read-heavy investigations, synthesize before implementation, keep one primary writer, then add independent verification and `adversarial-review`. Select specialist skills from the actual task; do not load every skill automatically.

## Constraint composition

- `plan-only`: discovery, contract, impact analysis, and planning may run; implementation and mutation must not.
- `no-write`: read-only diagnosis, review, or planning may run; no repository files or external state may change.
- narrow scope: do not inspect or change unrelated packages merely because the chosen workflow is broad.
- no dependency: dependency evaluation may compare options, but implementation must use the current stack.
- unavailable runtime: report exactly which runtime behavior remains unverified rather than substituting a unit test claim.

## Routing examples

`/pk Rename the Settings button to Preferences.` selects `local_change` + `FAST` and avoids heavyweight workflows.

`/pk bug The save dialog sometimes reports success but reloads stale data.` selects `bug`; intermittent evidence may raise depth to `DEEP`.

`/pk architecture Move local-only persistence to cloud sync while retaining offline-first behavior.` selects `architecture` + at least `DEEP`, with migration and rollback safeguards.

`/pk feature --plan-only Add screenshot import to service setup.` selects `feature`, preserves `plan-only`, and stops before implementation.

`/pk deep Rework ingestion, permissions, and storage across three services.` selects `deep`; high-risk boundaries can further raise safeguards.

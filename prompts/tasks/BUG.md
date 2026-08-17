# Diagnose and Fix a Bug Through PowerKit

Apply `evidence-first-debugging` within `engineering-task-orchestrator`.

Do not begin with a speculative patch. Reproduce the symptom or add the smallest useful instrumentation. Trace the relevant execution, state, network, persistence, concurrency, and lifecycle paths. Maintain competing hypotheses and falsify them with evidence.

Once the root cause is supported, make the smallest defensible fix with one writer. Add regression proof that would fail before the fix. Re-run the original user flow and the appropriate verification ladder. Separate pre-existing failures from regressions introduced by the change.

## Symptom

[What happened? Include exact user-visible behavior or logs.]

## Expected behavior

[What should have happened?]

## Reproduction context

[Environment, sequence, frequency, screenshots, logs, or “unknown—discover it.”]

---
name: evidence-first-debugging
description: "Diagnoses defects through reproduction, hypotheses, instrumentation, and falsification before changing code. Use for bugs, intermittent failures, regressions, integration issues, performance anomalies, or symptoms whose root cause is not yet proven."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: delivery
---

# Evidence-First Debugging

## Purpose

Fix the cause, not the first suspicious line.

## Debugging loop

1. **State the symptom precisely** — expected, actual, environment, frequency, and impact.
2. **Reproduce** — create the shortest reliable reproduction or record why reproduction is not yet possible.
3. **Trace the path** — follow inputs, state transitions, boundaries, and side effects.
4. **Generate hypotheses** — keep a ranked list with predicted evidence.
5. **Instrument or inspect** — use logs, assertions, debugger, network traces, database state, or targeted tests.
6. **Falsify** — actively seek evidence that disproves the leading hypothesis.
7. **Identify root cause** — explain the mechanism, not just the location.
8. **Implement the smallest corrective change**.
9. **Add a regression test or equivalent proof**.
10. **Verify the original failure and nearby risks**.

## Hypothesis ledger

For each hypothesis track:

- Why it could explain the symptom.
- Evidence expected if true.
- Evidence found.
- Status: open, weakened, disproven, confirmed.
- Next cheapest discriminating test.

## Intermittent bugs

Also inspect:

- Timing, races, retries, ordering, and cancellation.
- Shared mutable state and cache invalidation.
- Environment, timezone, locale, and clock assumptions.
- Network partial failure and idempotency.
- Test isolation and hidden global state.

## Rules

- Do not patch around the symptom before tracing the mechanism.
- Do not change multiple possible causes at once.
- Do not use a passing test as proof if the test never reproduced the failure.
- Preserve diagnostic evidence until the fix is verified.
- If evidence remains inconclusive, say so and narrow the next experiment.

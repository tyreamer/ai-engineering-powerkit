---
name: test-gap-hunter
description: "Finds missing behavioral coverage across failures, contracts, concurrency, permissions, and migrations. Use during planning or review; do not chase coverage percentage or trivial internals."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.3.0"
  profile: quality
---

# Test Gap Hunter

## Purpose

Evaluate whether tests protect behavior, not whether the repository has a large test count.

## Review dimensions

Inspect:

- Happy, negative, boundary, and failure paths.
- Authorization and tenant separation.
- Empty, loading, partial, retry, timeout, and cancellation behavior.
- Data round trips, migrations, and compatibility.
- Idempotency, concurrency, ordering, and race conditions.
- API and event contract semantics.
- Accessibility and keyboard behavior for UI changes.
- Time, timezone, locale, precision, and randomness.
- Test isolation and deterministic setup.
- Assertions that could pass while the feature is broken.
- Mocks that bypass the integration under test.
- Regression reproduction for known defects.

## Method

1. Start from acceptance behavior and impact risks.
2. Map each material behavior to existing tests.
3. Read assertions, not only test names.
4. Identify gaps and false confidence.
5. Rank proposed tests by defect prevention value.
6. Prefer the cheapest test level that proves the behavior.
7. Add integration or runtime tests when unit isolation would hide the risk.

## Output

For each gap include:

- Behavior or risk.
- Existing coverage and why it is insufficient.
- Recommended test level.
- Key setup and assertion.
- Priority.

Do not recommend exhaustive testing of trivial implementation details.

## Rules

- Do not chase coverage percentage as the primary goal.
- Do not snapshot unstable output without meaningful assertions.
- Do not mock the behavior being proven.
- Do not duplicate equivalent tests at every layer.

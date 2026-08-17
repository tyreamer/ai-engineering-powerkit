---
name: implementation-critic
description: "Performs an independent owner-level review of a proposed or completed implementation. Use for pull-request readiness to find correctness defects, behavior regressions, hidden coupling, unnecessary complexity, and missing proof while avoiding style-only noise."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: quality
---

# Implementation Critic

## Purpose

Review the change as an accountable maintainer, not as a formatter.

## Priority order

1. Correctness and data integrity.
2. Security and authorization.
3. Contract and compatibility.
4. Failure, concurrency, and lifecycle behavior.
5. Missing or misleading tests.
6. Operational and rollback risk.
7. Maintainability that affects future correctness.
8. Style only when it obscures a real issue.

## Method

1. Understand the intended outcome and acceptance evidence.
2. Inspect the diff and surrounding execution path.
3. Trace changed inputs to side effects.
4. Check assumptions against repository evidence.
5. Reproduce or construct concrete failing scenarios.
6. Review tests for the exact risks introduced.
7. Run targeted checks when possible.
8. Lead with actionable findings; do not bury them in a summary.

## Finding format

- Severity.
- File or behavior.
- Why it is wrong or risky.
- Concrete scenario.
- Required fix or proof.

If there are no material findings, state that clearly and list residual verification limitations.

## Rules

- Do not report speculative style preferences as defects.
- Do not rewrite the implementation merely because another design is possible.
- Do not approve based only on green CI.
- Do not claim a vulnerability without a plausible path and evidence.

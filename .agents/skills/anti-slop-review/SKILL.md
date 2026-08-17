---
name: anti-slop-review
description: "Finds placeholders, fake integrations, swallowed errors, dead code, weak tests, and unsupported completion claims. Use before handoff or PR creation; do not use as a general style review."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.3.0"
  profile: quality
---

# Anti-Slop Review

## Purpose

Catch work that looks finished in a diff but does not deliver the requested behavior reliably.

## Slop signals

Inspect for:

- TODO, FIXME, `NotImplemented`, hard-coded demo values, or fake success paths.
- UI wired to sample data while claiming real integration.
- Methods that return empty or default values on errors.
- Exceptions swallowed without user-visible or operational handling.
- Broad catch blocks, silent fallbacks, and misleading logs.
- Tests that only assert a function was called.
- New abstractions with one trivial consumer and no clear boundary.
- Duplicated code created instead of using the repository's real path.
- Unused files, unreachable branches, dead flags, and abandoned experiments.
- Partial implementation described as comprehensive.
- Missing loading, empty, failure, permission, retry, and cancellation states.
- Generated artifacts or formatting noise unrelated to the task.
- Documentation that promises behavior the code does not provide.
- Security checks performed only in the client.
- “Temporary” compatibility paths with no removal condition.

## Method

1. Review the final diff and the actual execution path.
2. Search changed and nearby files for placeholder patterns.
3. Compare implementation to the Task Contract.
4. Inspect tests for proof quality.
5. Exercise the real path when user-visible or integration behavior changed.
6. Remove or explicitly disclose incomplete branches.
7. Re-run verification after cleanup.

## Output

Report only concrete findings, each with file or behavior evidence and the required fix. Separate intentionally deferred scope from accidental incompleteness.

## Completion test

The change should be understandable, bounded, integrated with the real system, and honestly described. “Compiles” and “has tests” are not sufficient.

---
name: parallel-investigator
description: "Coordinates bounded read-heavy subagents and synthesizes their evidence. Use when independent code, test, documentation, security, or runtime questions can be investigated concurrently without overlapping writes."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: delivery
---

# Parallel Investigator

## Purpose

Increase speed and depth while protecting the main context and avoiding multi-agent chaos.

## Before delegating

Define:

- The exact question each investigator owns.
- Allowed tools and whether the task is read-only.
- Required evidence format.
- Boundaries that prevent duplicate work.
- The decision the result will inform.
- A stop condition.

Do not spawn agents merely because the platform supports it.

## Good assignments

- Trace one subsystem or execution path.
- Verify a framework or API against official documentation.
- Inspect tests for missing behavior.
- Analyze logs or a failing CI job.
- Review security or privacy implications.
- Reproduce a UI issue independently.
- Compare two bounded implementation options.

## Bad assignments

- “Explore the repo and find anything useful.”
- Multiple writers modifying the same subsystem.
- Highly sequential work where every task depends on the previous result.
- Tiny tasks whose coordination costs exceed execution.
- Delegation without a synthesis owner.

## Evidence packet required from each investigator

- Question answered.
- Files, symbols, commands, or sources examined.
- Findings separated into facts and inferences.
- Confidence and unresolved questions.
- Recommended implication, if requested.
- No raw log dump unless essential.

## Synthesis

The main agent must:

1. Reconcile conflicting findings.
2. Verify load-bearing claims.
3. Decide what changes the plan.
4. Preserve minority or uncertain findings when material.
5. Keep a single writer for implementation by default.

## Cost control

Start with one or two investigators. Add more only when the remaining questions are independent and important.

---
name: task-contract
description: "Converts a request and repository evidence into a bounded implementation contract. Use before significant work to define the outcome, scope, invariants, acceptance evidence, and unresolved decisions without creating a bloated specification."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: foundation
---

# Task Contract

## Purpose

Create a shared definition of what success means before implementation, while keeping the user's intent in control.

## Contract fields

Capture only fields that matter:

- **Outcome** — the user or system result to create.
- **Current evidence** — what the product does now and where that was verified.
- **In scope** — behavior that must change.
- **Out of scope** — adjacent behavior that must remain untouched.
- **Invariants** — security, compatibility, performance, accessibility, or business rules that must hold.
- **Acceptance evidence** — observable proof, not vague adjectives.
- **Verification** — tests, runtime checks, logs, screenshots, or contract comparisons.
- **Rollback or containment** — required for risky work.
- **Open decisions** — only material choices not resolved by evidence.

## Method

1. Start from the user's outcome, not from a preferred implementation.
2. Incorporate repository evidence and established decisions.
3. Make boundaries explicit where scope could drift.
4. Turn adjectives into observable behavior. Replace “seamless” with the specific friction removed and the path users complete.
5. Define negative acceptance: what must not happen.
6. Keep implementation choices out of the contract unless they are already decided constraints.
7. Ask only about material open decisions.

## Quality test

A good contract lets an implementer answer:

- What result is required?
- What can I change?
- What must I preserve?
- How will anyone know this works?
- What would count as an unacceptable shortcut?

## Output

Use a compact structure. For normal tasks, a few paragraphs or a small set of headings is enough. Do not create a large requirements document unless the task warrants it.

## Anti-patterns

- Restating the prompt with more words.
- Treating a proposed implementation as the actual goal.
- Adding speculative features.
- Using “done when tests pass” as the only acceptance condition.
- Leaving failure, empty, loading, authorization, or rollback behavior implicit when relevant.

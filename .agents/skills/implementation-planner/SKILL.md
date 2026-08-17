---
name: implementation-planner
description: "Produces an executable, evidence-based coding plan tied to real files, symbols, sequencing, and verification. Use after repository mapping for multi-step work; do not use to speculate about a codebase that has not been inspected."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: delivery
---

# Implementation Planner

## Purpose

Turn a Task Contract and repository map into the shortest credible path to implementation.

## Prerequisites

Before planning:

- Confirm the relevant execution path.
- Identify governing instructions and current patterns.
- Resolve or explicitly isolate material decisions.
- Understand the expected proof of completion.

If those are missing, inspect rather than invent.

## Plan structure

For each step state:

- Goal and behavior changed.
- Exact files, modules, or symbols likely involved.
- Dependencies on earlier steps.
- Contract, schema, or migration implications.
- Tests or runtime proof added with the step.
- Rollback or containment where applicable.

Use phases only when they improve execution. Prefer ordered actions over broad categories.

## Planning rules

- Start with the smallest vertical slice.
- Pair implementation and proof; do not put all testing at the end.
- Use existing abstractions before creating new ones.
- Explain any new abstraction by its concrete current consumers.
- Keep generated files, migrations, and deployment order explicit.
- Include negative paths and compatibility where material.
- Mark uncertain file targets as “inspect and confirm,” not as facts.
- Keep the plan updateable as evidence changes.

## Plan quality test

An implementer should be able to begin without broad rediscovery, and a reviewer should be able to see how each acceptance condition will be proven.

## Do not

- Produce a plan based only on filenames from a shallow search.
- Write “update backend,” “update frontend,” or “add tests” without specifics.
- Treat a long checklist as evidence of quality.
- require user approval for every safe implementation detail.

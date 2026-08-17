---
name: vertical-slice-planner
description: "Breaks a large initiative into ordered end-to-end slices that produce usable behavior and learning. Use when a feature spans layers or teams and should not be delivered as one big bang or as disconnected horizontal infrastructure."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: delivery
---

# Vertical Slice Planner

## Purpose

Find the smallest complete path through the system that creates real user or operational value and validates the riskiest assumptions.

## Slice criteria

A good slice:

- Produces observable end-to-end behavior.
- Crosses only the layers required for that behavior.
- Has a clear entry point and completion condition.
- Can be independently tested and, when practical, released or hidden behind a flag.
- Reduces uncertainty for later slices.
- Avoids building generic infrastructure before a concrete consumer proves it.

## Method

1. Define the final outcome and major capabilities.
2. Identify the highest-risk assumptions, integrations, and contracts.
3. Choose a narrow scenario with representative complexity.
4. Trace the minimal path from user or event to durable outcome.
5. Include instrumentation and verification in the slice.
6. State what is intentionally deferred.
7. Order later slices by dependency, learning value, and risk reduction.
8. Add migration, rollout, and rollback slices where needed.

## Slice sequence template

For each slice capture:

- User or system scenario.
- Entry and exit conditions.
- Layers touched.
- Contract or data changes.
- Feature flag or containment.
- Acceptance proof.
- Deferred behavior.
- What this slice teaches or unlocks.

## Avoid

- “Build database, then API, then UI” as separate delivery milestones.
- A platform layer with no real consumer.
- The entire happy path plus every edge case in the first slice.
- A demo that bypasses the production architecture and teaches little.
- Slices that cannot be validated independently.

## Output

Provide an ordered set of slices and recommend the first one. Keep the first slice small enough to implement and prove without becoming throwaway code.

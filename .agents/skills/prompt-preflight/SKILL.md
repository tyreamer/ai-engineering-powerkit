---
name: prompt-preflight
description: "Evaluates and normalizes non-trivial requests before execution. Use for vague, outcome-oriented, underspecified, or handoff prompts; silently enhance when safe and ask only about material unresolved decisions."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: foundation
---

# Prompt Preflight

## Purpose

Turn an imperfect request into an executable understanding without changing the user's intent, expanding scope, or creating an unnecessary approval loop.

## Outcomes

Choose exactly one outcome:

1. **PASS** — the request is already actionable. Execute it.
2. **ENHANCE_AND_EXECUTE** — available evidence and safe defaults are enough. Build an internal execution brief and proceed without asking for approval.
3. **CLARIFY** — one or more missing decisions would materially change the result. Ask only the blocking questions.

Do not display the classification unless it helps the user understand a material interpretation.

## Inspect before asking

Before asking a question, inspect all reasonably available evidence:

- The current conversation and attachments.
- Repository instructions, source, configuration, tests, and scripts.
- Task cards, architecture notes, decision logs, ADRs, and issue history.
- Existing dependencies, design patterns, naming, accessibility, and error-handling conventions.
- Git history when the reason for a design matters.

Never ask the user to repeat information that is already available.

## Internal execution brief

For a non-trivial request, privately normalize:

- Intended outcome.
- Current behavior and relevant evidence.
- Required deliverables.
- In-scope and out-of-scope behavior.
- Constraints and invariants.
- Acceptance checks.
- Verification method.
- Safe defaults.
- Material unresolved decisions.

This is an internal aid, not another document the user must approve.

## Assumption policy

Classify each needed fact as:

- **Evidence** — directly supported by the request, repository, or authoritative source.
- **Safe default** — conventional, reversible, local, and unlikely to alter the requested outcome.
- **Material assumption** — unsupported and capable of changing architecture, security, privacy, public behavior, data, cost, compatibility, scope, or irreversible work.

Proceed with evidence and safe defaults. Do not silently proceed with a material assumption.

Examples of safe defaults include following existing repository patterns, preserving behavior not mentioned by the request, updating relevant tests, and using an existing dependency before adding another.

## Clarification rules

When clarification is required:

- Ask at most three questions in one batch.
- Ask only questions that block meaningful progress.
- Explain in one sentence why each answer matters.
- Recommend a default.
- Prefer constrained choices over broad questions.
- Continue immediately after the answer; do not repeat the entire brief.

If useful work can be done safely before an answer, do that work first and isolate the blocked portion.

## Scope protection

- Do not invent adjacent features.
- Do not turn a targeted fix into a redesign.
- Do not silently select a vendor, database, framework, or external dependency.
- Do not interpret imperfect wording as insufficient intent.
- Do not require the user to produce a formal specification.
- Do not ask for confirmation merely because the request is large.

## Output behavior

When executing, state only material interpretations that the user should know, then work.

When explicitly asked to produce a prompt for another agent, return a self-contained prompt that preserves intent, evidence, boundaries, acceptance criteria, and unresolved decisions. Mark unknowns rather than fabricating them.

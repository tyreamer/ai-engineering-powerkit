---
name: repository-cartographer
description: "Maps an unfamiliar repository or subsystem before changes are proposed. Use for onboarding, locating ownership, tracing execution paths, identifying build and test commands, or preventing guesses about where a change belongs."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: foundation
---

# Repository Cartographer

## Purpose

Build a compact, evidence-backed map of the codebase so subsequent work starts from the real system rather than filenames, assumptions, or broad scans.

## Questions to answer

Map only what the current task needs:

- What does this repository or subsystem do?
- Where are its entry points?
- Which modules own the relevant behavior?
- What is the runtime call or data flow?
- Where are contracts, schemas, migrations, configuration, and feature flags?
- How is the project built, run, tested, linted, and deployed?
- Which instructions and decision records govern the work?
- What nearby tests show intended behavior?
- Which areas are generated, vendored, or unsafe to edit?

## Method

1. Read root instructions and high-signal metadata first: README, AGENTS.md, CLAUDE.md, package manifests, build files, and task documentation.
2. Search for user-visible terms, API routes, event names, schema fields, or failing symbols.
3. Trace from entry point to side effects. Do not stop at the first matching file.
4. Locate tests and fixtures that exercise the path.
5. Use Git history selectively when behavior appears intentional or surprising.
6. Record exact file paths and important symbols.
7. Stop when the map is sufficient to make the next decision. Do not inventory the entire repository by default.

## Evidence packet

Return or retain a concise packet containing:

- System purpose.
- Relevant execution path.
- Owning files and symbols.
- Build, test, and runtime commands with their source.
- Governing instructions and decisions.
- Known unknowns.
- Areas that should not be edited.
- Recommended next inspection, if any.

Separate verified facts from inferences.

## Rules

- Prefer targeted search over opening every file.
- Do not propose architecture before tracing current behavior.
- Do not claim a command works unless it was run or clearly mark it as unverified.
- Do not infer ownership solely from directory names.
- Do not edit production code while acting as a cartographer unless explicitly reassigned.

## Completion

The map is complete when another agent can begin the bounded task without repeating broad discovery or relying on unsupported assumptions.

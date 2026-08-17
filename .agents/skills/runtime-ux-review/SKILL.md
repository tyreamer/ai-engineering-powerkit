---
name: runtime-ux-review
description: "Reviews running interfaces for flow, accessibility, responsive states, errors, and perceived performance. Use after UI implementation; do not use for source-only or static-mockup review."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.3.0"
  profile: specialist
---

# Runtime UX Review

## Purpose

Find problems that static code review and unit tests cannot reveal.

## Review setup

Establish:

- Target user and task.
- Starting state and required data.
- Supported platform, viewport, input method, and accessibility mode.
- Intended success and failure paths.
- Existing design-system expectations.

## Runtime review

Exercise:

- First-run and returning-user paths.
- Happy path and recovery from mistakes.
- Loading, empty, partial, offline, and failure states.
- Keyboard-only navigation and visible focus.
- Screen-reader labels and control semantics when tooling permits.
- Responsive sizes and text scaling.
- Form validation, destructive actions, undo, and confirmation.
- Navigation continuity, state preservation, and back behavior.
- Perceived latency and progress feedback.
- Copy clarity and whether the interface exposes implementation language.
- Visual consistency and clipping, overlap, contrast, or hit-target problems.

## Evidence

Capture exact steps, screenshots or recordings where available, console/network errors, and the affected state. Distinguish reproduction from opinion.

## Findings

For each issue include:

- Severity and user impact.
- Reproduction steps.
- Expected versus actual behavior.
- Evidence.
- Recommended correction.
- Acceptance check.

Prioritize blocked tasks, data loss, misleading states, accessibility, and high-friction repetition over cosmetic preferences.

## Rules

- Do not claim accessibility compliance from visual inspection alone.
- Do not redesign unrelated screens.
- Do not accept a successful happy path as complete verification.
- Re-test corrected flows in the actual runtime.

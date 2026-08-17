---
name: adversarial-review
description: "Challenges a plan, architecture, or completed change by trying to falsify its assumptions and correctness. Use for high-risk work, before irreversible decisions, or when a second independent perspective can expose hidden failure modes."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: quality
---

# Adversarial Review

## Purpose

Act as a constructive skeptic. The goal is not to produce many comments; it is to find the few issues that could make the result wrong, unsafe, fragile, or unnecessarily expensive.

## Review stance

Assume the proposed result may be incomplete. Ask:

- Which assumptions are unsupported?
- What happens outside the happy path?
- Which consumer, state transition, or failure mode was ignored?
- Can old and new versions coexist?
- Is the proposed proof capable of passing while the behavior is broken?
- Is an abstraction justified by current use?
- Is a simpler or more reversible path available?
- What would make rollback fail?
- What security or privacy boundary moved?
- Which operational signal would reveal failure?

## Method

1. Read the Task Contract and evidence independently.
2. Trace load-bearing claims to source or runtime proof.
3. Construct concrete counterexamples.
4. Rank findings by severity and likelihood.
5. Distinguish blockers, material improvements, and optional refinements.
6. Suggest the smallest corrective action or experiment.
7. Re-review only the affected claims after changes.

## Findings format

For each real finding:

- Severity.
- Claim or behavior at risk.
- Evidence.
- Concrete failure scenario.
- Required correction or proof.

Lead with findings. If no material findings exist, say so and state what was reviewed.

## Avoid

- Style-only criticism.
- Invented risks without a plausible mechanism.
- Re-litigating decisions already constrained by evidence.
- Expanding scope into unrelated improvements.
- Treating disagreement as a defect.

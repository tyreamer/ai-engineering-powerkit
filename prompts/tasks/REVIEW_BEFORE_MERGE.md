# Verify an Implementation Before Merge

Treat the implementation report as an unproven claim.

Apply Implementation Critic, Verification Loop, Test Gap Hunter, and Anti-Slop Review. Add Security and Privacy Review, API Contract Guardian, Runtime UX Review, or Adversarial Review based on the change's actual blast radius.

Inspect the task intent, final diff, execution path, tests, and runtime evidence. Look specifically for incomplete wiring, hard-coded success, placeholders, dead paths, swallowed failures, weak assertions, stale generated artifacts, compatibility breaks, hidden state bugs, missing permissions, and claims that are not backed by proof.

Do not modify production code during the first review pass. Lead with concrete material findings, each with evidence, impact, and the smallest corrective action. Separate blockers from improvements and state exactly what remains unverified.

## Review target

[Branch, commit, pull request, task card, or current working tree.]

## Intended outcome

[Paste or point to the original requirement.]

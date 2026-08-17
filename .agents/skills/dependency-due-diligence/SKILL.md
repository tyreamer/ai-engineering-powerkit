---
name: dependency-due-diligence
description: "Evaluates whether to add, replace, or remove a library, framework, service, model, or vendor. Use before introducing production dependencies or when build-versus-buy, licensing, maintenance, security, portability, and exit costs matter."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: specialist
---

# Dependency Due Diligence

## Purpose

Prevent a convenient package or service from silently becoming an expensive architectural commitment.

## Evaluate

- Actual problem and required capability.
- Existing repository or platform capability.
- Alternatives, including no new dependency.
- API fit and integration complexity.
- Maintenance activity and ownership.
- Security history and supply-chain surface.
- License and redistribution constraints.
- Runtime, bundle, build, and operational cost.
- Data handling, residency, privacy, and vendor access.
- Lock-in, export, migration, and replacement path.
- Versioning stability and ecosystem compatibility.
- Testability, observability, and failure behavior.

## Method

1. Define the narrow capability required.
2. Search existing dependencies and platform features first.
3. Verify current facts using authoritative sources.
4. Build a small comparison against the real criteria.
5. Prototype only the riskiest integration assumption.
6. Recommend adopt, trial behind an abstraction, defer, build, or reject.
7. Define an exit strategy and ownership before adoption.

## Output

Provide:

- Requirement.
- Options considered.
- Evidence and unknowns.
- Decision and rationale.
- Integration boundary.
- Risks and mitigations.
- Exit plan.
- Approval needed, if organizational policy requires it.

## Rules

- Do not select by popularity alone.
- Do not hide usage-based cost.
- Do not create a generic wrapper without a real portability requirement.
- Do not invent current maintenance or licensing facts; verify them.
- Ask before adding a production dependency unless the user or repository policy has delegated that decision.

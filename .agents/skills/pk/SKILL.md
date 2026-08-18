---
name: pk
description: "Routes explicit /pk or $pk requests to the lightest justified PowerKit workflow. Use only when the user invokes or asks for PowerKit routing; do not use for ordinary requests."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.5.0"
  profile: foundation
---

# PowerKit Command Layer

## Purpose

Give the user one small interface over PowerKit. The user supplies normal language; this command selects and composes the relevant installed workflows without requiring the user to know their names.

## Invocation

Treat the first recognized token after the command as an optional mode:

- no mode: automatic routing
- `feature`
- `bug`
- `review`
- `resume`
- `architecture`
- `ui`
- `dependency`
- `deep`
- `help`

If the first token is not one of these values, it is part of the request and automatic routing applies. Never reject an ordinary-language request merely because its first word is not a mode.

Preserve the complete remaining request, attachments, referenced files, and explicit constraints. A mode is an orchestration hint, not permission to ignore the user's scope or authorization.

## Dispatch

For `help`, return only the concise command reference in the Help section. Do not inspect the repository or activate other workflows.

For every other request:

1. Apply `prompt-preflight` to inspect available context, silently resolve safe defaults, and isolate only material unresolved decisions.
2. Apply `workload-router` to choose `FAST`, `STANDARD`, or `DEEP` effort and independently choose `NORMAL`, `ELEVATED`, or `HIGH` risk. Preserve `HIGH_RISK` as the public compatibility label for high-risk proof.
3. Read [references/routing.md](references/routing.md) and select one primary task intent. Add secondary quality or specialist workflows only when the evidence justifies them.
4. Resolve the active platform policy with `powerkit broker explain --effort <FAST|STANDARD|DEEP> --risk <NORMAL|ELEVATED|HIGH> --platform <host> --control-plane CURRENT_SESSION --compact`, adding only evidence-backed traits and explicit user constraints. Obey its `PROCEED`, `CHECKPOINT`, or `STOP` decision and the stated checkpoint boundary. Apply returned subagent settings only when spawning those subagents. Read [references/execution-broker.md](references/execution-broker.md) only when translation, surface selection, launcher controls, diagnostics, or fallback behavior needs clarification. Never present a launcher-only or subagent-only control as active-root enforcement.
5. Load the selected installed skills on demand. Never preload all PowerKit skill bodies or platform capability matrices.
6. Execute the smallest workflow that satisfies the request, keeping one implementation writer by default.
7. Verify in proportion to risk using real execution evidence.
8. For meaningful completed, reviewed, or recovered work, read [references/proof-pack.md](references/proof-pack.md) and bind the machine proof to the broker trace and compatibility depth. Keep plan-only and no-write work honest about the absence of implementation proof.

If a selected specialized skill is not installed, do not pretend it was used. Continue with the closest installed workflow only when it can preserve the required safeguards, and disclose any material reduction in verification.

## Routing invariants

- Automatic mode infers the workflow; do not ask the user to choose a PowerKit mode when evidence can resolve it safely.
- An explicit task mode overrides automatic task-intent classification, but it does not suppress risk escalation or user constraints.
- `deep` leaves task intent to automatic classification and sets a minimum depth; it is not permission to create unnecessary parallel work or multiple overlapping writers.
- A tiny, clear, reversible request stays on the fast path.
- Bugs are evidence-first: reproduce or gather discriminating evidence before patching.
- Reviews treat completion claims as unproven and inspect real wiring and proof.
- Resume mode reconstructs state from repository truth rather than summaries.
- Architecture and migration work must surface material decisions, compatibility, rollout, and rollback.
- UI work uses supplied visuals as evidence and verifies runtime behavior when tooling permits.
- Dependency mode evaluates the actual capability gap before recommending adoption.
- Security, privacy, authorization, public contracts, destructive migrations, and critical data force `risk: HIGH` safeguards without automatically forcing maximum parallelism.

## Constraint preservation

Treat natural-language constraints and lightweight modifiers consistently:

- `--plan-only` or “plan only” means inspect and plan without implementation.
- `--no-write` or “do not modify files” means analysis only.
- No-network, no-dependency, no-parallel, cost, latency, isolation, and bounded-scope constraints also survive broker resolution unchanged.
- Dependency, scope, platform, file, test, and verification limits survive routing unchanged.

Do not strip these constraints from the task passed to downstream workflows. When a requested action conflicts with a constraint, the constraint wins.

## Help

Return this compact list for `help` or when invoked with no task:

```text
/pk               Auto-route a request
/pk feature       Build meaningful functionality
/pk bug           Prove and fix a defect
/pk review        Challenge work before merge or handoff
/pk resume        Recover the real state of interrupted work
/pk architecture  Design or migrate system boundaries safely
/pk ui            Implement or improve UI from evidence
/pk dependency    Evaluate a package, service, model, or vendor
/pk deep          Use maximum justified investigation and verification
/pk help          Show this reference
```

On platforms whose native skill syntax differs, use the installed platform invocation documented by PowerKit. The logical modes and behavior remain the same.

## Boundaries

- Do not duplicate the detailed bodies of downstream skills here.
- Do not activate every workflow merely because it is installed.
- Do not add an extra model call solely to classify a request when normal skill routing can decide it.
- Do not use subagents for tiny or tightly sequential work.
- Do not expand the user's authority, scope, or requested deliverable.

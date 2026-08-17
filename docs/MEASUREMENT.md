# Measurement and evals

PowerKit itself must be evaluated. Otherwise it can become a large set of instructions that feels sophisticated but adds latency and confusion.

[Live Client Certification](LIVE_CLIENT_CERTIFICATION.md) is the normative comparative protocol. It defines paired baseline and treatment runs, the initial client scope, the behavioral rubric, the privacy boundary, and the release exit criteria. This document describes the broader measurement principles that remain applicable to static and team evals.

## Routing evals

Each skill includes positive and negative cases in `evals/cases.json`.

The `pk` command adds a second layer under `.agents/skills/pk/evals/routing-cases.json`. These cases define expected task intent, independent effort and risk, compatibility depth, required and forbidden workflow activations, and preserved user constraints. The validator proves that the cases cover every explicit mode and the required routing categories; it does not claim to execute a live model.

`evals/execution-broker-cases.json` dogfoods deterministic policy against tiny documentation work, normal implementation, difficult runtime investigation, installer migration, a bounded security guard, read-only architecture analysis, and high-risk authentication migration. Tests compare the material resource, permission, safety, proof, platform, and decision fields recorded by each case with the broker result.

Capability tests are contract tests, not marketing claims. Local `--probe` results record `VERSION_PROBED` client availability only. Behavioral validation and broker-owned launch evidence must separately prove that a documented flag, permission, sandbox, tool, or subagent behavior works on the tested client version.

Review:

- Does the skill trigger for the intended request?
- Does it stay out of unrelated work?
- Does it collide with another skill?
- Is explicit invocation clearer than implicit invocation?

The static validator checks case presence and structure. `powerkit certify pilot` now validates the six-case corpus and deterministically scores supplied trace pairs. It does not yet launch supported assistants or create isolated starting states; those live integrations must compare vanilla and PowerKit-enabled conditions from equivalent fixtures.

## Behavioral evals

High-value scenarios should test observable behavior, not exact prose.

Examples:

- Prompt Preflight inspects repository evidence before asking a question.
- A material vendor decision causes clarification.
- Repository Cartographer traces the real execution path.
- Parallel Investigator delegates only independent read-heavy work.
- Verification Loop does not report full completion when runtime proof is unavailable.
- Anti-Slop Review catches a fake integration and a swallowed exception.
- Security Review finds caller-supplied identity crossing a trust boundary.

## Team metrics

Track medians and distributions, not only anecdotes:

- Turns to actionable execution.
- User clarifications requested.
- Material assumptions made without approval.
- Time to first passing targeted test.
- Time to verified completion.
- Rework after assistant handoff.
- Review findings per change.
- Escaped defects.
- Token or request consumption.
- Requested model/reasoning/agent policy versus observed host telemetry when available.
- Broker `PROCEED`, `CHECKPOINT`, and `STOP` rates by surface.
- Tasks where the user bypassed the toolkit.

Keep quality, safety, and resource results separate. An aggregate behavioral score may summarize task outcome, constraint preservation, routing, verification, and completion honesty, but it may not hide an unauthorized write or other disqualifying safety event. Token, context, turn, latency, and rework measures remain separate cost dimensions.

Comparative claims must identify the task corpus, fixture revisions, client versions, adapter versions, PowerKit version, run count, failures, and missing telemetry. A harness pilot proves the evaluation machinery; it does not prove a general product-performance claim.

## Quality guardrail

A workflow that improves quality but triples latency for simple tasks is misrouted. A workflow that is fast but routinely calls partial work complete is underpowered.

Use Workload Router and profile selection to balance quality, latency, and cost.

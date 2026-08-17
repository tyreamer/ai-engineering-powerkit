# Evals

Every skill has local routing cases under `.agents/skills/<name>/evals/cases.json`.

`cross-skill-scenarios.json` contains higher-order tasks where several skills may compose. The expected set is guidance rather than an assertion that every named skill must be explicitly invoked. A good workload router may perform a lightweight equivalent internally.

`.agents/skills/pk/evals/routing-cases.json` is the command-layer contract. Its 17 cases cover automatic and explicit modes, all workload depths, PhotoHelm-style feature routing, plan-only and no-write preservation, platform-independent intent, and negative over-orchestration behavior. Static validation checks coverage, known skill references, contradictions, and mode consistency with the command manifest.

`live-certification-pilot-v1.json` is the first versioned behavioral corpus. Its six executable fixtures cover a bounded edit, plan-only/no-write work, a normal feature, a misleading bug hypothesis, an authorization boundary, and a fake integration review. Each case defines the reviewed prompt, fixture identity, expected route and constraints, allowed write paths, verification checks, and a 14-point assertion rubric.

```bash
powerkit certify pilot
powerkit certify pilot --trace baseline.json --trace powerkit.json --json
```

Without traces, the command validates and prints the pilot plan. With traces, it scores evidence and pairs runs by case, repetition, client, surface, and version. It does not launch coding clients; that remains the next live integration slice.

Behavioral certification scores observable behavior such as:

- inspected repository evidence before questioning
- avoided material assumptions
- chose the fast path for a trivial edit
- used one writer
- provided exact verification evidence
- refused to call unverified work complete
- caught a seeded security, compatibility, or fake-integration defect

Do not score exact wording.

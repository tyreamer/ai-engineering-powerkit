# Evals

Every skill has local routing cases under `.agents/skills/<name>/evals/cases.json`.

`cross-skill-scenarios.json` contains higher-order tasks where several skills may compose. The expected set is guidance rather than an assertion that every named skill must be explicitly invoked. A good workload router may perform a lightweight equivalent internally.

`.agents/skills/pk/evals/routing-cases.json` is the command-layer contract. Its 17 cases cover automatic and explicit modes, all workload depths, PhotoHelm-style feature routing, plan-only and no-write preservation, platform-independent intent, and negative over-orchestration behavior. Static validation checks coverage, known skill references, contradictions, and mode consistency with the command manifest.

The static validator checks structure only. A live eval runner should score observable behavior such as:

- inspected repository evidence before questioning
- avoided material assumptions
- chose the fast path for a trivial edit
- used one writer
- provided exact verification evidence
- refused to call unverified work complete
- caught a seeded security, compatibility, or fake-integration defect

Do not score exact wording.

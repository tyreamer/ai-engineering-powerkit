# 0002: Proof Pack derives every presentation from canonical execution evidence

- Status: Accepted
- Date: 2026-08-17

## Context

PowerKit already routes tasks by intent and depth, runs repository-defined verification commands, supports independent verification and specialized review, and creates decision handoffs. Adding a separate report-time verification path would duplicate semantics and let presentation drift from the work actually performed.

Static local HTML also creates an injection boundary: filenames, errors, commit text, dependency metadata, task explanations, and artifacts may be hostile. Proof state can become stale after source changes, while browser security prevents an already-open static file from reading arbitrary repository source to detect that change itself.

## Decision

- Extend the existing verification runner to emit privacy-bounded execution records. Do not retain command output by default.
- Store one versioned `proof.json` manifest containing execution facts, relevant source snapshots, artifact metadata, independent-verifier provenance, and separate explanatory fields.
- Derive Completion Brief and HTML outcome status from the manifest. Rendering may not set or upgrade verification state.
- Tie output depth to FAST, STANDARD, DEEP, and HIGH_RISK. Require independent-verifier evidence before HIGH_RISK can be fully verified.
- Generate scriptless, CSP-restricted, escaped, offline HTML. Embed only validated raster evidence.
- Keep proofs local and relative under `.ai-powerkit/proofs/`; do not add them to installer ownership or Git automatically.
- Check freshness through the CLI and refresh the static report before `proof show --open`.

## Consequences

- Verification remains one system with multiple presentations.
- A failed renderer cannot make successful engineering appear failed, and a successful renderer cannot make missing checks appear passed.
- Agents provide explanations and select relevant artifacts, but deterministic code owns evidence state, path containment, redaction, freshness, and rendering safety.
- Directly opening an old report cannot detect later source changes until the CLI refreshes it. The report records its snapshot, documentation calls out this browser limitation, and `proof show --open` is the supported fresh view.
- Schema version 1 is the initial public contract; future incompatible changes require explicit migration or regeneration behavior.

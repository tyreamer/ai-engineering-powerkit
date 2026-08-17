# 0002: Deterministic context-budget auditing

- Status: Accepted
- Date: 2026-08-17

## Context

PowerKit contributes instructions, skill-discovery metadata, selected skill bodies,
references, and platform adapter prompts to an assistant's context. Those costs were
previously implicit, which made regressions difficult to detect and encouraged
subjective optimization. Provider-side prompt assembly and billed-token counts are
not consistently observable, so the first release cannot truthfully promise exact or
live measurements.

## Decision

- Add `powerkit context audit` as a read-only, deterministic command over known
  PowerKit artifacts.
- Report exact UTF-8 bytes and characters plus clearly labelled token estimates using
  a versioned estimator (`utf8-bytes-v1`, rounded up from four bytes per token).
- Model always-on instructions, discovery metadata, FAST/STANDARD/DEEP execution
  paths, selected skill bodies, references, agent prompts, and platform adapters as
  separate canonical artifact classes.
- Treat an unconfigured platform as not measurable rather than assuming parity with
  another platform.
- Publish stable v1 JSON report and baseline schemas. Baselines contain aggregate
  measurements only, never instruction or skill-body content.
- Make CI enforcement opt-in through `--ci` and configurable warning/failure budgets;
  recommendations remain advisory and never rewrite prompts automatically.
- Keep the auditor out of normal task context. It is a CLI/doctor diagnostic and adds
  no always-on instruction, hook, or auto-routed skill.

## Consequences

- Maintainers can compare releases, inspect platform differences, and block material
  context regressions with reproducible evidence.
- Measurements describe PowerKit-attributable context, not provider-billed tokens or
  the assistant's complete runtime context.
- Estimator changes require a new estimator identifier and incompatible baselines are
  rejected rather than silently compared.
- The first release has no live provider observation and no automatic prompt fixes;
  both would require explicit, platform-specific evidence and additional safety review.
- `powerkit doctor` may run the deterministic audit and print a one-line health result,
  but it does not inject the report into model context or add runtime task overhead.

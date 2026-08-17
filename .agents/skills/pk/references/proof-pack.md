# Proof Pack completion

Read this reference only after a meaningful non-help `pk` task reaches a truthful stopping point. Reuse evidence already produced by the selected workflow; do not rerun broad checks merely to decorate a report.

## Depth policy

- `FAST`: return a compact Completion Brief. Do not generate HTML by default.
- `STANDARD`: generate a Completion Brief and `proof.json`. HTML is automatic for UI, architecture, and migration work, or may be requested explicitly.
- `DEEP`: generate a Completion Brief, `proof.json`, and offline `report.html`.
- `HIGH_RISK`: generate the DEEP outputs, prominent caveats, and distinct independent-verifier evidence. Missing independent evidence keeps the result partially verified.

## One evidence path

The deterministic path is:

```text
repository verification commands
  → canonical execution records
  → proof.json
  → Completion Brief
  → optional report.html
```

Presentation must not set or upgrade verification state. Passing, failure, timeout, and skipped status come from command execution records. Explanatory fields describe the work but never prove that a check ran.

## Task specification

Create a small JSON task specification outside the proof output directory. Use schema version `1` and provide:

- `task`: lowercase stable `id`, human title and summary, workload `depth`, one or more task `types`, implementation state, requested scope, delivered behavior, and meaningful exclusions.
- `changes`: relevant project-relative file paths, change type, component, and human explanation.
- `understand`: only the components, responsibilities, boundaries, and maintenance notes needed tomorrow.
- `preserved`, `caveats`, and concrete `risks`.
- `modules`: only the selected adaptive task types (`feature`, `bug`, `ui`, `architecture`, `migration`, `database`, `security`, `performance`, `dependency`, `review`, `refactor`, or `general`).
- `artifacts`: explicit project-relative evidence files. Mark sensitive artifacts as `sensitive`; they will be hashed but not copied. Normal artifacts are capped at 25 MiB each, 100 per proof, and 100 MiB total.
- `independent_verification_path`: for HIGH_RISK work, a project-relative JSON result whose role is `independent-verifier`, whose task ID and source digest match this proof, whose repository binding is current, and whose non-empty checks agree with its verdict. Keep it under an ignored local evidence path.

Do not put a verification status in explanatory module data. When a UI state, migration check, review criterion, or performance measurement has canonical support, add `evidence_refs` using `verification:<level>` or `artifact:<id>`; unlinked claims are rendered as not verified. Do not include full prompts, environment values, source files, arbitrary logs, personal identity data, or other PII.

## Generation

Run:

```text
powerkit proof create --input <task-spec.json> --broker-trace .ai-powerkit/traces/<task>.json
```

For meaningful broker-routed work, pass the decision trace so the proof is integrity-bound to its task, repository state, compatible depth, and SHA-256 digest. The command replays the deterministic broker inputs and rejects forged fields, a mismatched task/depth, `STOP`, or an unresolved `CHECKPOINT`. A checkpoint requires recorded acknowledgement plus a successful non-dry-run broker launch. The command reads `.ai-powerkit/project.json`, runs the verification levels appropriate to the recorded depth, and writes under `.ai-powerkit/proofs/<task-id>/`. Use `--evidence` only with output created by the PowerKit verification runner; stale imported evidence cannot produce a verified result.

Command output is suppressed by default. Use `--stream-output` only after reviewing the repository-owned executable verification configuration and intentionally accepting terminal disclosure.

For ordinary FAST work, return the short Completion Brief directly and skip durable proof generation unless the user or repository policy asks for machine evidence.

Useful local lifecycle commands are:

```text
powerkit proof list
powerkit proof show <task-id>
powerkit proof show <task-id> --open
powerkit proof delete <task-id> --yes
```

`show` checks source freshness. `--open` refreshes the static report first so changed source receives a stale-proof banner.

## Final response

Lead with outcome, verified behavior, and material caveats. Do not lead with filenames, hashes, model names, workload labels, or PowerKit internals. Link the Proof Report when generated; do not paste it into chat.

If the deterministic tooling is unavailable, still give a truthful Completion Brief and state that the machine proof or report could not be generated. Never manufacture execution evidence.

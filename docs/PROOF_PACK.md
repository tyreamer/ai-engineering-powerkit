# PowerKit Proof Pack

Proof Pack makes completed AI engineering work easy to understand and easy to trust. It is the final presentation layer over PowerKit's existing execution, verification, review, and handoff workflows—not a second verification framework.

## For developers

You generally do nothing. Use `/pk` or the native `$pk` form and describe the task normally. PowerKit chooses the proof depth with the same workload classification it used for the work:

| Depth | Developer experience |
|---|---|
| FAST | A short Completion Brief. No HTML by default. |
| STANDARD | Completion Brief plus local `proof.json`; HTML for visual or structural work. |
| DEEP | Completion Brief, `proof.json`, and an offline HTML Proof Report. |
| HIGH_RISK | DEEP outputs plus explicit caveats and distinct independent-verifier evidence. Missing required evidence prevents a fully verified status. |

The first lines answer whether the work succeeded, what capability changed, and what needs attention. Files, commands, hashes, and artifacts remain available deeper in the report.

## One source of truth

```text
repository verification commands
  → execution records
  → proof.json
  → Completion Brief
  → optional report.html
```

`powerkit/verification.py` owns command execution records. `powerkit/proof.py` validates the task description, snapshots relevant source files, collects artifacts, and derives the outcome. `powerkit/proof_render.py` is read-only presentation code.

Presentation never decides whether a test passed. The status derives from executed records and their provenance. A failed or timed-out check produces failed verification. A skipped required check produces partial or unavailable verification. Imported execution evidence must match the current Git worktree fingerprint.

Required coverage is deterministic: FAST requires targeted evidence when durable proof is requested; STANDARD requires static and targeted; DEEP and HIGH_RISK require static, targeted, broader, and runtime. Narrowing `--levels` is allowed for diagnosis, but missing required coverage cannot produce `VERIFIED`.

## Adaptive proof

The report has a common outcome, scope, orientation, verification, risk, and raw-evidence shell. It adds only the selected task modules:

- feature
- bug
- UI
- architecture
- migration and database
- security
- performance
- dependency decision
- merge review
- refactor
- general

Bug proof separates symptom, contributing condition, root cause, fix, causal link, and regression proof. UI proof prioritizes actual visual artifacts and exercised states. Performance proof renders measurements rather than adjectives. Migration and database proof make compatibility and rollback explicit.

## For coding assistants

Use real execution evidence. Do not turn source inspection into a runtime claim and do not copy an implementation summary into a verifier result. The canonical `/pk` completion reference at `.agents/skills/pk/references/proof-pack.md` defines the small task specification accepted by:

```text
powerkit proof create --input <task-spec.json>
```

Repository verification entries may remain command strings or use an object with `command` and a human `label`. Labels improve the Completion Brief without changing verification semantics.

The task specification carries explanations, relevant change paths, selected task types, important component orientation, caveats, and explicit artifacts. It does not carry a verification status. Status-like module fields are ignored. A UI state, migration check, review criterion, or performance measurement may use `evidence_refs` such as `artifact:desktop-after` or `verification:targeted`; deterministic code resolves those references and otherwise labels the claim `not verified`.

HIGH_RISK independent evidence is a separate JSON file under an ignored local path such as `.ai-powerkit/verification/`. It must declare role `independent-verifier`, the exact task ID, the current repository binding, the source-snapshot digest, a verdict, and at least one canonical check consistent with that verdict. This is procedural provenance, not cryptographic attestation; stale or cross-task verifier files cannot satisfy HIGH_RISK status.

## Local state and lifecycle

Default layout:

```text
.ai-powerkit/proofs/<task-id>/
├── completion.txt
├── proof.json
├── report.html        # DEEP/HIGH_RISK and selected STANDARD work
└── artifacts/         # only explicitly selected, non-sensitive files
```

The output location may be changed with `proof.output_directory` in `.ai-powerkit/project.json`, but it must remain dedicated generated state under `.ai-powerkit/` and may not traverse symlinks. Tracked files are never hidden from freshness checks even if they are placed inside the configured directory.

```text
powerkit proof list
powerkit proof show <task-id>
powerkit proof show <task-id> --open
powerkit proof delete <task-id> --yes
```

`show` recomputes source freshness. `--open` rewrites the static report with the current freshness banner before opening it. Opening an old `report.html` directly cannot query unrelated local source files in a browser, so use `proof show --open` when freshness matters.

Proofs are generated local state, ignored by Git by default, never uploaded, never auto-committed, and not part of the installer ownership manifest. Normal uninstall preserves them; delete a selected proof explicitly when it is no longer needed.

## Privacy and report security

By default Proof Pack never stores:

- command stdout or stderr
- environment values
- prompt history
- complete source files
- arbitrary logs
- sensitive artifacts

It stores exact redacted commands, exit status, duration, timestamp, labels, hashes, and explicitly authored explanations. Sensitive mapping keys and common credential, email, and phone forms are redacted. This pattern filter is defense in depth, not a complete PII classifier: do not put personal identity data into task specifications, labels, filenames, or artifacts. Artifacts marked `sensitive` are hashed and described but not copied. Normal artifacts are limited to 25 MiB each, 100 per proof, and 100 MiB total.

Verification configuration is trusted executable repository code. Proof creation suppresses command output by default so secrets cannot spill into an agent transcript; pass `--stream-output` only after reviewing the commands and when terminal output is intentionally desired. Symlinked verification configuration is rejected.

Every dynamic HTML value is escaped. Reports contain no JavaScript, no remote scripts, no trackers, and no external CDN references. A restrictive Content Security Policy permits only inline CSS and embedded raster images. SVG is not embedded as an image because repository-provided SVG may contain executable content.

## Freshness

The proof records SHA-256 hashes for each relevant changed source file plus the complete non-ignored Git worktree fingerprint. `proof show` compares both, then rechecks copied artifact hashes and the independent-verifier source file. Omitted source changes, replaced artifacts, and reused verifier evidence therefore make the proof stale or fail closed. Previously recorded command evidence also carries the worktree fingerprint, so evidence captured before later repository changes cannot silently verify a newer implementation.

## Schema

`schemas/proof-manifest.schema.json` defines proof schema version 1. Unsupported versions fail without rewriting the manifest. Version 1 is the initial public schema; a future schema change must add an explicit migration or regeneration path rather than silently coercing old evidence.

## Presentation failures

HTML generation status is separate from engineering verification. If rendering fails, `proof.json` and `completion.txt` remain available and retain the true implementation outcome. The CLI reports the presentation failure without changing passed checks into failed engineering work.

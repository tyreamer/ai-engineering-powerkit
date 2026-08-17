# PowerKit Execution Broker

Read after intent, effort, and risk are selected. The broker converts router output into a deterministic resource and safety policy; it does not classify the request itself.

## Normal current-session path

Run the smallest command that describes the selected task:

```text
powerkit broker explain \
  --effort FAST|STANDARD|DEEP \
  --risk NORMAL|ELEVATED|HIGH \
  --platform codex|claude|copilot \
  --surface <active-surface> \
  --control-plane CURRENT_SESSION \
  --compact
```

Surface names:

- Codex: `app`, `cli`, or `cloud`.
- Claude Code: `cli`.
- GitHub Copilot: `ide`, `cli`, `coding-agent`, or `sdk`.

Add only evidence-backed task traits:

```text
READ_ONLY ARCHITECTURE MIGRATION RUNTIME
SECURITY_SENSITIVE AUTHORIZATION PRIVACY SECRETS
PRODUCTION_DATA BILLING PUBLIC_CONTRACT DESTRUCTIVE
EXTERNAL_WRITE DEPENDENCY_CHANGE
```

Translate explicit user constraints without weakening them:

| User intent | Broker constraint |
|---|---|
| plan only | `PLAN_ONLY` |
| no write | `NO_WRITE` |
| no network | `NO_NETWORK` |
| no new dependencies | `NO_DEPENDENCIES` |
| no parallel agents | `NO_PARALLEL` |
| no shell | `NO_SHELL` |
| cost sensitive | `COST_SENSITIVE` |
| latency sensitive | `LATENCY_SENSITIVE` |
| strongest available reasoning | `STRONGEST_REASONING` |
| bounded scope | `BOUNDED_SCOPE` |
| isolation is mandatory | `ISOLATION_REQUIRED` |

Repeat `--trait` and `--constraint` for multiple values. Add concise `--reason` values only when a human asks why; do not send the task text, secrets, or large context through the command.

## Obey the result

- `PROCEED`: use the selected agents, repository scope, permissions, verification, and proof policy.
- `CHECKPOINT`: complete safe preparatory work, then stop at the stated consequential boundary.
- `STOP`: do not continue the unsafe phase. Report the exact unenforceable requirement and the safer launcher/profile/surface needed.
- `one_writer=true`: never create overlapping implementation writers.
- Independent verification is sequentially distinct even when `max_parallel=1`.
- `compatibility_depth=HIGH_RISK` preserves the existing Proof Pack interface while effort and risk remain independent internally.

The compact output is an internal directive. Do not dump it into every user response. Explain only material checkpoints, refusals, or unenforced controls.

Apply every returned `subagent_settings` entry when creating that subagent. Those values are not active-root enforcement. Treat `enforcement_status=NOT_APPLIED` literally.

## Launcher path

When PowerKit owns a supported local client launch, use `powerkit broker launch`; do not manually reconstruct its command. Inspect first with `--dry-run`, acknowledge a stated checkpoint only after the required approval, and pass exactly one task prompt after `--`; arbitrary client flags are not accepted. The launcher transmits the prompt through stdin and disables local client session persistence, but provider retention remains outside PowerKit. Treat `SETTINGS_PASSED` and `APPLICATION_ATTEMPTED` literally: neither proves host acknowledgement, and a launcher or subagent setting does not prove that the active root turn changed.

Use full JSON for automation or trace capture:

```text
powerkit broker explain ... --json
powerkit broker explain ... --trace .ai-powerkit/traces/<task>.json --task-id <task>
```

Observed usage remains empty unless a host emits real telemetry. Requested and estimated fields are not observed facts.

## Capability diagnostics

Use:

```text
powerkit broker capabilities
powerkit broker capabilities --platform codex --surface app --probe
```

`--probe` actively executes bounded version commands from trusted client paths. `VERSION_PROBED` does not prove any permission, network, browser, or subagent behavior. Capability states mean:

- `NATIVE`: the selected surface has a native control at the stated lifecycle.
- `PARTIAL`: native support covers only part of the requested boundary or is surface/model dependent.
- `EMULATED`: PowerKit, a hook, or an outer harness supplies the behavior.
- `UNAVAILABLE`: no credible enforcement path is documented.

## Safe fallback

If the installed PowerKit CLI lacks `broker`, apply the visible effort × risk policy using `workload-router`, preserve all user constraints, and label every host control as behavioral or unknown. Do not claim native enforcement. For HIGH risk, stop at any consequential mutation whose required permission, network, isolation, or checkpoint boundary cannot be verified.

Do not load platform capability manifests into ordinary prompt context. The deterministic CLI reads only the selected platform/surface contract.

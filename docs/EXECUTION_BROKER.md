# Execution Broker

PowerKit's Execution Broker converts workload classification into an explicit execution policy and then negotiates that policy against the selected coding-agent surface. It is the boundary between “this task deserves more rigor” and the concrete controls that actually exist.

The broker is deterministic, offline, and vendor-neutral at its core. Platform model names, flags, profiles, tool semantics, and lifecycle limits live in versioned adapter contracts under `adapters/*/capabilities.json`.

## Why it exists

Prompt instructions can request careful behavior, but they cannot prove that the active host changed its model, reasoning level, sandbox, network boundary, tool set, or turn limit. The broker makes that distinction visible:

```text
request + repository evidence
        ↓
effort × risk classification
        ↓
canonical desired policy
        ↓
selected platform + surface + control plane
        ↓
capability negotiation
        ↓
PROCEED | CHECKPOINT | STOP
        ↓
verification + Proof Pack compatibility depth
```

The broker does not classify the task itself, launch a container platform, choose project architecture, or learn from usage. It does not invent a host setting when no credible enforcement path exists. Its optional local launcher applies only the documented Codex and Claude CLI settings it can represent.

## Independent policy axes

Effort and risk are deliberately separate.

| Effort | Resource intent | Typical defaults |
|---|---|---|
| `FAST` | Finish a clear, bounded task cheaply | Economy tier, low reasoning, one agent, minimal context, targeted verification |
| `STANDARD` | Handle normal engineering work | Balanced tier, medium reasoning, up to two agents, focused context, standard verification |
| `DEEP` | Investigate difficult or cross-cutting work | Strong tier, high reasoning, up to four agents, expanded context, deep verification and independent review |

| Risk | Safety intent | Typical additions |
|---|---|---|
| `NORMAL` | Ordinary reversible engineering | Task-scoped tools and writes |
| `ELEVATED` | Material migration, dependency, or external-effect concerns | Stronger verification and checkpoints at consequential boundaries |
| `HIGH` | Security, authorization, privacy, production data, billing, public contracts, or destructive behavior | Narrow writes, least privilege, deep/security verification, checkpoint, preferred isolation, independent proof |

Examples:

- A one-line authorization guard can be `FAST × HIGH`: low reasoning remains appropriate, while security verification and high-risk proof become mandatory.
- A large read-only architecture audit can be `DEEP × NORMAL`: extensive investigation is useful without implying write permissions or destructive risk.
- A cross-service authentication migration is normally `DEEP × HIGH`.

For compatibility with the existing Proof Pack, effective `HIGH` risk maps to the public `HIGH_RISK` proof depth. Other work maps proof compatibility to `FAST`, `STANDARD`, or `DEEP` effort.

## Canonical policy

The desired policy covers:

- intelligence: portable model tier, reasoning level, and model-upgrade permission;
- agents: maximum parallelism, distinct roles, one-writer invariant, independent verifier, and adversarial critic;
- context: PowerKit budget class and repository scope;
- permissions: tools, filesystem writes, shell, network, MCP, external writes, destructive actions, and dependency changes;
- verification: depth, runtime checks, security checks, and independent verification;
- safety: checkpoints, isolation, and rollback expectations;
- limits: maximum workflow iterations;
- proof: presentation depth and compatibility depth;
- telemetry: requested controls, relative cost and latency estimates, compact-policy overhead, and empty observed fields until a host supplies evidence.

Portable tiers such as `ECONOMY`, `BALANCED`, `STRONG`, and `MAXIMUM` are intentionally not model identifiers. Model identifiers belong only in platform adapter translations or project adapter overrides.

### Precedence

Resolution order is deterministic:

1. Start with the selected effort defaults.
2. Apply project cost and latency preferences.
3. Elevate risk from consequence-bearing task traits when necessary.
4. Apply risk safety floors; cost optimization never reduces required verification, permission boundaries, checkpoints, or proof.
5. Preserve explicit user constraints. A constraint always wins over a more permissive default.
6. Negotiate every requested control against the selected platform surface and lifecycle.

The broker never silently lowers `HIGH` risk. Task traits can raise risk, but they do not automatically force maximum model strength or parallelism.

## Project policy

Projects may commit a top-level `execution_policy` in `.ai-powerkit/project.json`:

```json
{
  "execution_policy": {
    "cost_preference": "BALANCED",
    "latency_preference": "BALANCED",
    "max_parallel_agents": 4,
    "allow_model_upgrade": true,
    "allow_network": "WHEN_REQUIRED",
    "high_risk_requires_checkpoint": true,
    "iteration_limits": {
      "FAST": 4,
      "STANDARD": 8,
      "DEEP": 16
    },
    "adapter_overrides": {
      "copilot": {
        "model_tiers": {
          "BALANCED": "<account-approved-model-id>"
        }
      }
    }
  }
}
```

Accepted cost values are `ECONOMY`, `BALANCED`, and `QUALITY`. Accepted latency values are `FASTEST`, `BALANCED`, and `QUALITY`. Network policy is `NEVER`, `WHEN_REQUIRED`, or `ALLOW`.

Adapter overrides are the explicit escape hatch for model catalogs that differ by account, organization policy, region, or client version. Shared canonical policy never pins those names.

## Task traits and constraints

Traits are evidence-backed facts about the work. They may elevate risk or select specialist roles:

```text
READ_ONLY ARCHITECTURE MIGRATION RUNTIME
SECURITY_SENSITIVE AUTHORIZATION PRIVACY SECRETS
PRODUCTION_DATA BILLING PUBLIC_CONTRACT DESTRUCTIVE
EXTERNAL_WRITE DEPENDENCY_CHANGE
```

Constraints are explicit user or project limits:

```text
PLAN_ONLY NO_WRITE NO_NETWORK NO_DEPENDENCIES NO_PARALLEL NO_SHELL
COST_SENSITIVE LATENCY_SENSITIVE STRONGEST_REASONING BOUNDED_SCOPE
ISOLATION_REQUIRED
```

`PLAN_ONLY` and `NO_WRITE` force read-only execution. `NO_NETWORK` also denies MCP use because MCP may cross a network boundary. `NO_PARALLEL` limits concurrency to one but does not erase the requirement for a logically independent verifier; verification can run sequentially.

## Capability negotiation

Every control resolves to one of four states:

| State | Meaning |
|---|---|
| `NATIVE` | The selected surface exposes a documented host control for the stated lifecycle. |
| `PARTIAL` | Native support covers only part of the requested boundary or varies by model, version, transport, or surface. |
| `EMULATED` | PowerKit, a trusted hook, or an outer launcher supplies the behavior; the host does not enforce the canonical control directly. |
| `UNAVAILABLE` | No credible enforcement path is documented for this surface and lifecycle. |

Each result separates `platform_support`, lifecycle `availability_state`, negotiated `state`, setting `application`, and `enforcement_status`. Availability is not proof of activation: ordinary `explain` output reports `NOT_APPLIED`. A completed broker-owned launch reports native settings as `SETTINGS_PASSED` and the corresponding control as `APPLICATION_ATTEMPTED`; client success is still not host acknowledgement that every setting achieved its intended effect. An advertised native capability is downgraded to `PARTIAL` when the requested value has no concrete translation.

### Control planes

`CURRENT_SESSION` describes what can honestly be changed during the active task. `LAUNCHER` describes controls that PowerKit can apply only when it owns creation of a new host task or subagent.

This distinction prevents a common false claim: a model or sandbox flag that works at launch does not retroactively change the active root turn. The broker returns launcher-native settings only when `--control-plane LAUNCHER` is selected.

### Decisions

- `PROCEED`: the selected surface is adequate for the task's required boundary.
- `CHECKPOINT`: safe preparatory work may continue, but a human or enforced tool boundary is required before the consequential phase.
- `STOP`: an explicit requirement such as proven no-network or required isolation cannot be enforced. Select a stronger launcher profile or surface before continuing.

All non-native controls remain visible as caveats. High-risk work receives a checkpoint when filesystem, network, or checkpoint enforcement is incomplete even if execution is not categorically unsafe.

## CLI diagnostics

Explain the selected policy:

```bash
powerkit broker explain \
  --effort DEEP \
  --risk ELEVATED \
  --platform claude \
  --surface cli \
  --trait MIGRATION \
  --constraint NO_PARALLEL
```

Use `--compact` for the internal agent directive and `--json` for the stable machine contract. The compact form includes every permission and safety boundary plus applicable subagent settings; it is intentionally larger than the original resource-only form. `STOP` returns exit code 3, `CHECKPOINT` returns exit code 4, and malformed input or configuration returns exit code 2.

Apply supported settings while starting a trusted local Codex or Claude client:

```bash
powerkit broker launch \
  --effort STANDARD \
  --risk NORMAL \
  --platform codex \
  --surface cli \
  --dry-run \
  -- "Inspect the affected subsystem and report the next safe step."
```

Remove `--dry-run` to execute. The launcher accepts exactly one task prompt after `--`; arbitrary client flags are rejected. It sends the broker directive and prompt through stdin, uses an argument vector without a shell, disables local client session persistence (`--ephemeral` for Codex and `--no-session-persistence` for Claude), and never records prompt contents. Codex ignores user configuration for the launched task; Claude loads no user/project/local settings, discovered MCP servers, slash-command skills, or browser integration. Repository instructions remain part of the coding task, so the target repository must still be trusted. Provider-side request or service retention remains outside PowerKit's control. A `CHECKPOINT` launch requires `--ack-checkpoint`, and that resolution is included in the child directive while all `DENY` constraints remain in force. Copilot has no local launcher adapter because its surfaces require host-specific ownership.

Launcher client selection is a filesystem-location allowlist plus a self-reported platform/version check. It is not binary signature, hash, or provenance verification; operators remain responsible for the integrity of the installed client at those paths. Public launch records use a platform label rather than persisting a user-specific absolute executable path.

Inspect platform capability contracts:

```bash
powerkit broker capabilities
powerkit broker capabilities --platform codex --surface app
powerkit broker capabilities --platform copilot --surface ide --json
powerkit broker capabilities --probe
```

`--probe` actively executes a version command from a small path allowlist in a neutral working directory with a minimal environment, a timeout, and bounded output. `VERSION_PROBED` proves only that the client is locally callable. It does not validate client provenance or any tool, permission, network, browser, model, or subagent behavior.

Persist a local decision trace:

```bash
powerkit broker explain ... \
  --trace .ai-powerkit/traces/task-id.json \
  --task-id task-id \
  --json
```

Trace paths are confined to `.ai-powerkit/traces/*.json`, reject traversal and symlinks, require the proof task identity, are written mode `0600`, and are ignored by Git by default. Reasons are limited to five content-light, redacted entries of 200 characters each and reject control characters. Do not put task text, prompts, source content, secrets, or environment variables in `--reason`. Retain traces only as long as the associated local proof or audit requires them; delete both the trace and bound proof when that evidence is no longer needed.

Bind a Proof Pack to the exact broker decision:

```bash
powerkit proof create \
  --input .ai-powerkit/task-spec.json \
  --broker-trace .ai-powerkit/traces/task-id.json
```

The proof integrity-binds the verified trace path and SHA-256 digest to the task and current repository state. Binding deterministically replays the recorded inputs and rejects forged policy fields, a task mismatch, a compatibility-depth mismatch, `STOP`, or an unresolved `CHECKPOINT`. A checkpoint is accepted only when a non-dry-run broker launch records acknowledgement, client success, and settings passed. This is an integrity check, not a signature or independent attestation.

## Capability summary

The following tables show documented surface-level support from contracts last verified on 2026-08-17. They are summaries, not substitutes for the current-session versus launcher records in each manifest.

### Codex

| Control | App | CLI | Cloud |
|---|---|---|---|
| Model selection | NATIVE | NATIVE | UNAVAILABLE |
| Reasoning effort | NATIVE | NATIVE | PARTIAL |
| Parallel agents | NATIVE | NATIVE | NATIVE |
| Agent roles | NATIVE | NATIVE | NATIVE |
| Context budget | PARTIAL | PARTIAL | PARTIAL |
| Tool restriction | PARTIAL | PARTIAL | PARTIAL |
| Filesystem scope | NATIVE | NATIVE | NATIVE |
| Network restriction | PARTIAL | PARTIAL | PARTIAL |
| Shell restriction | NATIVE | NATIVE | NATIVE |
| Maximum iterations | EMULATED | EMULATED | EMULATED |
| Checkpoints | PARTIAL | PARTIAL | PARTIAL |
| Execution isolation | PARTIAL | PARTIAL | NATIVE |
| Runtime/browser | PARTIAL | PARTIAL | UNAVAILABLE |
| Usage telemetry | PARTIAL | PARTIAL | PARTIAL |
| External-write gating | PARTIAL | PARTIAL | PARTIAL |
| MCP restriction | NATIVE | NATIVE | NATIVE |

Codex model and reasoning controls are native for a new root turn or subagent, but only partial for an already-running root turn. Local filesystem sandboxing is stronger than the combined network boundary: command networking, web search, apps, MCP, browser traffic, and model traffic are separate transports. No stable client maximum-turn setting is claimed.

### Claude Code

| Control | CLI |
|---|---|
| Model selection | NATIVE |
| Reasoning effort | PARTIAL |
| Parallel agents | NATIVE |
| Agent roles | NATIVE |
| Context budget | PARTIAL |
| Tool restriction | NATIVE |
| Filesystem scope | PARTIAL |
| Network restriction | PARTIAL |
| Shell restriction | NATIVE |
| Maximum iterations | PARTIAL |
| Checkpoints | PARTIAL |
| Execution isolation | PARTIAL |
| Runtime/browser | PARTIAL |
| Usage telemetry | PARTIAL |
| External-write gating | PARTIAL |
| MCP restriction | NATIVE |

Claude Code exposes useful launcher controls including model, effort, tools, denied tools, permission mode, strict MCP configuration, worktrees, agent definitions, budget caps, and maximum turns. They still compose rather than forming one universal boundary. In particular, `allowedTools` preapproves matching tools; it is not an availability allowlist. Use the tool-availability control plus explicit deny rules when a real restriction is required.

### GitHub Copilot

| Control | CLI | IDE | Coding agent | SDK |
|---|---|---|---|---|
| Model selection | NATIVE | PARTIAL | NATIVE | NATIVE |
| Reasoning effort | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| Parallel agents | PARTIAL | PARTIAL | UNAVAILABLE | PARTIAL |
| Agent roles | NATIVE | NATIVE | NATIVE | NATIVE |
| Context budget | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| Tool restriction | NATIVE | NATIVE | NATIVE | NATIVE |
| Filesystem scope | PARTIAL | UNAVAILABLE | PARTIAL | PARTIAL |
| Network restriction | PARTIAL | UNAVAILABLE | PARTIAL | PARTIAL |
| Shell restriction | NATIVE | NATIVE | NATIVE | NATIVE |
| Maximum iterations | EMULATED | EMULATED | EMULATED | EMULATED |
| Checkpoints | PARTIAL | PARTIAL | PARTIAL | NATIVE |
| Execution isolation | PARTIAL | UNAVAILABLE | NATIVE | PARTIAL |
| Runtime/browser | PARTIAL | PARTIAL | NATIVE | PARTIAL |
| Usage telemetry | PARTIAL | PARTIAL | PARTIAL | NATIVE |
| External-write gating | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| MCP restriction | PARTIAL | PARTIAL | PARTIAL | NATIVE |

Copilot is a family of surfaces, not one execution runtime. The IDE offers the weakest enforceable filesystem and network boundary. The coding agent uses a hosted ephemeral environment but firewall and external-service exceptions still matter. The SDK gives an application more ownership of checkpoints, MCP, and telemetry, yet application code must implement those controls correctly. Account model catalogs vary, so the shared adapter contains no guessed model identifier.

The machine-readable contracts and their primary documentation links are:

- [`adapters/codex/capabilities.json`](../adapters/codex/capabilities.json)
- [`adapters/claude/capabilities.json`](../adapters/claude/capabilities.json)
- [`adapters/copilot/capabilities.json`](../adapters/copilot/capabilities.json)

## Integration with `/pk`

The `pk` skill performs request preflight and workload routing first. It then invokes the compact broker path using the active platform and surface, preserves the broker decision, and loads specialist workflows only as needed.

The full capability matrices are never injected into ordinary task context. The Context Budget Auditor separately reports the whole selected path and the generated compact directive. The safety-complete compact form is currently 126–163 estimated tokens across representative normal paths and platforms. The measured whole-path increase versus the checked-in pre-broker baseline is 761–798 estimated tokens; this includes static routing/instruction changes as well as generated policy. All modeled paths remain under configured budgets but currently sit in the auditor's `watch` band. The detailed broker reference loads only when translation, launcher controls, diagnostics, or fallback behavior needs clarification.

Proof Pack can bind the broker's compatibility depth and trace digest through `--broker-trace`. Requested and estimated telemetry can appear in diagnostics; `observed` remains empty unless real host instrumentation supplies evidence.

## Validation and maintenance

`python3 tools/validate.py` verifies:

- every platform surface covers all broker controls;
- all support states, lifecycle records, sources, and translations are structurally valid;
- the distribution manifest, project template, command manifest, CLI, and schema are wired consistently;
- routing cases carry independent effort and risk;
- at least seven representative broker dogfood cases remain versioned;
- vendor model identifiers do not leak into canonical broker policy.

Unit and integration tests cover policy resolution, safety floors, user overrides, lifecycle negotiation, stop/checkpoint decisions, schema conformance, CLI formats and exits, trace confinement, probes, context overhead, installation, and dogfood cases.

When a client surface changes, update only evidence-backed adapter records, refresh `last_verified`, cite the current primary source in the manifest, run the full test suite, and record what was structurally versus live validated.

## Current limitations

- The broker cannot retrofit launcher-only settings into an active root turn. It exposes subagent settings to `/pk` and applies supported root settings only through `broker launch`.
- Capability-contract load failures degrade explicitly to behavioral fallback for the current session. Read-only work may proceed with caveats, mutation requires a checkpoint, and a local launcher stops because it cannot safely construct or validate settings without its contract.
- Static capability documentation can become stale as clients change. `last_verified` and local probes reduce ambiguity but do not replace behavioral tests.
- Relative cost and latency are ordinal projections, not prices, billing estimates, or service-level guarantees.
- Provider context-window hard limits and exact token counts remain platform/model dependent.
- No universal transport-level no-network switch is assumed across shell, browser, web, apps, MCP, and model traffic.
- Maximum iterations are often workflow or outer-harness controls rather than host-native hard stops.
- Observed usage is not fabricated. It remains empty without trustworthy host telemetry.
- Local persistence flags do not control provider-side retention, and client location/version checks do not attest binary provenance.
- The dogfood corpus proves deterministic allocation, not that FAST/standard/deep outcome quality or resource savings outweigh the measured context overhead; that comparative outcome eval remains future work.
- The broker is not a sandbox, container orchestrator, adaptive optimizer, or autonomous policy learner.

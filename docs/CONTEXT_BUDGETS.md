# Context budgets

PowerKit's progressive-disclosure promise is measurable:

```text
always-on instructions
        ↓
skill discovery metadata
        ↓
selected SKILL.md
        ↓
references only at the decision that needs them
        ↓
isolated agent instructions only for that agent
```

Run the offline audit in the current project:

```bash
powerkit context audit
```

Useful deterministic variants are:

```bash
powerkit context audit --target .
powerkit context audit --platform codex
powerkit context audit --platform all
powerkit context audit --json
powerkit context audit --ci
powerkit context audit --write-baseline
```

The terminal report is for quick decisions. `--json` returns the stable schema used by CI and other tooling. The contracts are published as [`context-audit-v1.schema.json`](../schemas/context-audit-v1.schema.json) and [`context-baseline-v1.schema.json`](../schemas/context-baseline-v1.schema.json).

## What is measured

The canonical artifact model separates:

- Always-on PowerKit instruction files or managed instruction blocks.
- Skill discovery metadata: the skill name and description, not the full body.
- Full selected skill bodies.
- Skill references.
- Specialized agent instructions, reported outside the primary-agent path.
- Platform adapter overhead.
- Generated task context when real evidence eventually makes it available.

The auditor uses `catalog.json`, `.ai-powerkit/project.json`, `.ai-powerkit/install-manifest.json`, managed ownership metadata, and known platform destinations. Distribution checkouts must carry PowerKit's source identity. Installed audits verify profile selection plus every expected instruction, skill, agent, and command-adapter inventory entry; corrupt or drifted state fails closed instead of falling back to optimistic counts. Schema-v1 installation inventories remain readable through their validated legacy file list. The auditor does not crawl dependencies, build output, caches, `.git`, or unrelated source code.

The modeled FAST, STANDARD, and DEEP paths use the installed `pk` command manifest and current progressive-disclosure rules. A missing skill in a minimal profile makes the affected path `partial` instead of fabricating a total.

## Estimated versus observed

Static inspection answers what PowerKit could or should load. It does not prove what a client actually placed in a model request.

The built-in estimator uses a deterministic UTF-8 byte approximation and labels every result `estimated`. It works offline with the Python standard library. No host/model tokenizer is assumed because PowerKit usually cannot prove which tokenizer the active surface used.

An exact or compatible tokenizer can be added behind the `TokenEstimator` boundary when the active platform supplies trustworthy model information. Baselines record the estimator ID; incompatible estimators are never compared as if they were equivalent.

Until client instrumentation exists, every platform reports observed context as unsupported. PowerKit never turns a static estimate into a claim about provider-billed input. A future Flight Recorder can supply content-free observed loading and generated-context measurements through a separate evidence path.

## Platform models

- Codex: `AGENTS.md` or the managed user instruction block, `.agents/skills`, and isolated `.codex/agents` definitions.
- Claude Code: `CLAUDE.md` or the managed user instruction block, `.claude/skills`, and isolated `.claude/agents` definitions.
- GitHub Copilot: `.github/copilot-instructions.md`, `.agents/skills`, isolated Copilot agents, and the project-scoped `pk` prompt adapter when present.

Platform values may be equal when the canonical content is equal. Copilot's selected `pk` path includes its prompt-file adapter; Codex and Claude do not. A user-scope Copilot install has no PowerKit-managed always-on instruction file, so the auditor reports zero rather than inventing one.

## Budget configuration

Projects can override release defaults in `.ai-powerkit/project.json`:

```json
{
  "powerkit": {
    "context_budgets": {
      "policy": "warn",
      "always_on_tokens": 900,
      "discovery_tokens": 2100,
      "fast_path_tokens": 8000,
      "standard_path_tokens": 12000,
      "deep_path_tokens": 15000,
      "regression_percent": 20,
      "regression_tokens": 250
    }
  }
}
```

These limits were derived from the PowerKit v0.2 static baseline with practical headroom. They are toolkit budgets, not model context-window limits.

Policies are:

- `warn`: show budget status without making an interactive audit fail.
- `fail_ci`: return nonzero for a configured breach or meaningful regression.
- `disabled`: retain measurements but skip budget enforcement.

Passing `--ci` explicitly enables failure behavior unless the policy is `disabled`.

## Baselines and CI

Write a checked-in project or release baseline:

```bash
powerkit context audit --platform all --write-baseline
git add .ai-powerkit/context-baseline.json
```

Then enforce it:

```bash
powerkit context audit --platform all --ci
```

The baseline contains only static aggregate metrics and estimator metadata. It does not contain prompts, conversations, source code, environment variables, or machine-specific runtime traces.

An explicitly named missing baseline, malformed metric, foreign platform entry, empty measurement set, or baseline lacking currently measurable CI metrics cannot produce a green comparison. A baseline produced by a different estimator is shown as incompatible and fails enforced CI instead of silently disabling comparison. Partial profiles may omit only path metrics that are genuinely not measurable.

CI focuses on always-on, discovery, FAST, and STANDARD regressions. A change is meaningful only when it crosses both the configured token and percentage thresholds. Growing a rarely selected skill does not fail an unrelated always-on or discovery regression check.

## Recommendations

Each finding includes what is expensive, why it matters, a suggested architectural change, estimated impact, confidence, evidence, and affected paths. Current deterministic classes cover:

- Oversized always-on instructions and discovery descriptions.
- Large skill bodies that have no progressive reference boundary.
- Large references directed into common paths too early.
- Exact duplicated procedure while protecting short or safety-sensitive invariants.
- Possible cross-skill routing overlap without automatically recommending a merge.
- Discovery metadata growth.
- Oversized generic agent prompts that exceed a role-specific context boundary.
- Repeated platform-agent adapters, reported separately from common-request context.

Recommendations are ranked as highest impact, worth doing, or minor cleanup. The first release does not auto-rewrite human-authored instructions. Every prompt-content change requires review because token reduction is not allowed to weaken activation boundaries, safety, correctness, completion criteria, or platform reliability.

Prefer architectural movement over prompt minification:

```text
always-on → selected skill
selected skill → conditional reference
prose rule → deterministic tool
duplicate procedure → canonical source
```

## Doctor and normal runtime

`powerkit doctor` shows only a one-line context-budget status and points to the full audit when needed. It does not dump findings.

The auditor adds no skill, always-on policy, hook, or automatic audit to ordinary `$pk`/`/pk` tasks. It runs only when requested through the CLI, doctor, or CI. The already-loaded compact `pk` routing reference directs context questions to deterministic audit evidence without adding a discovery entry; that reference remains smaller than it was before this release.

## Safety and privacy

The static auditor treats every inspected string as untrusted data. It reads only known PowerKit files and manifest-confined paths, rejects path traversal and symlinked context roots, tolerates malformed UTF-8 without execution, strips terminal control characters from labels, and never imports consumer modules or runs project commands.

Machine output contains counts, categories, paths, discovery descriptions, and recommendations. It excludes full instruction and skill bodies. HTML output is intentionally not part of the first release, avoiding another rendering and injection surface until scale proves it necessary.

## Current limitations

- Actual host loading and activation rates require live-client instrumentation.
- Total provider input includes non-PowerKit material outside this tool's scope.
- Generated repository maps, task contracts, plans, handoffs, and repeated cross-agent packets are unknown without observed traces.
- Exact token counts remain model/tokenizer dependent.
- Dead-context confidence is limited without routing or activation telemetry.

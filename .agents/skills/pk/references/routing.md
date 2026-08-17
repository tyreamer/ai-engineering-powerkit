# PowerKit command routing

Read after a non-help `pk` invocation. Select intent and depth without replacing selected skills.

## Selection order

1. Use an explicit task mode other than `deep` as the primary intent.
2. Otherwise infer one intent from outcome, evidence, and repository state. `deep` sets minimum depth, not intent.
3. Select workload depth independently.
4. Add skills only for concrete risk or evidence.

## Automatic intent signals

| Intent | Strong signals | Avoid |
|---|---|---|
| `local_change` | narrow, reversible edit | architecture or migration workflow |
| `feature` | new end-to-end capability or product outcome | treating a broad outcome as one-file work |
| `bug` | failure, regression, expected versus actual behavior | patching before discriminating evidence |
| `review` | challenge completed work or a merge claim | modifying production code on the first pass |
| `resume` | interrupted, stale, or uncertain work | trusting summaries over repository truth |
| `architecture` | migration, system boundary, public contract, or security boundary | big-bang change without compatibility and rollback |
| `ui` | screenshot, mockup, interaction, or accessibility outcome | inventing behavior from a happy-path image |
| `dependency` | package, SDK, model, service, or build-versus-buy | adoption before proving the capability gap |
| `research` | evidence requested without writes | silently turning analysis into implementation |

Keep one primary intent; add secondary workflows only for concrete risk.

## Deterministic context audit

For PowerKit context or token questions, run `powerkit context audit`. Use its report as evidence; do not invent counts by eyeballing Markdown.

## Workload depth

- **FAST** — clear, low-risk, reversible local work: inspect the owner, make the smallest authorized change, and run targeted proof. Avoid task contracts, broad maps, migrations, or adversarial review unless risk changes.
- **STANDARD** — ordinary multi-file features and reproducible bugs: compact contract, relevant path map, one writer, affected-scope verification, and diff review.
- **DEEP** — cross-cutting work, difficult bugs, architecture, or migration: impact analysis, explicit planning, bounded read-only investigation where useful, broader verification, and criticism.
- **HIGH_RISK** — security, privacy, authorization, critical data, destructive migration, public contracts, money, or irreversible actions: add the relevant security, compatibility, rollback, and adversarial safeguards. Urgency never lowers them.

## Constraint invariants

- `plan-only` permits inspection and planning, never implementation.
- `no-write` permits read-only diagnosis or review, never mutation.
- Narrow scope and dependency limits survive routing unchanged.
- When runtime proof is unavailable, state that limitation instead of substituting a unit-test claim.

## Conditional composition detail

After intent and depth are known, read [modes.md](modes.md) only when an explicit mode, STANDARD/DEEP composition, or constraint recipe needs it. A normal automatic FAST request stops here.

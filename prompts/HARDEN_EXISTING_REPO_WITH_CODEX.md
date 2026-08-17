# Harden the Existing AI Engineering PowerKit Repository

Act as the maintainer of this repository. Do not rebuild it blindly.

## Objective

Audit the current repository against its stated architecture and turn it into a dependable, portable toolkit for expert AI-assisted engineering.

## First pass: evidence

Use independent read-heavy agents where available:

- One agent maps the canonical skills, catalog, installer, tests, and docs.
- One agent checks Codex compatibility against current official documentation.
- One agent checks Claude Code compatibility against current official documentation.
- One agent checks GitHub Copilot compatibility against current official documentation.
- One critic identifies routing collisions, security risks, placeholder behavior, and claims not proven by tests.

Require concise evidence packets with exact files and authoritative sources. Keep the main thread for synthesis.

## Audit questions

- Does every skill solve one repeated workflow?
- Are descriptions specific enough to route correctly and different from neighboring skills?
- Do positive and negative eval cases represent real ambiguity?
- Is `.agents/skills` the only canonical skill source?
- Are platform copies generated or installed rather than manually drifting?
- Are subagents narrow, permission-conscious, and single-writer by default?
- Are hooks deterministic, opt-in, and safe for an untrusted cloned repository?
- Does the installer preserve existing user content and back up changes?
- Can it update an existing managed installation safely?
- Does validation catch malformed and conflicting customizations?
- Do docs accurately match the current 2026 platform behavior?
- Are there meaningful automated tests, not only syntax checks?
- Is every completion claim backed by command output?

## Implementation

Create a prioritized plan from actual findings. Implement the highest-value gaps in vertical slices.

Do not:

- Add more skills merely to increase the count.
- Add broad abstractions without current consumers.
- Hard-code model names into shared behavior.
- Automatically enable repository hooks.
- Add dependencies when the standard library is enough.
- weaken tests to make validation pass.
- rewrite working files unrelated to the findings.

## Required verification

Run:

- the repository validator
- all unit tests
- hook self-tests
- an installer dry run against a temporary repository
- an actual temporary installation for each supported platform adapter
- package creation
- archive inspection

Then run an independent implementation critic and anti-slop review over the final diff.

## Handoff

Report:

- Material findings and fixes.
- Exact commands and results.
- Compatibility assumptions that remain unverified in live clients.
- Security decisions.
- Version changes.
- Recommended next release slice.

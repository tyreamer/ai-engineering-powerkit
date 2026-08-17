# AI Engineering PowerKit

### Your coding assistant can write code. PowerKit makes it earn “done.”

**PowerKit is a portable engineering harness for Codex, Claude Code, and GitHub Copilot.**

It gives coding assistants something the model alone does not have:

**a disciplined way to work.**

**PowerKit knows when to spend more.** Small changes stay fast. Hard problems can receive deeper reasoning, focused investigators, broader verification, and stronger proof. High-risk work receives tighter permissions and independent checks instead of merely receiving more compute.

Most coding agents can produce impressive code. They can also start too early, guess when they should inspect, chase the first plausible bug, widen scope without permission, trust their own implementation, and declare victory before the work is actually proven.

PowerKit changes the workflow around the model.

```text
YOU
 │
 │  normal language
 ▼
pk skill
 │
 ├─ understand the request
 ├─ inspect the repository
 ├─ recover existing context
 ├─ choose effort and risk independently
 ├─ negotiate real host capabilities
 ├─ preserve your constraints
 ├─ use specialized skills when needed
 ├─ implement within bounds
 ├─ verify independently
 └─ challenge the result before calling it done
```

**You bring the intent. PowerKit brings the engineering discipline.**

When the agent says it is done, **PowerKit shows you what you now own, how it works, and how it was proven.** Its Proof Pack starts with a concise Completion Brief, preserves machine evidence locally, and adds an offline visual report when the work is complex enough to benefit from one.

---

# Give it to your coding assistant

You do not need to learn PowerKit before using it.

Tell your coding assistant:

```text
Install AI Engineering PowerKit into this repository:

https://github.com/tyreamer/ai-engineering-powerkit

Follow BOOTSTRAP.md, preserve existing project configuration,
verify the installation, and tell me when PowerKit is ready.
```

PowerKit v0.4.0 provides a machine-readable bootstrap contract and deterministic installation tooling so the assistant can configure the repository from a pinned release instead of manually recreating skills and agent files.

Once installed, explicitly invoke the `pk` skill and describe the task. Native syntax depends on the host:

- Codex can use an explicit skill invocation such as `$pk` on supported surfaces.
- Claude Code commonly exposes installed skills as slash commands such as `/pk`.
- GitHub Copilot invocation varies by surface; use `/pk` only where prompt commands are supported, otherwise select or invoke the installed `pk` skill through the native mechanism.

The installing assistant should report the exact invocation supported by its active client.

---

# Stop engineering prompts

PowerKit is built around a simple premise:

**The developer should spend less time telling the AI how to work.**

You should be able to describe the outcome, constraints, and decisions that actually matter.

PowerKit handles the rest of the execution discipline.

That includes knowing when to:

* just make the small change
* inspect more of the repository first
* recover context from previous work
* ask you a genuinely blocking question
* investigate multiple hypotheses
* plan a vertical slice
* bring in a specialized agent
* perform deeper architecture analysis
* increase verification because the change is risky
* challenge an implementation instead of trusting it

The goal is not a bigger prompt.

The goal is **better engineering with less prompting**.

---

# One command. Different levels of force.

The `pk` skill routes the request based on what the work actually requires.

A narrow change should stay narrow.

A difficult migration should not be treated like a text edit.

A security-sensitive change should receive more scrutiny than either.

PowerKit classifies two independent axes:

```text
EFFORT: FAST | STANDARD | DEEP
RISK:   NORMAL | ELEVATED | HIGH
```

Effort controls resources: model tier, reasoning, context, agents, iterations, and workflow depth. Risk controls permissions, checkpoints, isolation, rollback, verification, and proof. A small security fix can therefore be `FAST × HIGH`; a broad read-only architecture study can be `DEEP × NORMAL`. `HIGH_RISK` remains the public Proof Pack compatibility depth for high-risk work.

The Execution Broker turns that classification into a deterministic desired policy, negotiates it against a versioned Codex, Claude Code, or GitHub Copilot capability contract, and returns `PROCEED`, `CHECKPOINT`, or `STOP`. Native host controls, PowerKit emulation, behavioral guidance, and unavailable enforcement are reported separately—PowerKit does not claim that a prompt changed the active model or sandbox.

```bash
powerkit broker explain --effort STANDARD --risk ELEVATED --platform codex
powerkit broker capabilities --platform codex --surface app --probe
powerkit broker launch --effort STANDARD --risk NORMAL --platform codex --surface cli --dry-run -- "Inspect this subsystem."
```

The optional broker-owned launcher is intentionally limited to validated local Codex and Claude Code CLI versions. It sends the task over stdin, disables local client session persistence, and records settings as passed or application attempted rather than claiming the remote host acknowledged them. Copilot currently uses capability negotiation only; there is no PowerKit-owned local Copilot launcher.

Parallel read-only investigation can support deep or high-risk work, but overlapping implementation keeps one writer. See [Execution Broker](docs/EXECUTION_BROKER.md).

The explicit `pk` routes currently implemented are:

| Command | Use it when |
|---|---|
| `/pk` or `$pk` | Let PowerKit choose the smallest safe route |
| `pk feature` | Build meaningful functionality |
| `pk bug` | Find the actual cause before fixing |
| `pk review` | Challenge work before merge |
| `pk resume` | Recover the real state of interrupted work |
| `pk architecture` | Design or migrate boundaries safely |
| `pk ui` | Implement or improve UI from evidence |
| `pk dependency` | Evaluate a package, service, model, or vendor |
| `pk deep` | Set a minimum of deep investigation and verification |
| `pk help` | Show the concise command reference |

Invocation punctuation is platform-specific. The route names and workflow intent are portable.

---

# What PowerKit changes

## It looks before it asks

Coding assistants often ask questions the repository can already answer.

PowerKit pushes the agent to inspect the code, configuration, tests, documentation, decisions, and current state before sending work back to you.

Questions are reserved for decisions that actually require a human.

---

## It separates facts from guesses

Not every missing detail is ambiguity.

PowerKit distinguishes between:

**Evidence**

The repository or supplied context supports the decision.

**Safe defaults**

The decision is conventional, reversible, and unlikely to change the outcome.

**Material assumptions**

The choice could meaningfully change architecture, security, data, contracts, product behavior, cost, or irreversible work.

Only the last category should normally stop execution.

---

## It does not let the first bug theory win

A plausible explanation is not a root cause.

The debugging workflow emphasizes reproduction, competing hypotheses, evidence, falsification, the smallest justified fix, and regression proof.

---

## It does not equate generated code with finished work

Writing the implementation is one stage.

PowerKit can independently look for:

* code that was added but never wired in
* placeholder or fake integrations
* swallowed errors
* tests that only prove mocks
* dead abstractions
* missing failure paths
* contract regressions
* security or privacy mistakes
* hidden scope expansion
* TODOs inside supposedly completed work
* completion claims unsupported by evidence

“Done” should mean more than “the agent stopped editing files.”

---

## It scales effort instead of maximizing it

More agents, more reasoning, more tools, and more context are not automatically better.

They are also slower and more expensive.

PowerKit deliberately keeps easy work cheap and reserves heavyweight workflows for work that deserves them.

---

# Not every skill belongs in every prompt

PowerKit uses **progressive disclosure** on host surfaces that support skill discovery and loading:

```text
small always-on metadata
        ↓
      routing
        ↓
 relevant skill selected
        ↓
 skill instructions loaded
        ↓
 deeper references only if needed
```

The standard v0.4.0 bootstrap installs all 24 skills so every `pk` mode has its specialist workflows. Installing PowerKit does **not** mean intentionally injecting the entire toolkit into every model request.

A project can have many capabilities available while a small task loads only what it needs. Exact discovery and loading behavior remains host-dependent.

This matters for latency, context quality, and token usage.

**PowerKit watches its own weight.**

The Context Budget Auditor measures what PowerKit adds to coding-agent context, catches progressive-disclosure regressions, and tells you what to move, shorten, or lazy-load before prompt bloat becomes everyone's problem:

```bash
powerkit context audit --target .
```

It reports PowerKit-attributable estimates rather than pretending to know total provider input. Checked-in baselines and `--ci` protect always-on, discovery, and common-path budgets. See [Context budgets](docs/CONTEXT_BUDGETS.md).

---

# The toolkit

PowerKit v0.4.0 includes **24 canonical skills** and **6 specialized agent roles**.

The skills cover four broad areas:

### Foundation

How work enters and moves through the system.

Includes request preflight, repository discovery, workload routing, context recovery, task boundaries, orchestration, handoffs, and the `pk` command layer.

### Delivery

How non-trivial changes are understood and implemented.

Includes impact analysis, vertical slicing, implementation planning, migration planning, parallel investigation, and evidence-first debugging.

### Quality

How work is challenged and proven.

Includes verification, test-gap analysis, adversarial review, anti-slop review, security/privacy review, API contract protection, and implementation criticism.

### Specialist

Focused workflows for dependency decisions, UI evidence, and runtime UX evaluation.

The canonical skills live in:

```text
.agents/skills/
```

Platform adapters keep the skill definitions portable across supported assistants.

---

# Specialized agents

Some problems benefit from independent context.

PowerKit includes focused agent roles for:

| Agent                  | Responsibility                                            |
| ---------------------- | --------------------------------------------------------- |
| `evidence-explorer`    | Understand the real code path without editing it          |
| `system-architect`     | Analyze boundaries, contracts, and migrations             |
| `bounded-implementer`  | Own a clearly defined set of source changes               |
| `independent-verifier` | Prove behavior without trusting the implementation report |
| `adversarial-critic`   | Try to falsify the proposed solution                      |
| `runtime-ui-observer`  | Evaluate the running experience rather than source alone  |

One rule matters more than the number of agents:

**Parallelize independent investigation. Keep one writer when changes overlap.**

Agent definitions are platform-specific files under `adapters/*/agents/`; the installer places selected copies in each host's project location.

---

# AI decides. Code enforces.

Not every rule should depend on model judgment.

PowerKit also includes deterministic tooling for:

* initialization and installation
* synchronization from committed project state
* explicitly selected version updates
* managed-file ownership and content digests
* repository status and health checks
* effort × risk policy resolution and capability negotiation
* versioned platform capability diagnostics and safe execution decisions
* offline context accounting, recommendations, baselines, and CI budgets
* static validation
* release packaging
* repository-defined verification commands
* conflict protection
* optional catastrophic-command guarding
* ownership-proven uninstall
* routing fixtures and static eval validation

The model decides what should happen.

Deterministic tooling handles the things that should happen the same way every time.

---

# Agent-native from the start

PowerKit is designed primarily for **coding assistants**, not for humans to operate as another complicated developer tool.

The repository exposes:

```text
BOOTSTRAP.md
```

as the authoritative agent entry point for installation, synchronization, updates, status checks, and removal.

The machine-readable distribution manifest at `manifests/powerkit.json` records the release version, bootstrap path, supported platforms, defaults, state paths, and deterministic command surface.

Consumer repositories retain PowerKit state under:

```text
.ai-powerkit/
```

so future sessions can inspect what is desired, what is installed, which version is pinned, and which assets PowerKit can prove it owns.

Projects can also commit an `execution_policy` object that bounds cost, latency, parallelism, model upgrades, network use, high-risk checkpoints, iteration limits, and optional adapter-local model mappings.

This enables a simple lifecycle:

```text
FIRST USE

GitHub URL
   ↓
agent bootstrap contract
   ↓
pinned deterministic installation
   ↓
doctor
   ↓
pk ready
```

```text
DAILY USE

explicit pk invocation
 ↓
intent
 ↓
right-sized workflow
 ↓
evidence-backed result
```

---

# Teams do not have to rebuild the setup

A PowerKit-enabled repository can commit its desired project configuration.

A teammate cloning the repository should not need to remember which profiles, skills, or adapters the original developer selected.

Their coding assistant can read `.ai-powerkit/project.json`, resolve the pinned PowerKit release, run `powerkit sync`, and validate the reconstructed installation with `powerkit doctor`.

PowerKit tracks managed assets and content digests in `.ai-powerkit/install-manifest.json` so synchronization, stale pruning, and uninstall can distinguish proven PowerKit content from unrelated project configuration.

---

# Safety is part of the design

PowerKit modifies coding-assistant configuration and can influence how agents operate.

That deserves the same care as other engineering tooling.

The v0.4.0 installer, lifecycle commands, and Execution Broker are designed around:

* path-containment checks
* symlink defenses
* managed ownership and SHA-256 content digests
* conflict detection before mutation
* explicit version pins
* collision-safe backups
* dry runs for mutating lifecycle commands
* digest-aware doctor checks
* offline context-budget inspection with no consumer-code execution
* capability states that distinguish native, partial, emulated, and unavailable controls
* `STOP` decisions when an explicit high-risk boundary cannot be enforced
* stale-file pruning only when ownership remains proven
* uninstall that refuses ambiguous or changed assets
* deterministic package construction from reviewed tracked files

Optional hooks remain **opt-in** and are never enabled automatically.

PowerKit is not a security sandbox and does not pretend to be one.

Repository-defined verification commands are executable project code. Bootstrap preserves their configuration but does not invent or automatically run project commands.

---

# This is not a prompt library

Prompt libraries accumulate instructions.

PowerKit is trying to solve a different problem:

**How should an AI coding assistant behave from the moment it receives a request until the moment it claims the work is complete?**

That includes:

```text
interpretation
→ evidence
→ boundaries
→ execution
→ verification
→ criticism
→ handoff
```

The individual prompts are implementation details.

The workflow is the product.

---

# Repository map

```text
.agents/skills/     Canonical portable skills, including the pk router
powerkit/           Deterministic lifecycle and CLI implementation
adapters/           Platform-specific agent and hook/config integration
hooks/              Optional deterministic guards
manifests/          Machine-readable PowerKit distribution metadata
evals/              Cross-skill routing fixtures
tests/              Installer, lifecycle, safety, and regression coverage
tools/              Validation, packaging, legacy install, and verification tools
schemas/            Versioned machine contracts, including broker and Proof Pack evidence
docs/               Architecture, security, portability, and operating guidance
BOOTSTRAP.md         Entry point for coding assistants managing PowerKit
```

---

# Project status

PowerKit v0.4.0 is an integration candidate for:

* OpenAI Codex
* Anthropic Claude Code
* GitHub Copilot

Platform capabilities and invocation mechanisms change quickly. PowerKit keeps canonical skill behavior portable and isolates platform-specific differences in adapters wherever possible.

The repository contains structural validation, lifecycle tests, routing fixtures, managed-update tests, packaging tests, and safety regressions. The release is not proven merely because those files exist: acceptance requires a conflict-free tree with the validator and complete test suite passing.

The broker-owned launch path has been live-validated with Codex `0.147.0-alpha.6.5` and Claude Code `2.1.123`. That proves those validated clients accepted the broker-owned settings and completed the task; it does not prove remote host acknowledgement or every platform surface. Copilot remains documentation-backed rather than locally live-validated.

The generated broker directive is currently about 126–163 estimated tokens. The measured complete selected-path increase is 761–798 estimated tokens, with all modeled paths inside their configured budgets but in the context auditor's `watch` band. The routing fixtures prove deterministic allocation, not that the broker already delivers net token, latency, cost, or outcome improvements; comparative live evaluation remains future work.

---

# What comes next

The next frontier is not more prompts.

It is **measured execution quality across live clients**.

PowerKit is being designed so its behavior can be evaluated against unmodified coding assistants on things that actually matter:

* task success
* routing accuracy
* unnecessary clarification
* assumption rate
* debugging quality
* verification depth
* rework
* latency
* context consumption
* token usage

The toolkit should earn every bit of complexity it introduces.

---

# Contributing

A useful PowerKit contribution is not:

> “Here is a clever prompt I use.”

It is a repeatable engineering behavior with:

* a clear reason to exist
* explicit activation boundaries
* known failure cases
* deterministic checks where possible
* evidence that it improves outcomes

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution model.

---

# License

MIT.

---

## Give your coding assistant PowerKit

```text
Install AI Engineering PowerKit into this repository:

https://github.com/tyreamer/ai-engineering-powerkit

Follow BOOTSTRAP.md, preserve existing project configuration,
verify the installation, and tell me when PowerKit is ready.
```

Then explicitly invoke the installed `pk` skill using the syntax supported by your coding assistant:

```text
/pk

<what you want>
```

# Why this is not just a prompt library

A prompt library helps people remember useful wording. It does not create a dependable engineering system.

## Prompt files are useful for explicit entry points

Use a prompt file when a person intentionally wants to start a known task, such as:

- Review this branch.
- Create an onboarding map.
- Diagnose a failing CI job.
- Prepare a migration plan.

They are easy to discover but still depend on the user selecting the right prompt.

## Skills add reusable judgment

A skill can be selected from the task description and can carry a multi-step workflow, references, examples, and scripts. It is appropriate when the same reasoning process should be reused across many requests.

## Instructions set defaults

A short instruction such as “inspect before asking” should apply to every task. Loading a 200-line debugging procedure on every turn would waste context and may distort unrelated work.

## Hooks enforce deterministic policy

A model may forget to run a formatter or may rationalize a destructive command. A hook can enforce a deterministic rule every time.

## Subagents control context and responsibility

A second prompt in the same conversation does not isolate noisy exploration. A subagent can trace a code path, inspect tests, or challenge a plan in a separate context, then return a compact evidence packet.

## Evals keep the system honest

A clever-sounding skill can trigger too often, conflict with another skill, or produce unnecessary ceremony. Routing cases and behavioral scenarios make those failures reviewable.

The repository should therefore be treated as an engineering harness, not as a collection of magic incantations.

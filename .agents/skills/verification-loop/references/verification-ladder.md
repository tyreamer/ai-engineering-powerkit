# Verification evidence examples

- Static: formatter, linter, compiler, type checker, schema validation
- Targeted: changed unit/component tests and a regression test reproducing the defect
- Broader: package, service, integration, end-to-end, or contract suite
- Runtime: launch app/service, perform the changed flow, inspect UI/network/state
- Operational: migration dry run, logs, metrics, retry behavior, rollback exercise
- Diff: final patch, generated files, secrets, TODOs, unrelated changes

A higher level does not automatically replace a lower one. A successful end-to-end flow may still hide a type error in an unvisited branch; a unit test may not prove the app launches.

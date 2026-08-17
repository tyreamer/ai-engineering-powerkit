## What changed

Describe the repeated workflow, adapter, guardrail, or tooling behavior changed.

## Why it belongs in PowerKit

Explain why this is not better handled by a short repository instruction, an existing skill, a deterministic hook, or a repository-specific document.

## Routing and behavior

- Positive scenarios:
- Negative scenarios:
- Material assumptions prevented:
- Platform-specific behavior:

## Verification

- [ ] `python3 tools/validate.py`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] Hook self-tests when hook code changed
- [ ] Installer dry run when installation behavior changed
- [ ] Documentation and catalog updated
- [ ] Executable code reviewed for secrets, network access, and destructive behavior

## Residual risk

State what was not verified in a live platform client.

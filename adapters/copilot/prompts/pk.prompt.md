---
agent: 'agent'
description: 'Route a normal-language engineering request through AI Engineering PowerKit'
---

<!-- AI-ENGINEERING-POWERKIT-MANAGED -->

Apply the canonical [PowerKit command skill](../../.agents/skills/pk/SKILL.md) to the rest of the user's request.

Preserve any explicit mode, attachments, file references, scope limits, plan-only or no-write constraints, and verification requirements. Load only the workflows selected by the canonical skill. If there is no task, show its concise help.

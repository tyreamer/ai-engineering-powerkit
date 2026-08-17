---
applyTo: ".agents/skills/**"
---

Skill directories are canonical source.

- Keep each skill focused on one repeated workflow.
- Make `description` specific enough for implicit routing and include when to use the skill.
- Add or update `evals/cases.json`.
- Avoid vendor-specific frontmatter in canonical skills.
- Keep `SKILL.md` below 500 lines when practical; move detail into referenced files.
- Run `python3 tools/validate.py`.

#!/usr/bin/env python3
"""Scaffold a new canonical PowerKit skill."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--title")
    parser.add_argument("--profile", choices=("foundation", "delivery", "quality", "specialist"))
    parser.add_argument("--description", required=True)
    args = parser.parse_args()

    if not NAME_RE.fullmatch(args.name):
        parser.error("name must use lowercase letters, digits, and single hyphens")
    if len(args.description) > 1024:
        parser.error("description exceeds 1024 characters")
    if "use " not in args.description.lower():
        parser.error("description should say when to use the skill")

    title = args.title or args.name.replace("-", " ").title()
    profile = args.profile or "specialist"
    directory = ROOT / ".agents" / "skills" / args.name
    if directory.exists():
        parser.error(f"skill already exists: {directory}")

    directory.mkdir(parents=True)
    skill = f"""---
name: {args.name}
description: {json.dumps(args.description)}
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: {profile}
---

# {title}

## Purpose

Describe the repeated failure mode this skill prevents.

## Workflow

1. Inspect the relevant evidence.
2. Perform the bounded task.
3. Verify the output.

## Output contract

Describe the observable result.

## Boundaries

State when not to use this skill and what it must not assume.
"""
    (directory / "SKILL.md").write_text(skill, encoding="utf-8")
    eval_dir = directory / "evals"
    eval_dir.mkdir()
    (eval_dir / "cases.json").write_text(
        json.dumps(
            {
                "skill": args.name,
                "positive_cases": [
                    {"prompt": f"Use {args.name} for this bounded scenario."},
                    {"prompt": f"This request should trigger {args.name}."},
                ],
                "negative_cases": [
                    {"prompt": f"This unrelated request should not use {args.name}."},
                    {"prompt": "A simple direct edit that needs no specialized workflow."},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Created {directory}")
    print("Add the skill to catalog.json and replace the scaffold eval cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Inspect a repository for AI-assistant customization and build metadata."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def count_skill_dirs(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for child in path.iterdir() if child.is_dir() and (child / "SKILL.md").is_file())


def git_summary(target: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(target), "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "git unavailable"
    if result.returncode != 0:
        return "not a Git worktree"
    lines = result.stdout.strip().splitlines()
    if not lines:
        return "clean worktree"
    return "; ".join(lines[:4]) + ("; …" if len(lines) > 4 else "")


def package_scripts(target: Path) -> list[str]:
    path = target / "package.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ["package.json exists but is invalid"]
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    preferred = ["build", "test", "lint", "typecheck", "check", "dev", "start"]
    return [f"npm run {name}" for name in preferred if name in scripts]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=Path("."))
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    if not target.is_dir():
        parser.error(f"target does not exist: {target}")

    print(f"Target: {target}")
    print(f"Git: {git_summary(target)}")
    print()

    checks = [
        ("AGENTS.md", target / "AGENTS.md"),
        ("CLAUDE.md", target / "CLAUDE.md"),
        ("Copilot instructions", target / ".github/copilot-instructions.md"),
        ("PowerKit manifest", target / ".ai-powerkit/install-manifest.json"),
        ("PowerKit project config", target / ".ai-powerkit/project.json"),
        ("Codex config", target / ".codex/config.toml"),
        ("Claude settings", target / ".claude/settings.json"),
    ]
    print("Customization:")
    for label, path in checks:
        print(f"  {'✓' if path.exists() else '·'} {label}: {path.relative_to(target)}")
    print(f"  {'✓' if count_skill_dirs(target / '.agents/skills') else '·'} "
          f"canonical skills: {count_skill_dirs(target / '.agents/skills')}")
    print(f"  {'✓' if count_skill_dirs(target / '.claude/skills') else '·'} "
          f"Claude skills: {count_skill_dirs(target / '.claude/skills')}")
    print()

    indicators = [
        ("Node", "package.json"),
        ("Python", "pyproject.toml"),
        ("Python requirements", "requirements.txt"),
        ("Go", "go.mod"),
        ("Rust", "Cargo.toml"),
        ("Gradle", "gradlew"),
        ("Maven", "pom.xml"),
        ("Make", "Makefile"),
        ("Docker", "Dockerfile"),
    ]
    present = [label for label, filename in indicators if (target / filename).exists()]
    print("Detected project signals:", ", ".join(present) if present else "none")

    scripts = package_scripts(target)
    if scripts:
        print("Candidate package scripts:")
        for command in scripts:
            print(f"  - {command}")

    recommendations: list[str] = []
    if not (target / "AGENTS.md").exists() and not (target / "CLAUDE.md").exists():
        recommendations.append("Add concise repository instructions with verified build and test commands.")
    if count_skill_dirs(target / ".agents/skills") == 0:
        recommendations.append("Install the foundation profile before broader skill packs.")
    if not (target / ".ai-powerkit/project.json").exists():
        recommendations.append("Create .ai-powerkit/project.json only after commands are verified manually.")
    if not present:
        recommendations.append("Document bootstrap, build, test, lint, and run commands explicitly.")
    if recommendations:
        print("\nRecommendations:")
        for item in recommendations:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

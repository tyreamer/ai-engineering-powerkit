#!/usr/bin/env python3
"""Static validation for AI Engineering PowerKit."""

from __future__ import annotations

import json
import py_compile
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MANAGED_MARKER = "AI-ENGINEERING-POWERKIT-MANAGED"


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing opening YAML delimiter")
    try:
        _, front, body = text.split("---", 2)
    except ValueError as exc:
        raise ValueError("missing closing YAML delimiter") from exc

    values: dict[str, str] = {}
    for line in front.splitlines():
        if not line or line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        raw = raw.strip()
        if not raw:
            continue
        try:
            value = json.loads(raw)
            values[key.strip()] = str(value)
        except json.JSONDecodeError:
            values[key.strip()] = raw
    return values, body.strip()


def validate_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return None


def validate_toml(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{path.relative_to(ROOT)}: invalid TOML: {exc}")
        return None


def validate_agent_adapters(expected_agents: set[str], errors: list[str]) -> None:
    agent_roots = {
        "codex": (ROOT / "adapters/codex/agents", ".toml"),
        "claude": (ROOT / "adapters/claude/agents", ".md"),
        "copilot": (ROOT / "adapters/copilot/agents", ".agent.md"),
    }
    for platform, (directory, suffix) in agent_roots.items():
        names: set[str] = set()
        paths: list[Path] = []
        if directory.exists():
            for path in directory.iterdir():
                if path.is_file() and path.name.endswith(suffix):
                    name = path.name[: -len(suffix)]
                    names.add(name)
                    paths.append(path)
        if names != expected_agents:
            errors.append(
                f"{platform} agent adapter mismatch; expected {sorted(expected_agents)}, "
                f"found {sorted(names)}"
            )

        for path in sorted(paths):
            expected_name = path.name[: -len(suffix)]
            text = path.read_text(encoding="utf-8")
            if MANAGED_MARKER not in text:
                errors.append(f"{path.relative_to(ROOT)}: missing managed installer marker")

            if platform == "codex":
                payload = validate_toml(path, errors)
                if not isinstance(payload, dict):
                    continue
                if payload.get("name") != expected_name:
                    errors.append(f"{path.relative_to(ROOT)}: name must match filename")
                for field in ("description", "developer_instructions"):
                    if not isinstance(payload.get(field), str) or not payload[field].strip():
                        errors.append(f"{path.relative_to(ROOT)}: {field} is required")
                if payload.get("sandbox_mode") not in {
                    "read-only",
                    "workspace-write",
                    "danger-full-access",
                }:
                    errors.append(f"{path.relative_to(ROOT)}: invalid sandbox_mode")
            else:
                try:
                    metadata, body = parse_frontmatter(path)
                except ValueError as exc:
                    errors.append(f"{path.relative_to(ROOT)}: {exc}")
                    continue
                if metadata.get("name") != expected_name:
                    errors.append(f"{path.relative_to(ROOT)}: name must match filename")
                if not metadata.get("description"):
                    errors.append(f"{path.relative_to(ROOT)}: description is required")
                if platform == "copilot" and not metadata.get("tools"):
                    errors.append(
                        f"{path.relative_to(ROOT)}: explicit tools are required for least privilege"
                    )
                if not body:
                    errors.append(f"{path.relative_to(ROOT)}: body is empty")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    catalog_path = ROOT / "catalog.json"
    catalog = validate_json(catalog_path, errors)
    if not isinstance(catalog, dict):
        catalog = {}

    skill_root = ROOT / ".agents" / "skills"
    if not skill_root.is_dir():
        errors.append(".agents/skills is missing")
        skill_dirs: list[Path] = []
    else:
        skill_dirs = sorted(path for path in skill_root.iterdir() if path.is_dir())

    discovered: dict[str, dict[str, str]] = {}
    for directory in skill_dirs:
        skill_file = directory / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"{directory.relative_to(ROOT)}: missing SKILL.md")
            continue
        try:
            metadata, body = parse_frontmatter(skill_file)
        except ValueError as exc:
            errors.append(f"{skill_file.relative_to(ROOT)}: {exc}")
            continue

        name = metadata.get("name", "")
        description = metadata.get("description", "")
        if not NAME_RE.fullmatch(name):
            errors.append(f"{skill_file.relative_to(ROOT)}: invalid name {name!r}")
        if len(name) > 64:
            errors.append(f"{skill_file.relative_to(ROOT)}: name exceeds 64 characters")
        if name != directory.name:
            errors.append(f"{skill_file.relative_to(ROOT)}: name must match parent directory")
        if not description:
            errors.append(f"{skill_file.relative_to(ROOT)}: description is required")
        if len(description) > 1024:
            errors.append(f"{skill_file.relative_to(ROOT)}: description exceeds 1024 characters")
        if "use " not in description.lower():
            warnings.append(
                f"{skill_file.relative_to(ROOT)}: description should say when to use the skill"
            )
        if not body:
            errors.append(f"{skill_file.relative_to(ROOT)}: body is empty")
        line_count = len(skill_file.read_text(encoding="utf-8").splitlines())
        if line_count > 500:
            warnings.append(
                f"{skill_file.relative_to(ROOT)}: {line_count} lines; consider references"
            )

        eval_path = directory / "evals" / "cases.json"
        cases = validate_json(eval_path, errors) if eval_path.exists() else None
        if not isinstance(cases, dict):
            errors.append(f"{directory.relative_to(ROOT)}: missing valid evals/cases.json")
        else:
            if cases.get("skill") != name:
                errors.append(f"{eval_path.relative_to(ROOT)}: skill field does not match")
            for key in ("positive_cases", "negative_cases"):
                values = cases.get(key)
                if not isinstance(values, list) or len(values) < 2:
                    errors.append(
                        f"{eval_path.relative_to(ROOT)}: {key} must contain at least two cases"
                    )
                elif any(
                    not isinstance(item, dict) or not str(item.get("prompt", "")).strip()
                    for item in values
                ):
                    errors.append(
                        f"{eval_path.relative_to(ROOT)}: every {key} entry needs a prompt"
                    )

        if name:
            if name in discovered:
                errors.append(f"duplicate skill name: {name}")
            discovered[name] = {"description": description}

    catalog_items = {
        item.get("name"): item
        for item in catalog.get("skills", [])
        if isinstance(item, dict) and item.get("name")
    }
    catalog_skills = set(catalog_items)
    discovered_names = set(discovered)
    if catalog_skills != discovered_names:
        missing = sorted(discovered_names - catalog_skills)
        extra = sorted(catalog_skills - discovered_names)
        if missing:
            errors.append(f"catalog.json missing skills: {', '.join(missing)}")
        if extra:
            errors.append(f"catalog.json references unknown skills: {', '.join(extra)}")
    for name in sorted(discovered_names & catalog_skills):
        if catalog_items[name].get("description") != discovered[name]["description"]:
            errors.append(f"catalog.json description is out of sync for {name}")

    # Validate profile memberships and catalog profile fields.
    profile_members: set[str] = set()
    for profile, payload in catalog.get("profiles", {}).items():
        if not isinstance(payload, dict) or not isinstance(payload.get("skills"), list):
            errors.append(f"catalog profile {profile!r} is invalid")
            continue
        for name in payload["skills"]:
            if name in profile_members:
                errors.append(f"skill {name!r} appears in more than one profile")
            profile_members.add(name)
            item = catalog_items.get(name)
            if isinstance(item, dict) and item.get("profile") != profile:
                errors.append(f"catalog skill {name!r} has incorrect profile field")
    if profile_members != discovered_names:
        errors.append("catalog profile membership does not cover every skill exactly once")

    # Cross-skill routing scenarios must reference real skills and unique IDs.
    cross_path = ROOT / "evals" / "cross-skill-scenarios.json"
    cross = validate_json(cross_path, errors)
    if isinstance(cross, dict):
        seen_ids: set[str] = set()
        scenarios = cross.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios:
            errors.append(f"{cross_path.relative_to(ROOT)}: scenarios must be a non-empty list")
        else:
            for index, scenario in enumerate(scenarios):
                if not isinstance(scenario, dict):
                    errors.append(
                        f"{cross_path.relative_to(ROOT)}: scenario {index} must be an object"
                    )
                    continue
                scenario_id = str(scenario.get("id", "")).strip()
                if not scenario_id:
                    errors.append(
                        f"{cross_path.relative_to(ROOT)}: scenario {index} is missing id"
                    )
                elif scenario_id in seen_ids:
                    errors.append(
                        f"{cross_path.relative_to(ROOT)}: duplicate scenario id {scenario_id}"
                    )
                seen_ids.add(scenario_id)
                for key in ("expected_skills", "allowed_skills"):
                    values = scenario.get(key, [])
                    if not isinstance(values, list):
                        errors.append(
                            f"{cross_path.relative_to(ROOT)}: {scenario_id} {key} must be a list"
                        )
                        continue
                    unknown = sorted(set(values) - discovered_names)
                    if unknown:
                        errors.append(
                            f"{cross_path.relative_to(ROOT)}: {scenario_id} references unknown "
                            f"skills in {key}: {', '.join(unknown)}"
                        )

    expected_agents = {
        "evidence-explorer",
        "system-architect",
        "bounded-implementer",
        "independent-verifier",
        "adversarial-critic",
        "runtime-ui-observer",
    }
    validate_agent_adapters(expected_agents, errors)

    # Validate platform examples beyond basic JSON/TOML syntax.
    codex_hooks_path = ROOT / "adapters" / "codex" / "hooks.example.json"
    codex_hooks = validate_json(codex_hooks_path, errors)
    if isinstance(codex_hooks, dict):
        hooks = codex_hooks.get("hooks")
        if not isinstance(hooks, dict):
            errors.append(f"{codex_hooks_path.relative_to(ROOT)}: top-level hooks object is required")
        else:
            pre_tool = hooks.get("PreToolUse")
            if not isinstance(pre_tool, list) or not pre_tool:
                errors.append(
                    f"{codex_hooks_path.relative_to(ROOT)}: hooks.PreToolUse must be non-empty"
                )
            else:
                first = pre_tool[0] if isinstance(pre_tool[0], dict) else {}
                handlers = first.get("hooks") if isinstance(first, dict) else None
                handler = handlers[0] if isinstance(handlers, list) and handlers else {}
                command = handler.get("command", "") if isinstance(handler, dict) else ""
                if "git rev-parse --show-toplevel" not in command:
                    errors.append(
                        f"{codex_hooks_path.relative_to(ROOT)}: repo-local hook must resolve from Git root"
                    )

    claude_hooks_path = ROOT / "adapters" / "claude" / "settings.hooks.example.json"
    claude_hooks = validate_json(claude_hooks_path, errors)
    if isinstance(claude_hooks, dict):
        hooks = claude_hooks.get("hooks")
        if not isinstance(hooks, dict) or not isinstance(hooks.get("PreToolUse"), list):
            errors.append(
                f"{claude_hooks_path.relative_to(ROOT)}: hooks.PreToolUse must be present"
            )

    codex_config_path = ROOT / "adapters" / "codex" / "config.example.toml"
    codex_config = validate_toml(codex_config_path, errors)
    if isinstance(codex_config, dict):
        features = codex_config.get("features")
        agents = codex_config.get("agents")
        if not isinstance(features, dict) or features.get("hooks") is not True:
            errors.append(f"{codex_config_path.relative_to(ROOT)}: features.hooks must be true")
        if not isinstance(features, dict) or features.get("multi_agent") is not True:
            errors.append(f"{codex_config_path.relative_to(ROOT)}: features.multi_agent must be true")
        max_threads = agents.get("max_concurrent_threads_per_session") if isinstance(agents, dict) else None
        if not isinstance(max_threads, int) or max_threads < 1:
            errors.append(
                f"{codex_config_path.relative_to(ROOT)}: agents.max_concurrent_threads_per_session must be positive"
            )

    # Parse every JSON and TOML source file, including examples and project metadata.
    for path in ROOT.rglob("*.json"):
        if any(part in {".git", "dist", "build"} for part in path.parts):
            continue
        validate_json(path, errors)
    for path in ROOT.rglob("*.toml"):
        if any(part in {".git", "dist", "build"} for part in path.parts):
            continue
        validate_toml(path, errors)

    # Compile Python source.
    for path in list((ROOT / "tools").glob("*.py")) + list((ROOT / "hooks").glob("*.py")):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{path.relative_to(ROOT)}: Python compile failed: {exc.msg}")

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"Validation passed: {len(discovered_names)} skills, "
        f"{len(expected_agents)} agent profiles, {len(warnings)} warnings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

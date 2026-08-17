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
SCAFFOLD_SENTINELS = (
    "Describe the repeated failure mode this skill prevents.",
    "Describe the observable result.",
    "State when not to use this skill",
    "for this bounded scenario.",
    "This request should trigger ",
    "This unrelated request should not use ",
)
COPILOT_TOOL_ALIASES = {
    "read",
    "search",
    "edit",
    "execute",
    "agent",
    "todo",
    "web",
    "playwright/*",
}
CLAUDE_TOOL_ALIASES = {"Read", "Grep", "Glob", "Edit", "Write", "Bash"}


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing opening YAML delimiter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("missing closing YAML delimiter") from exc
    front_lines = lines[1:closing]
    body = "\n".join(lines[closing + 1 :])

    values: dict[str, Any] = {}
    current_mapping: str | None = None
    for line_number, line in enumerate(front_lines, start=2):
        if not line:
            continue
        if line.startswith((" ", "\t")):
            if not current_mapping or not line.startswith("  ") or line.startswith("   "):
                raise ValueError(f"unsupported YAML indentation at line {line_number}")
            nested = values[current_mapping]
            if not isinstance(nested, dict) or ":" not in line:
                raise ValueError(f"malformed nested YAML at line {line_number}")
            key, raw = line.strip().split(":", 1)
            key = key.strip()
            raw = raw.strip()
            if not key or not raw or key in nested:
                raise ValueError(f"malformed nested YAML at line {line_number}")
            try:
                nested[key] = json.loads(raw)
            except json.JSONDecodeError:
                if raw.startswith(("[", "{", '"', "'")):
                    raise ValueError(
                        f"malformed nested YAML scalar for {key!r} at line {line_number}"
                    )
                nested[key] = raw
            continue
        current_mapping = None
        if ":" not in line:
            raise ValueError(f"malformed top-level YAML at line {line_number}")
        key, raw = line.split(":", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"empty YAML key at line {line_number}")
        if key in values:
            raise ValueError(f"duplicate YAML key {key!r}")
        raw = raw.strip()
        if not raw:
            values[key] = {}
            current_mapping = key
            continue
        try:
            value = json.loads(raw)
            values[key] = value
        except json.JSONDecodeError:
            if raw.startswith(("[", "{", '"', "'")):
                raise ValueError(f"malformed YAML scalar for {key!r} at line {line_number}")
            values[key] = raw
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
    behavior: dict[str, dict[str, tuple[str, str]]] = {}
    for platform, (directory, suffix) in agent_roots.items():
        behavior[platform] = {}
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
            marker_lines = {
                f"# {MANAGED_MARKER}",
                f"<!-- {MANAGED_MARKER} -->",
            }
            if not any(line.strip() in marker_lines for line in text.splitlines()):
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
                if "model" in payload:
                    errors.append(f"{path.relative_to(ROOT)}: shared agents must not pin a model")
                if expected_name in {
                    "adversarial-critic",
                    "evidence-explorer",
                    "system-architect",
                } and payload.get("sandbox_mode") != "read-only":
                    errors.append(f"{path.relative_to(ROOT)}: read-only role needs read-only sandbox")
                behavior[platform][expected_name] = (
                    str(payload.get("description", "")).strip(),
                    str(payload.get("developer_instructions", "")).strip(),
                )
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
                tools = metadata.get("tools")
                if platform == "copilot":
                    if not isinstance(tools, list) or not tools:
                        errors.append(
                            f"{path.relative_to(ROOT)}: explicit tools array is required for least privilege"
                        )
                        tool_names: set[str] = set()
                    else:
                        tool_names = {str(item) for item in tools}
                        unknown_tools = sorted(
                            tool
                            for tool in tool_names
                            if tool not in COPILOT_TOOL_ALIASES
                        )
                        if unknown_tools:
                            errors.append(
                                f"{path.relative_to(ROOT)}: unknown Copilot tool aliases: "
                                f"{', '.join(unknown_tools)}"
                            )
                    if len(body) > 30_000:
                        errors.append(f"{path.relative_to(ROOT)}: prompt exceeds 30000 characters")
                else:
                    if not isinstance(tools, str) or not tools.strip():
                        errors.append(f"{path.relative_to(ROOT)}: explicit tools are required")
                        tool_names = set()
                    else:
                        tool_names = {item.strip() for item in tools.split(",") if item.strip()}
                        unknown_tools = sorted(tool_names - CLAUDE_TOOL_ALIASES)
                        if unknown_tools:
                            errors.append(
                                f"{path.relative_to(ROOT)}: unknown Claude tool aliases: "
                                f"{', '.join(unknown_tools)}"
                            )
                if "model" in metadata:
                    errors.append(f"{path.relative_to(ROOT)}: shared agents must not pin a model")
                if expected_name in {
                    "adversarial-critic",
                    "evidence-explorer",
                    "system-architect",
                }:
                    write_tools = {"Edit", "Write", "Bash", "edit", "execute"}
                    if tool_names & write_tools:
                        errors.append(
                            f"{path.relative_to(ROOT)}: read-only role declares write/execute tools"
                        )
                if expected_name in {"independent-verifier", "runtime-ui-observer"}:
                    if tool_names & {"Edit", "Write", "edit"}:
                        errors.append(
                            f"{path.relative_to(ROOT)}: non-writing role declares edit tools"
                        )
                if not body:
                    errors.append(f"{path.relative_to(ROOT)}: body is empty")
                marker = f"<!-- {MANAGED_MARKER} -->"
                normalized_body = body.replace(marker, "", 1).strip()
                behavior[platform][expected_name] = (
                    str(metadata.get("description", "")).strip(),
                    normalized_body,
                )

    for name in sorted(expected_agents):
        records = {
            platform: behavior[platform].get(name)
            for platform in agent_roots
            if behavior[platform].get(name) is not None
        }
        if len(set(records.values())) > 1:
            errors.append(
                f"agent adapter behavior drift for {name}: {', '.join(sorted(records))} differ"
            )


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    catalog_path = ROOT / "catalog.json"
    catalog = validate_json(catalog_path, errors)
    if not isinstance(catalog, dict):
        catalog = {}
    elif catalog.get("schema_version") != 1:
        errors.append("catalog.json: unsupported schema_version")

    project_path = ROOT / "pyproject.toml"
    project_config = validate_toml(project_path, errors) or {}
    project = project_config.get("project", {})
    toolkit_config = project_config.get("tool", {}).get("powerkit", {})
    if isinstance(project, dict) and project.get("version") != catalog.get("version"):
        errors.append("catalog.json and pyproject.toml versions differ")
    if (
        not isinstance(toolkit_config, dict)
        or toolkit_config.get("canonical_skill_root") != catalog.get("canonical_skill_root")
    ):
        errors.append("catalog.json and pyproject.toml canonical skill roots differ")
    if catalog.get("canonical_skill_root") != ".agents/skills":
        errors.append("catalog.json: canonical_skill_root must be .agents/skills")

    for path in ROOT.rglob("*"):
        if any(part in {".git", "build", "dist", "__pycache__"} for part in path.parts):
            continue
        if path.is_symlink():
            errors.append(f"{path.relative_to(ROOT)}: repository customizations must not use symlinks")

    skill_root = ROOT / ".agents" / "skills"
    if not skill_root.is_dir():
        errors.append(".agents/skills is missing")
        skill_dirs: list[Path] = []
    else:
        skill_dirs = sorted(path for path in skill_root.iterdir() if path.is_dir())

    for path in ROOT.rglob("SKILL.md"):
        if any(part in {".git", "build", "dist"} for part in path.parts):
            continue
        try:
            path.relative_to(skill_root)
        except ValueError:
            errors.append(
                f"{path.relative_to(ROOT)}: canonical skill bodies belong only under .agents/skills"
            )

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
        unknown_fields = sorted(
            set(metadata) - {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
        )
        if unknown_fields:
            errors.append(
                f"{skill_file.relative_to(ROOT)}: unsupported frontmatter fields: "
                f"{', '.join(unknown_fields)}"
            )
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"{skill_file.relative_to(ROOT)}: invalid name {name!r}")
        if isinstance(name, str) and len(name) > 64:
            errors.append(f"{skill_file.relative_to(ROOT)}: name exceeds 64 characters")
        if name != directory.name:
            errors.append(f"{skill_file.relative_to(ROOT)}: name must match parent directory")
        if not isinstance(description, str) or not description:
            errors.append(f"{skill_file.relative_to(ROOT)}: description is required")
        if isinstance(description, str) and len(description) > 1024:
            errors.append(f"{skill_file.relative_to(ROOT)}: description exceeds 1024 characters")
        if isinstance(description, str) and "use " not in description.lower():
            warnings.append(
                f"{skill_file.relative_to(ROOT)}: description should say when to use the skill"
            )
        component = metadata.get("metadata")
        if not isinstance(component, dict):
            errors.append(f"{skill_file.relative_to(ROOT)}: metadata mapping is required")
            component = {}
        if component.get("author") != "ai-engineering-powerkit":
            errors.append(f"{skill_file.relative_to(ROOT)}: metadata.author is invalid")
        component_version = component.get("version")
        if not isinstance(component_version, str) or not re.fullmatch(
            r"\d+\.\d+\.\d+", component_version
        ):
            errors.append(f"{skill_file.relative_to(ROOT)}: metadata.version must be semantic")
        component_profile = component.get("profile")
        if not isinstance(component_profile, str) or not component_profile:
            errors.append(f"{skill_file.relative_to(ROOT)}: metadata.profile is required")
        if not body:
            errors.append(f"{skill_file.relative_to(ROOT)}: body is empty")
        for sentinel in SCAFFOLD_SENTINELS[:3]:
            if sentinel in body:
                errors.append(f"{skill_file.relative_to(ROOT)}: scaffold placeholder remains")
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
            prompts_by_kind: dict[str, set[str]] = {}
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
                else:
                    prompts = [str(item["prompt"]).strip() for item in values]
                    if len(set(prompts)) != len(prompts):
                        errors.append(f"{eval_path.relative_to(ROOT)}: duplicate prompts in {key}")
                    prompts_by_kind[key] = set(prompts)
                    for prompt in prompts:
                        if any(sentinel in prompt for sentinel in SCAFFOLD_SENTINELS[3:]):
                            errors.append(
                                f"{eval_path.relative_to(ROOT)}: scaffold routing prompt remains"
                            )
            overlap = prompts_by_kind.get("positive_cases", set()) & prompts_by_kind.get(
                "negative_cases", set()
            )
            if overlap:
                errors.append(
                    f"{eval_path.relative_to(ROOT)}: prompts cannot be both positive and negative"
                )

        if isinstance(name, str) and name:
            if name in discovered:
                errors.append(f"duplicate skill name: {name}")
            discovered[name] = {
                "description": description if isinstance(description, str) else "",
                "profile": component_profile if isinstance(component_profile, str) else "",
            }

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
        if catalog_items[name].get("profile") != discovered[name]["profile"]:
            errors.append(f"catalog.json profile is out of sync for {name}")

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
        if cross.get("schema_version") != 1:
            errors.append(f"{cross_path.relative_to(ROOT)}: unsupported schema_version")
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
                prompt = scenario.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip():
                    errors.append(
                        f"{cross_path.relative_to(ROOT)}: {scenario_id} needs a prompt"
                    )
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
                expected = scenario.get("expected_skills", [])
                allowed = scenario.get("allowed_skills", [])
                if isinstance(expected, list) and isinstance(allowed, list):
                    overlap = sorted(set(expected) & set(allowed))
                    if overlap:
                        errors.append(
                            f"{cross_path.relative_to(ROOT)}: {scenario_id} repeats skills in "
                            f"expected and allowed: {', '.join(overlap)}"
                        )
                must = scenario.get("must")
                if (
                    not isinstance(must, list)
                    or not must
                    or any(not isinstance(item, str) or not item.strip() for item in must)
                ):
                    errors.append(
                        f"{cross_path.relative_to(ROOT)}: {scenario_id} must be a non-empty string list"
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
                command_windows = (
                    handler.get("commandWindows", "") if isinstance(handler, dict) else ""
                )
                if "catastrophic_command_guard.py" not in command_windows:
                    errors.append(
                        f"{codex_hooks_path.relative_to(ROOT)}: commandWindows must invoke the guard"
                    )

    claude_hooks_path = ROOT / "adapters" / "claude" / "settings.hooks.example.json"
    claude_hooks = validate_json(claude_hooks_path, errors)
    if isinstance(claude_hooks, dict):
        hooks = claude_hooks.get("hooks")
        pre_tool = hooks.get("PreToolUse") if isinstance(hooks, dict) else None
        if not isinstance(pre_tool, list):
            errors.append(
                f"{claude_hooks_path.relative_to(ROOT)}: hooks.PreToolUse must be present"
            )
        else:
            groups = {
                group.get("matcher"): group.get("hooks")
                for group in pre_tool
                if isinstance(group, dict)
            }
            if set(groups) != {"Bash", "PowerShell"}:
                errors.append(
                    f"{claude_hooks_path.relative_to(ROOT)}: must cover Bash and PowerShell"
                )
            expected_commands = {"Bash": "python3", "PowerShell": "py"}
            for matcher, expected_command in expected_commands.items():
                handlers = groups.get(matcher)
                handler = handlers[0] if isinstance(handlers, list) and handlers else None
                if not isinstance(handler, dict):
                    errors.append(
                        f"{claude_hooks_path.relative_to(ROOT)}: {matcher} handler is required"
                    )
                    continue
                args = handler.get("args")
                if handler.get("type") != "command" or handler.get("command") != expected_command:
                    errors.append(
                        f"{claude_hooks_path.relative_to(ROOT)}: invalid {matcher} command handler"
                    )
                if (
                    not isinstance(args, list)
                    or not args
                    or "${CLAUDE_PROJECT_DIR}/.ai-powerkit/hooks/"
                    "catastrophic_command_guard.py" not in args
                ):
                    errors.append(
                        f"{claude_hooks_path.relative_to(ROOT)}: {matcher} must use the staged project guard"
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

    instruction_templates = [
        ROOT / "templates/instructions/AGENTS.block.md",
        ROOT / "templates/instructions/CLAUDE.block.md",
        ROOT / "templates/instructions/copilot-instructions.block.md",
    ]
    template_texts = {
        path.read_text(encoding="utf-8")
        for path in instruction_templates
        if path.is_file()
    }
    if len(template_texts) != 1:
        errors.append("platform instruction templates have drifted")

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

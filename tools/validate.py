#!/usr/bin/env python3
"""Static validation for AI Engineering PowerKit."""

from __future__ import annotations

import json
import py_compile
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
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
PK_MODES = {
    "auto",
    "feature",
    "bug",
    "review",
    "resume",
    "architecture",
    "ui",
    "dependency",
    "deep",
}
PK_DEPTHS = {"FAST", "STANDARD", "DEEP", "HIGH_RISK"}
PK_EFFORTS = {"FAST", "STANDARD", "DEEP"}
PK_RISKS = {"NORMAL", "ELEVATED", "HIGH"}
CAPABILITY_VALIDATION_STATES = {
    "LIVE_VALIDATED",
    "STRUCTURALLY_VALIDATED",
    "SUPPORTED",
    "UNAVAILABLE",
}
PK_ROUTING_CATEGORIES = {
    "tiny_local_change",
    "normal_feature",
    "ambiguous_material_feature",
    "photohelm_vertical_slice",
    "reproducible_bug",
    "difficult_bug",
    "review_before_merge",
    "context_recovery",
    "architecture_migration",
    "screenshot_ui",
    "dependency_evaluation",
    "high_risk_security",
    "deep_cross_cutting",
    "plan_only",
    "no_write",
    "no_heavyweight",
    "explicit_override",
    "context_budget_audit",
}


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


def validate_execution_broker(
    distribution: Mapping[str, Any] | None,
    project_template: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    try:
        from powerkit.broker import (
            CAPABILITY_CONTROLS,
            SUPPORT_STATES,
            load_capability_manifest,
            validate_project_policy,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"powerkit/broker.py: unable to load execution broker: {exc}")
        return

    expected_controls = set(CAPABILITY_CONTROLS)
    for platform in ("codex", "claude", "copilot"):
        relative = Path("adapters") / platform / "capabilities.json"
        try:
            manifest = load_capability_manifest(platform)
        except RuntimeError as exc:
            errors.append(f"{relative}: {exc}")
            continue
        if manifest.get("last_verified") is None:
            errors.append(f"{relative}: last_verified is required")
        for surface_name, surface in manifest["surfaces"].items():
            if surface.get("validation") not in CAPABILITY_VALIDATION_STATES:
                errors.append(f"{relative}: {surface_name} has invalid validation status")
            if not str(surface.get("validation_detail", "")).strip():
                errors.append(f"{relative}: {surface_name} validation detail is required")
            controls = surface.get("controls", {})
            if set(controls) != expected_controls:
                errors.append(
                    f"{relative}: {surface_name} must cover all execution controls"
                )
            for control_name, control in controls.items():
                if control.get("support") not in SUPPORT_STATES:
                    errors.append(
                        f"{relative}: {surface_name}.{control_name} has invalid support"
                    )
            for translation in surface.get("translations", []):
                if not isinstance(translation, dict) or translation.get("control") not in expected_controls:
                    errors.append(
                        f"{relative}: {surface_name} has an invalid native translation"
                    )

    schema_path = ROOT / "schemas/execution-broker-v1.schema.json"
    schema = validate_json(schema_path, errors)
    if isinstance(schema, dict):
        required = schema.get("required")
        expected = {
            "schema_version",
            "classification",
            "inputs",
            "platform",
            "desired_policy",
            "negotiation",
            "telemetry",
        }
        version = schema.get("properties", {}).get("schema_version", {})
        if version.get("const") != 1 or not isinstance(required, list) or not expected <= set(required):
            errors.append(
                "schemas/execution-broker-v1.schema.json has an invalid report contract"
            )

    policy = distribution.get("execution_policy") if isinstance(distribution, Mapping) else None
    if not isinstance(policy, Mapping):
        errors.append("manifests/powerkit.json execution_policy is required")
    else:
        try:
            validate_project_policy(policy)
        except RuntimeError as exc:
            errors.append(f"manifests/powerkit.json execution_policy is invalid: {exc}")
    if isinstance(project_template, Mapping) and project_template.get("execution_policy") != policy:
        errors.append(
            "templates/project-config.example.json execution policy must match distribution defaults"
        )

    cases_path = ROOT / "evals/execution-broker-cases.json"
    cases_payload = validate_json(cases_path, errors)
    cases = cases_payload.get("cases") if isinstance(cases_payload, dict) else None
    if (
        not isinstance(cases_payload, dict)
        or cases_payload.get("schema_version") != 1
        or not isinstance(cases, list)
        or len(cases) < 7
    ):
        errors.append(f"{cases_path.relative_to(ROOT)}: at least seven versioned cases are required")
    else:
        seen: set[str] = set()
        expected_fields = {
            "model_tier",
            "reasoning",
            "max_parallel",
            "roles",
            "one_writer",
            "context_budget",
            "repository_scope",
            "write",
            "shell",
            "network",
            "dependency_changes",
            "checkpoint",
            "isolation",
            "max_iterations",
            "verification",
            "proof",
            "compatibility_depth",
            "decision",
            "platform",
            "surface",
            "control_plane",
        }
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                errors.append(f"{cases_path.relative_to(ROOT)}: case {index} must be an object")
                continue
            case_id = str(case.get("id", "")).strip()
            if not case_id or case_id in seen:
                errors.append(f"{cases_path.relative_to(ROOT)}: duplicate or missing id {case_id!r}")
            seen.add(case_id)
            if case.get("effort") not in PK_EFFORTS or case.get("risk") not in PK_RISKS:
                errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} has invalid effort/risk")
            for field in ("traits", "constraints"):
                values = case.get(field)
                if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                    errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} has invalid {field}")
            expected = case.get("expected")
            if not isinstance(expected, dict) or set(expected) != expected_fields:
                errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} expected policy is incomplete")

    broker_source = (ROOT / "powerkit/broker.py").read_text(encoding="utf-8")
    for model_fragment in ('"gpt-', "'gpt-", '"claude-', "'claude-"):
        if model_fragment in broker_source:
            errors.append(
                "powerkit/broker.py: vendor model identifiers belong in platform adapters"
            )
            break


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


def validate_pk_command(known_skills: set[str], errors: list[str]) -> None:
    command_root = ROOT / ".agents/skills/pk"
    skill_path = command_root / "SKILL.md"
    routing_path = command_root / "references/routing.md"
    modes_path = command_root / "references/modes.md"
    manifest_path = command_root / "references/command-manifest.json"
    cases_path = command_root / "evals/routing-cases.json"

    manifest = validate_json(manifest_path, errors)
    if not isinstance(manifest, dict):
        return
    if manifest.get("schema_version") != 1:
        errors.append(f"{manifest_path.relative_to(ROOT)}: schema_version must be 1")
    if manifest.get("command") != "pk":
        errors.append(f"{manifest_path.relative_to(ROOT)}: command must be 'pk'")
    if manifest.get("default_mode") != "auto" or manifest.get("help_mode") != "help":
        errors.append(
            f"{manifest_path.relative_to(ROOT)}: default_mode/help_mode must be auto/help"
        )
    global_skills = manifest.get("global_skills")
    if global_skills != ["prompt-preflight", "workload-router"]:
        errors.append(
            f"{manifest_path.relative_to(ROOT)}: global_skills must be prompt-preflight and "
            "workload-router"
        )
    completion = manifest.get("completion")
    proof_reference = command_root / "references/proof-pack.md"
    broker_reference = command_root / "references/execution-broker.md"
    expected_outputs = {
        "FAST": ["completion-brief"],
        "STANDARD": ["completion-brief", "proof.json"],
        "DEEP": ["completion-brief", "proof.json", "report.html"],
        "HIGH_RISK": [
            "completion-brief",
            "proof.json",
            "report.html",
            "independent-verification",
        ],
    }
    if (
        not isinstance(completion, dict)
        or completion.get("reference") != "references/proof-pack.md"
        or completion.get("outputs_by_depth") != expected_outputs
    ):
        errors.append(f"{manifest_path.relative_to(ROOT)}: completion policy is invalid")
    if not proof_reference.is_file():
        errors.append(f"{proof_reference.relative_to(ROOT)}: proof completion reference is missing")
    elif skill_path.is_file() and "references/proof-pack.md" not in skill_path.read_text(
        encoding="utf-8"
    ):
        errors.append(f"{skill_path.relative_to(ROOT)}: must route completion to proof-pack.md")
    broker_contract = manifest.get("execution_broker")
    expected_broker = {
        "reference": "references/execution-broker.md",
        "resolve_command": "powerkit broker explain",
        "capabilities_command": "powerkit broker capabilities",
        "launch_command": "powerkit broker launch",
        "effort": ["FAST", "STANDARD", "DEEP"],
        "risk": ["NORMAL", "ELEVATED", "HIGH"],
        "high_risk_compatibility_depth": "HIGH_RISK",
    }
    if broker_contract != expected_broker:
        errors.append(f"{manifest_path.relative_to(ROOT)}: execution broker contract is invalid")
    if not broker_reference.is_file():
        errors.append(f"{broker_reference.relative_to(ROOT)}: execution broker reference is missing")
    elif skill_path.is_file():
        skill_text = skill_path.read_text(encoding="utf-8")
        if "powerkit broker explain" not in skill_text or "references/execution-broker.md" not in skill_text:
            errors.append(
                f"{skill_path.relative_to(ROOT)}: must invoke and progressively disclose the broker"
            )

    modes = manifest.get("modes")
    if not isinstance(modes, dict) or set(modes) != PK_MODES:
        found = sorted(modes) if isinstance(modes, dict) else []
        errors.append(
            f"{manifest_path.relative_to(ROOT)}: expected modes {sorted(PK_MODES)}, found {found}"
        )
    elif isinstance(modes, dict):
        for mode, payload in modes.items():
            if not isinstance(payload, dict):
                errors.append(f"{manifest_path.relative_to(ROOT)}: mode {mode} must be an object")
                continue
            primary = payload.get("primary_skills")
            conditional = payload.get("conditional_skills")
            for key, values in (("primary_skills", primary), ("conditional_skills", conditional)):
                if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                    errors.append(
                        f"{manifest_path.relative_to(ROOT)}: mode {mode} {key} must be a string list"
                    )
                    continue
                unknown = sorted(set(values) - known_skills)
                if unknown:
                    errors.append(
                        f"{manifest_path.relative_to(ROOT)}: mode {mode} references unknown skills: "
                        f"{', '.join(unknown)}"
                    )
            if isinstance(primary, list) and isinstance(conditional, list):
                overlap = sorted(set(primary) & set(conditional))
                if overlap:
                    errors.append(
                        f"{manifest_path.relative_to(ROOT)}: mode {mode} duplicates skills: "
                        f"{', '.join(overlap)}"
                    )
                global_overlap = sorted((set(primary) | set(conditional)) & set(global_skills or []))
                if global_overlap:
                    errors.append(
                        f"{manifest_path.relative_to(ROOT)}: mode {mode} repeats global skills: "
                        f"{', '.join(global_overlap)}"
                    )

    adapters = manifest.get("adapters")
    if not isinstance(adapters, dict) or set(adapters) != {"codex", "claude", "copilot"}:
        errors.append(
            f"{manifest_path.relative_to(ROOT)}: adapters must cover codex, claude, and copilot"
        )
    else:
        expected_invocations = {"codex": "$pk", "claude": "/pk", "copilot": "/pk"}
        expected_skill_roots = {
            "codex": (".agents/skills", ".agents/skills"),
            "claude": (".claude/skills", ".claude/skills"),
            "copilot": (".agents/skills", ".agents/skills"),
        }
        for platform, invocation in expected_invocations.items():
            payload = adapters.get(platform)
            if not isinstance(payload, dict) or payload.get("invocation") != invocation:
                errors.append(
                    f"{manifest_path.relative_to(ROOT)}: {platform} invocation must be {invocation}"
                )
                continue
            expected_project, expected_user = expected_skill_roots[platform]
            if (
                payload.get("project_skill_root") != expected_project
                or payload.get("user_skill_root") != expected_user
            ):
                errors.append(
                    f"{manifest_path.relative_to(ROOT)}: {platform} skill roots are inconsistent"
                )
        codex = adapters.get("codex", {})
        claude = adapters.get("claude", {})
        if isinstance(codex, dict) and codex.get("literal_slash") is not False:
            errors.append(
                f"{manifest_path.relative_to(ROOT)}: Codex must document non-literal slash support"
            )
        if isinstance(claude, dict) and claude.get("literal_slash") is not True:
            errors.append(
                f"{manifest_path.relative_to(ROOT)}: Claude must document literal slash support"
            )
        copilot = adapters.get("copilot", {})
        if isinstance(copilot, dict):
            if copilot.get("user_invocation") != "ask Copilot to use the pk skill":
                errors.append(
                    f"{manifest_path.relative_to(ROOT)}: Copilot user-scope invocation is invalid"
                )
            source_value = copilot.get("project_prompt_source")
            destination = copilot.get("project_prompt_destination")
            if not isinstance(source_value, str):
                errors.append(
                    f"{manifest_path.relative_to(ROOT)}: Copilot project prompt source is required"
                )
            else:
                source = ROOT / source_value
                if not source.is_file():
                    errors.append(f"{source_value}: Copilot command adapter is missing")
                else:
                    text = source.read_text(encoding="utf-8")
                    if MANAGED_MARKER not in text:
                        errors.append(f"{source_value}: missing managed installer marker")
                    if "../../.agents/skills/pk/SKILL.md" not in text:
                        errors.append(f"{source_value}: must reference the canonical pk skill")
                    if len(text.splitlines()) > 40:
                        errors.append(f"{source_value}: command adapter must stay thin")
            if destination != ".github/prompts/pk.prompt.md":
                errors.append(
                    f"{manifest_path.relative_to(ROOT)}: unexpected Copilot prompt destination"
                )

    if skill_path.is_file() and len(skill_path.read_text(encoding="utf-8").splitlines()) > 200:
        errors.append(f"{skill_path.relative_to(ROOT)}: command entrypoint must stay under 200 lines")
    if not routing_path.is_file():
        errors.append(f"{routing_path.relative_to(ROOT)}: routing reference is missing")
    elif len(routing_path.read_text(encoding="utf-8").splitlines()) > 300:
        errors.append(f"{routing_path.relative_to(ROOT)}: routing reference is too large")
    elif "[modes.md](modes.md)" not in routing_path.read_text(encoding="utf-8"):
        errors.append(f"{routing_path.relative_to(ROOT)}: conditional mode reference is missing")
    if not modes_path.is_file():
        errors.append(f"{modes_path.relative_to(ROOT)}: mode composition reference is missing")

    routing_cases = validate_json(cases_path, errors)
    if not isinstance(routing_cases, dict):
        return
    if routing_cases.get("schema_version") != 1 or routing_cases.get("command") != "pk":
        errors.append(f"{cases_path.relative_to(ROOT)}: invalid schema_version or command")
    cases = routing_cases.get("cases")
    if not isinstance(cases, list) or len(cases) < len(PK_ROUTING_CATEGORIES):
        errors.append(
            f"{cases_path.relative_to(ROOT)}: at least {len(PK_ROUTING_CATEGORIES)} cases are required"
        )
        return

    seen_ids: set[str] = set()
    seen_categories: set[str] = set()
    seen_modes: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"{cases_path.relative_to(ROOT)}: case {index} must be an object")
            continue
        case_id = str(case.get("id", "")).strip()
        category = str(case.get("category", "")).strip()
        mode = str(case.get("command_mode", "")).strip()
        if not case_id or case_id in seen_ids:
            errors.append(f"{cases_path.relative_to(ROOT)}: missing or duplicate case id {case_id!r}")
        seen_ids.add(case_id)
        seen_categories.add(category)
        seen_modes.add(mode)
        if not str(case.get("invocation", "")).strip():
            errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} invocation is required")
        if mode not in PK_MODES:
            errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} has invalid command_mode")
        if case.get("expected_depth") not in PK_DEPTHS:
            errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} has invalid expected_depth")
        if case.get("expected_effort") not in PK_EFFORTS:
            errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} has invalid expected_effort")
        if case.get("expected_risk") not in PK_RISKS:
            errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} has invalid expected_risk")
        if not str(case.get("expected_intent", "")).strip():
            errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} expected_intent is required")
        deterministic_command = case.get("deterministic_command")
        if deterministic_command is not None and (
            not isinstance(deterministic_command, str) or not deterministic_command.strip()
        ):
            errors.append(
                f"{cases_path.relative_to(ROOT)}: {case_id} deterministic_command must be a string"
            )
        activate = case.get("must_activate")
        reject = case.get("must_not_activate")
        constraints = case.get("preserved_constraints")
        for key, values in (
            ("must_activate", activate),
            ("must_not_activate", reject),
            ("preserved_constraints", constraints),
        ):
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                errors.append(f"{cases_path.relative_to(ROOT)}: {case_id} {key} must be a string list")
        if isinstance(activate, list) and isinstance(reject, list):
            unknown = sorted((set(activate) | set(reject)) - known_skills)
            if unknown:
                errors.append(
                    f"{cases_path.relative_to(ROOT)}: {case_id} references unknown skills: "
                    f"{', '.join(unknown)}"
                )
            overlap = sorted(set(activate) & set(reject))
            if overlap:
                errors.append(
                    f"{cases_path.relative_to(ROOT)}: {case_id} both requires and rejects "
                    f"{', '.join(overlap)}"
                )

    missing_categories = sorted(PK_ROUTING_CATEGORIES - seen_categories)
    if missing_categories:
        errors.append(
            f"{cases_path.relative_to(ROOT)}: missing routing categories: "
            f"{', '.join(missing_categories)}"
        )
    missing_modes = sorted(PK_MODES - seen_modes)
    if missing_modes:
        errors.append(
            f"{cases_path.relative_to(ROOT)}: explicit/automatic mode coverage is missing: "
            f"{', '.join(missing_modes)}"
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

    version = catalog.get("version")
    default_profiles: list[str] | None = None
    distribution_path = ROOT / "manifests" / "powerkit.json"
    distribution = validate_json(distribution_path, errors)
    if isinstance(distribution, dict):
        if distribution.get("powerkit_version") != version:
            errors.append("manifests/powerkit.json version must match catalog.json")
        if distribution.get("bootstrap") != "BOOTSTRAP.md":
            errors.append("manifests/powerkit.json bootstrap must be BOOTSTRAP.md")
        if set(distribution.get("supported_platforms", [])) != {
            "codex",
            "claude",
            "copilot",
        }:
            errors.append("manifests/powerkit.json supported_platforms is invalid")
        commands = distribution.get("commands")
        if not isinstance(commands, dict) or commands.get("context_audit") != "powerkit context audit":
            errors.append("manifests/powerkit.json must expose powerkit context audit")
        context_budgets = distribution.get("context_budgets")
        required_budgets = {
            "always_on_tokens",
            "discovery_tokens",
            "fast_path_tokens",
            "standard_path_tokens",
            "deep_path_tokens",
            "regression_percent",
            "regression_tokens",
        }
        if not isinstance(context_budgets, dict):
            errors.append("manifests/powerkit.json context_budgets is required")
        else:
            if context_budgets.get("policy") not in {"warn", "fail_ci", "disabled"}:
                errors.append("manifests/powerkit.json context_budgets.policy is invalid")
            for key in required_budgets:
                value = context_budgets.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    errors.append(f"manifests/powerkit.json context_budgets.{key} is invalid")
        release = distribution.get("release")
        expected_tag = f"v{version}"
        if not isinstance(release, dict) or release.get("tag") != expected_tag:
            errors.append(f"manifests/powerkit.json release.tag must be {expected_tag}")
        elif f"@{expected_tag}" not in str(release.get("install", "")):
            errors.append("manifests/powerkit.json release.install must pin release.tag")
        default_setup = distribution.get("default_setup")
        candidate_profiles = (
            default_setup.get("profiles") if isinstance(default_setup, dict) else None
        )
        known_profiles = set(catalog.get("profiles", {})) | {"all"}
        if (
            not isinstance(candidate_profiles, list)
            or not candidate_profiles
            or not all(isinstance(profile, str) and profile in known_profiles for profile in candidate_profiles)
        ):
            errors.append("manifests/powerkit.json default_setup.profiles is invalid")
        else:
            default_profiles = candidate_profiles
        commands = distribution.get("commands")
        if not isinstance(commands, dict) or commands.get("proof") != "powerkit proof":
            errors.append("manifests/powerkit.json must expose the proof command")
        if not isinstance(commands, dict) or commands.get("broker") != "powerkit broker":
            errors.append("manifests/powerkit.json must expose the broker command")
        schemas = distribution.get("schemas")
        if not isinstance(schemas, dict) or schemas.get("proof_manifest") != (
            "schemas/proof-manifest.schema.json"
        ):
            errors.append("manifests/powerkit.json must expose the proof manifest schema")
        if not isinstance(schemas, dict) or schemas.get("execution_broker") != (
            "schemas/execution-broker-v1.schema.json"
        ):
            errors.append("manifests/powerkit.json must expose the execution broker schema")
        for relative in ("bootstrap",):
            target = distribution.get(relative)
            if isinstance(target, str) and not (ROOT / target).is_file():
                errors.append(f"manifests/powerkit.json references missing {target}")

    bootstrap_path = ROOT / "BOOTSTRAP.md"
    if not bootstrap_path.is_file():
        errors.append("BOOTSTRAP.md is missing")
    else:
        bootstrap = bootstrap_path.read_text(encoding="utf-8")
        for required in (
            "manifests/powerkit.json",
            ".ai-powerkit/project.json",
            ".ai-powerkit/install-manifest.json",
            "python3 -m powerkit",
            "powerkit doctor",
        ):
            if required not in bootstrap:
                errors.append(f"BOOTSTRAP.md must reference {required}")
        if len(bootstrap.splitlines()) > 180:
            warnings.append("BOOTSTRAP.md exceeds 180 lines; keep the agent contract concise")

    pyproject = validate_toml(ROOT / "pyproject.toml", errors)
    if isinstance(pyproject, dict):
        project = pyproject.get("project")
        if not isinstance(project, dict) or project.get("version") != version:
            errors.append("pyproject.toml version must match catalog.json")
        scripts = project.get("scripts") if isinstance(project, dict) else None
        if not isinstance(scripts, dict) or scripts.get("powerkit") != "powerkit.cli:main":
            errors.append("pyproject.toml must expose the powerkit console script")

    project_template = validate_json(ROOT / "templates/project-config.example.json", errors)
    if isinstance(project_template, dict):
        powerkit = project_template.get("powerkit")
        if not isinstance(powerkit, dict) or powerkit.get("version") != version:
            errors.append("templates/project-config.example.json version must match catalog.json")
        elif default_profiles is not None and powerkit.get("profiles") != default_profiles:
            errors.append(
                "templates/project-config.example.json profiles must match distribution defaults"
            )
        proof_config = project_template.get("proof")
        if not isinstance(proof_config, dict) or proof_config.get("output_directory") != (
            ".ai-powerkit/proofs"
        ):
            errors.append(
                "templates/project-config.example.json proof output must be .ai-powerkit/proofs"
            )

    validate_execution_broker(
        distribution if isinstance(distribution, Mapping) else None,
        project_template if isinstance(project_template, Mapping) else None,
        errors,
    )

    proof_schema_path = ROOT / "schemas/proof-manifest.schema.json"
    proof_schema = validate_json(proof_schema_path, errors)
    if isinstance(proof_schema, dict):
        properties = proof_schema.get("properties")
        schema_version = properties.get("schema_version") if isinstance(properties, dict) else None
        required = proof_schema.get("required")
        required_fields = {
            "task",
            "outcome",
            "verification",
            "verification_evidence",
            "source_snapshot",
            "privacy",
            "presentation",
        }
        if not isinstance(schema_version, dict) or schema_version.get("const") != 1:
            errors.append("schemas/proof-manifest.schema.json must define schema version 1")
        if not isinstance(required, list) or not required_fields <= set(required):
            errors.append("schemas/proof-manifest.schema.json is missing canonical evidence fields")
        if (
            isinstance(distribution, dict)
            and isinstance(powerkit, dict)
            and powerkit.get("context_budgets") != distribution.get("context_budgets")
        ):
            errors.append(
                "templates/project-config.example.json context budgets must match distribution defaults"
            )

    audit_schema = validate_json(ROOT / "schemas/context-audit-v1.schema.json", errors)
    baseline_schema = validate_json(ROOT / "schemas/context-baseline-v1.schema.json", errors)
    if isinstance(audit_schema, dict):
        required = audit_schema.get("required")
        expected = {
            "schema_version",
            "scope",
            "estimator",
            "summary",
            "platforms",
            "artifacts",
            "recommendations",
            "budgets",
            "baseline_comparison",
            "warnings",
            "limitations",
        }
        if not isinstance(required, list) or not expected <= set(required):
            errors.append("schemas/context-audit-v1.schema.json omits required report fields")
    if isinstance(baseline_schema, dict):
        required = baseline_schema.get("required")
        if not isinstance(required, list) or set(required) != {
            "schema_version",
            "powerkit_version",
            "estimator",
            "platforms",
        }:
            errors.append("schemas/context-baseline-v1.schema.json has invalid required fields")

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

    validate_pk_command(discovered_names, errors)

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
    python_sources = (
        list((ROOT / "tools").glob("*.py"))
        + list((ROOT / "hooks").glob("*.py"))
        + list((ROOT / "powerkit").glob("*.py"))
        + [ROOT / "setup.py"]
    )
    for path in python_sources:
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

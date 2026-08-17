"""Deterministic execution policy and platform capability negotiation."""

from __future__ import annotations

import json
import hashlib
import os
import re
import signal
import subprocess
import tempfile
import threading
import unicodedata
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from powerkit.installer import atomic_write_text, ensure_managed_path
from powerkit.privacy import redact_text
from powerkit.proof import VerifiedExecutionPolicy
from powerkit.resources import distribution_manifest, distribution_root
from powerkit.state import load_project_config
from powerkit.verification import repository_fingerprint


SCHEMA_VERSION = 1
EFFORTS = ("FAST", "STANDARD", "DEEP")
RISKS = ("NORMAL", "ELEVATED", "HIGH")
SUPPORT_STATES = ("NATIVE", "PARTIAL", "EMULATED", "UNAVAILABLE")
CONTROL_PLANES = ("CURRENT_SESSION", "LAUNCHER")
COST_PREFERENCES = ("ECONOMY", "BALANCED", "QUALITY")
LATENCY_PREFERENCES = ("FASTEST", "BALANCED", "QUALITY")
MODEL_TIERS = ("ECONOMY", "BALANCED", "STRONG", "MAXIMUM")
REASONING_LEVELS = ("LOW", "MEDIUM", "HIGH", "MAXIMUM")

CONSTRAINTS = (
    "PLAN_ONLY",
    "NO_WRITE",
    "NO_NETWORK",
    "NO_DEPENDENCIES",
    "NO_PARALLEL",
    "NO_SHELL",
    "COST_SENSITIVE",
    "LATENCY_SENSITIVE",
    "STRONGEST_REASONING",
    "BOUNDED_SCOPE",
    "ISOLATION_REQUIRED",
)

TASK_TRAITS = (
    "READ_ONLY",
    "ARCHITECTURE",
    "MIGRATION",
    "RUNTIME",
    "SECURITY_SENSITIVE",
    "AUTHORIZATION",
    "PRIVACY",
    "SECRETS",
    "PRODUCTION_DATA",
    "BILLING",
    "PUBLIC_CONTRACT",
    "DESTRUCTIVE",
    "EXTERNAL_WRITE",
    "DEPENDENCY_CHANGE",
)

CAPABILITY_CONTROLS = (
    "model_selection",
    "reasoning_effort",
    "parallel_agents",
    "agent_roles",
    "context_budget",
    "tool_restriction",
    "filesystem_scope",
    "network_restriction",
    "shell_restriction",
    "max_iterations",
    "checkpoints",
    "execution_isolation",
    "runtime_browser",
    "usage_telemetry",
    "external_write_gating",
    "mcp_restriction",
)

CONTROL_POLICY_PATHS: dict[str, tuple[str, ...]] = {
    "model_selection": ("intelligence", "model_tier"),
    "reasoning_effort": ("intelligence", "reasoning"),
    "parallel_agents": ("agents", "max_parallel"),
    "agent_roles": ("agents", "roles"),
    "context_budget": ("context", "budget"),
    "tool_restriction": ("permissions", "tool_scope"),
    "filesystem_scope": ("permissions", "write"),
    "network_restriction": ("permissions", "network"),
    "shell_restriction": ("permissions", "shell"),
    "max_iterations": ("limits", "max_iterations"),
    "checkpoints": ("safety", "checkpoint"),
    "execution_isolation": ("safety", "isolation"),
    "runtime_browser": ("verification", "runtime"),
    "usage_telemetry": ("telemetry", "capture"),
    "external_write_gating": ("permissions", "external_writes"),
    "mcp_restriction": ("permissions", "mcp"),
}

SECURITY_TRAITS = {"SECURITY_SENSITIVE", "AUTHORIZATION", "PRIVACY", "SECRETS"}
HIGH_RISK_TRAITS = SECURITY_TRAITS | {
    "PRODUCTION_DATA",
    "BILLING",
    "PUBLIC_CONTRACT",
    "DESTRUCTIVE",
}
MAX_REASONS = 5
MAX_REASON_CHARS = 200
TRANSLATION_SETTINGS = {
    "codex": {
        "model",
        "agents.default_subagent_model",
        "model_reasoning_effort",
        "agents.default_subagent_reasoning_effort",
        "agents.max_concurrent_threads_per_session",
        "sandbox_mode",
        "features.shell_tool",
        "mcp_servers",
    },
    "claude": {
        "--model",
        "subagent.model",
        "--effort",
        "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS",
        "--permission-mode",
        "--tools",
        "--disallowedTools",
        "--strict-mcp-config",
        "--max-turns",
        "--worktree",
    },
    "copilot": {"--model"},
}


def _enum(value: str, allowed: Sequence[str], label: str) -> str:
    normalized = value.strip().replace("-", "_").upper()
    if normalized not in allowed:
        raise RuntimeError(
            f"Unknown {label}: {value!r}. Expected one of {', '.join(allowed)}."
        )
    return normalized


def _normalized_values(
    values: Iterable[str], allowed: Sequence[str], label: str
) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(_enum(value, allowed, label) for value in values))
    return normalized


def _normalized_reasons(values: Iterable[str]) -> list[str]:
    reasons = [value.strip() for value in values if value.strip()]
    if len(reasons) > MAX_REASONS:
        raise RuntimeError(f"At most {MAX_REASONS} broker reasons may be supplied.")
    for reason in reasons:
        if len(reason) > MAX_REASON_CHARS:
            raise RuntimeError(
                f"Broker reasons must be at most {MAX_REASON_CHARS} characters."
            )
        if any(unicodedata.category(character) in {"Cc", "Cf"} for character in reason):
            raise RuntimeError("Broker reasons must not contain control characters.")
    return [redact_text(reason) for reason in reasons]


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _policy_value(policy: Mapping[str, Any], path: Sequence[str]) -> Any:
    value: Any = policy
    for part in path:
        if not isinstance(value, Mapping) or part not in value:
            raise RuntimeError(f"Execution policy is missing {'.'.join(path)}.")
        value = value[part]
    return value


def _shift(value: str, ordered: Sequence[str], amount: int) -> str:
    index = ordered.index(value)
    return ordered[max(0, min(len(ordered) - 1, index + amount))]


def _client_version_token(output: str) -> str | None:
    match = re.search(r"\b[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?\b", output)
    return match.group(0) if match else None


def default_execution_policy() -> dict[str, Any]:
    payload = distribution_manifest().get("execution_policy")
    if not isinstance(payload, dict):
        raise RuntimeError("PowerKit distribution has no execution_policy defaults.")
    return validate_project_policy(payload)


def validate_project_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "cost_preference",
        "latency_preference",
        "max_parallel_agents",
        "allow_model_upgrade",
        "allow_network",
        "high_risk_requires_checkpoint",
        "iteration_limits",
        "adapter_overrides",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise RuntimeError(
            "Unknown execution_policy fields: " + ", ".join(unknown)
        )

    cost = _enum(
        str(payload.get("cost_preference", "BALANCED")),
        COST_PREFERENCES,
        "cost preference",
    )
    latency = _enum(
        str(payload.get("latency_preference", "BALANCED")),
        LATENCY_PREFERENCES,
        "latency preference",
    )
    max_parallel = payload.get("max_parallel_agents", 4)
    if not isinstance(max_parallel, int) or isinstance(max_parallel, bool) or not 1 <= max_parallel <= 16:
        raise RuntimeError("execution_policy.max_parallel_agents must be an integer from 1 to 16.")
    allow_upgrade = payload.get("allow_model_upgrade", True)
    checkpoint = payload.get("high_risk_requires_checkpoint", True)
    if not isinstance(allow_upgrade, bool) or not isinstance(checkpoint, bool):
        raise RuntimeError(
            "execution_policy model-upgrade and checkpoint settings must be booleans."
        )
    allow_network = _enum(
        str(payload.get("allow_network", "WHEN_REQUIRED")),
        ("NEVER", "WHEN_REQUIRED", "ALLOW"),
        "network policy",
    )

    raw_limits = payload.get("iteration_limits", {"FAST": 4, "STANDARD": 8, "DEEP": 16})
    if not isinstance(raw_limits, Mapping) or set(raw_limits) != set(EFFORTS):
        raise RuntimeError(
            "execution_policy.iteration_limits must define FAST, STANDARD, and DEEP."
        )
    limits: dict[str, int] = {}
    for effort in EFFORTS:
        value = raw_limits.get(effort)
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100:
            raise RuntimeError(
                f"execution_policy.iteration_limits.{effort} must be an integer from 1 to 100."
            )
        limits[effort] = value

    raw_overrides = payload.get("adapter_overrides", {})
    if not isinstance(raw_overrides, Mapping):
        raise RuntimeError("execution_policy.adapter_overrides must be an object.")
    overrides: dict[str, Any] = {}
    for platform, override in raw_overrides.items():
        if platform not in {"codex", "claude", "copilot"} or not isinstance(override, Mapping):
            raise RuntimeError(
                "execution_policy.adapter_overrides keys must be codex, claude, or copilot objects."
            )
        unknown_override = set(override) - {"model_tiers"}
        if unknown_override:
            raise RuntimeError(
                f"Unknown {platform} adapter override fields: "
                + ", ".join(sorted(unknown_override))
            )
        raw_models = override.get("model_tiers", {})
        if not isinstance(raw_models, Mapping):
            raise RuntimeError(f"{platform} model_tiers override must be an object.")
        models: dict[str, str] = {}
        for tier, model in raw_models.items():
            normalized_tier = _enum(str(tier), MODEL_TIERS, "model tier")
            if not isinstance(model, str) or not model.strip():
                raise RuntimeError(
                    f"{platform} model_tiers.{normalized_tier} must be a non-empty string."
                )
            models[normalized_tier] = model.strip()
        overrides[platform] = {"model_tiers": models}

    return {
        "cost_preference": cost,
        "latency_preference": latency,
        "max_parallel_agents": max_parallel,
        "allow_model_upgrade": allow_upgrade,
        "allow_network": allow_network,
        "high_risk_requires_checkpoint": checkpoint,
        "iteration_limits": limits,
        "adapter_overrides": overrides,
    }


def configured_execution_policy(target: Path) -> dict[str, Any]:
    defaults = default_execution_policy()
    config = load_project_config(target, required=False)
    if not config or "execution_policy" not in config:
        return defaults
    configured = config.get("execution_policy")
    if not isinstance(configured, Mapping):
        raise RuntimeError("Project execution_policy must be an object.")
    return validate_project_policy(_deep_merge(defaults, configured))


def capability_manifest_path(platform: str) -> Path:
    normalized = _enum(platform, ("CODEX", "CLAUDE", "COPILOT"), "platform").lower()
    return distribution_root() / "adapters" / normalized / "capabilities.json"


def load_capability_manifest(platform: str) -> dict[str, Any]:
    path = capability_manifest_path(platform)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read platform capability contract: {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported platform capability contract: {path}")
    expected_platform = platform.strip().lower()
    if payload.get("platform") != expected_platform:
        raise RuntimeError(f"Platform capability contract identity mismatch: {path}")
    sources = payload.get("sources")
    defaults = payload.get("defaults")
    surfaces = payload.get("surfaces")
    if (
        not isinstance(sources, dict)
        or not isinstance(defaults, dict)
        or not isinstance(surfaces, dict)
        or not surfaces
    ):
        raise RuntimeError(f"Platform capability contract is incomplete: {path}")
    validated_versions = payload.get("validated_client_versions")
    if (
        not isinstance(validated_versions, list)
        or any(not isinstance(item, str) or not item.strip() for item in validated_versions)
    ):
        raise RuntimeError(
            f"Platform capability contract must define validated_client_versions: {path}"
        )
    default_surface = payload.get("default_surface")
    if default_surface not in surfaces:
        raise RuntimeError(f"Platform capability contract has invalid default surface: {path}")
    for source_id, source in sources.items():
        if (
            not isinstance(source_id, str)
            or not isinstance(source, dict)
            or not isinstance(source.get("title"), str)
            or not isinstance(source.get("url"), str)
            or not source["url"].startswith("https://")
        ):
            raise RuntimeError(f"Platform capability contract has an invalid source: {path}")
    merged_surfaces: dict[str, Any] = {}
    for surface_name, surface in surfaces.items():
        if not isinstance(surface_name, str) or not isinstance(surface, Mapping):
            raise RuntimeError(f"Platform capability contract has an invalid surface: {path}")
        merged = _deep_merge(defaults, surface)
        controls = merged.get("controls")
        if not isinstance(controls, Mapping) or set(controls) != set(CAPABILITY_CONTROLS):
            raise RuntimeError(
                f"{path}: surface {surface_name} must define every broker capability control."
            )
        for control_name, control in controls.items():
            if not isinstance(control, Mapping):
                raise RuntimeError(f"{path}: invalid {surface_name}.{control_name} control.")
            support = _enum(str(control.get("support", "")), SUPPORT_STATES, "capability support")
            support_rank = {"UNAVAILABLE": 0, "EMULATED": 1, "PARTIAL": 2, "NATIVE": 3}
            for plane in ("current_session", "launcher"):
                effective = control.get(plane)
                if not isinstance(effective, Mapping):
                    raise RuntimeError(
                        f"{path}: {surface_name}.{control_name}.{plane} is required."
                    )
                lifecycle = _enum(
                    str(effective.get("state", "")), SUPPORT_STATES, "effective support"
                )
                if support_rank[lifecycle] > support_rank[support]:
                    raise RuntimeError(
                        f"{path}: {surface_name}.{control_name}.{plane} exceeds overall support."
                    )
                if not isinstance(effective.get("origin"), str) or not isinstance(
                    effective.get("detail"), str
                ):
                    raise RuntimeError(
                        f"{path}: {surface_name}.{control_name}.{plane} is incomplete."
                    )
            source_ids = control.get("source_ids", [])
            if (
                not isinstance(source_ids, list)
                or not source_ids
                or any(not isinstance(item, str) or item not in sources for item in source_ids)
            ):
                raise RuntimeError(
                    f"{path}: {surface_name}.{control_name} references unknown sources."
                )
        translations = merged.get("translations", [])
        if not isinstance(translations, list):
            raise RuntimeError(f"{path}: {surface_name} translations must be a list.")
        seen_translations: set[tuple[str, str]] = set()
        for index, translation in enumerate(translations):
            if not isinstance(translation, Mapping):
                raise RuntimeError(
                    f"{path}: {surface_name}.translations[{index}] must be an object."
                )
            translated_control = translation.get("control")
            setting = translation.get("setting")
            applies_to = translation.get("applies_to")
            if translated_control not in CAPABILITY_CONTROLS:
                raise RuntimeError(
                    f"{path}: {surface_name}.translations[{index}] has an invalid control."
                )
            if not isinstance(setting, str) or not setting.strip():
                raise RuntimeError(
                    f"{path}: {surface_name}.translations[{index}] requires a setting."
                )
            if setting not in TRANSLATION_SETTINGS[expected_platform]:
                raise RuntimeError(
                    f"{path}: {surface_name}.translations[{index}] has an unsupported setting."
                )
            if applies_to not in {"LAUNCHER", "CURRENT_SESSION", "SUBAGENT"}:
                raise RuntimeError(
                    f"{path}: {surface_name}.translations[{index}] has invalid applies_to."
                )
            translation_key = (str(translated_control), str(applies_to))
            if translation_key in seen_translations:
                raise RuntimeError(
                    f"{path}: {surface_name} has a duplicate control/lifecycle translation."
                )
            seen_translations.add(translation_key)
            values = translation.get("values")
            requires_override = translation.get("requires_override", False)
            if not isinstance(requires_override, bool):
                raise RuntimeError(
                    f"{path}: {surface_name}.translations[{index}].requires_override must be boolean."
                )
            if values is not None:
                if not isinstance(values, Mapping) or not values:
                    raise RuntimeError(
                        f"{path}: {surface_name}.translations[{index}].values must be a non-empty object."
                    )
                allowed_values = {
                    "model_selection": set(MODEL_TIERS),
                    "reasoning_effort": set(REASONING_LEVELS),
                    "filesystem_scope": {"READ_ONLY", "SCOPED_WRITE", "NARROW_SCOPED_WRITE"},
                    "shell_restriction": {"DENY", "READ_ONLY", "SCOPED"},
                    "execution_isolation": {"NORMAL", "PREFERRED", "REQUIRED"},
                }.get(str(translated_control))
                if allowed_values is not None and not set(values) <= allowed_values:
                    raise RuntimeError(
                        f"{path}: {surface_name}.translations[{index}] has invalid value keys."
                    )
        merged_surfaces[surface_name] = merged
    result = dict(payload)
    result["surfaces"] = merged_surfaces
    return result


def capability_surface(platform: str, surface: str | None = None) -> tuple[dict[str, Any], str, dict[str, Any]]:
    manifest = load_capability_manifest(platform)
    selected = surface or str(manifest["default_surface"])
    if selected not in manifest["surfaces"]:
        raise RuntimeError(
            f"Unknown {platform} surface {selected!r}. Expected one of "
            + ", ".join(sorted(manifest["surfaces"]))
            + "."
        )
    return manifest, selected, manifest["surfaces"][selected]


def _fallback_capability_surface(
    platform: str, surface: str | None, failure: RuntimeError
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    defaults = {"codex": "app", "claude": "cli", "copilot": "cli"}
    known = {
        "codex": {"app", "cli", "cloud"},
        "claude": {"cli"},
        "copilot": {"cli", "ide", "coding-agent", "sdk"},
    }
    selected = surface or defaults[platform]
    if selected not in known[platform]:
        raise RuntimeError(
            f"Unknown {platform} surface {selected!r}. Expected one of "
            + ", ".join(sorted(known[platform]))
            + "."
        )
    detail = (
        "Capability contract unavailable; only behavioral guidance is known. "
        f"Original error: {failure}"
    )
    controls = {
        name: {
            "support": "EMULATED",
            "summary": detail,
            "source_ids": [],
            "current_session": {
                "state": "EMULATED",
                "origin": "behavioral_fallback",
                "detail": detail,
            },
            "launcher": {
                "state": "EMULATED",
                "origin": "behavioral_fallback",
                "detail": detail,
            },
        }
        for name in CAPABILITY_CONTROLS
    }
    surface_payload = {
        "label": f"{selected} (capability fallback)",
        "validation": "FALLBACK",
        "validation_detail": detail,
        "controls": controls,
        "translations": [],
    }
    manifest = {
        "platform": platform,
        "display_name": platform.title(),
        "default_surface": defaults[platform],
        "last_verified": "1970-01-01",
        "sources": {},
        "surfaces": {selected: surface_payload},
    }
    return manifest, selected, surface_payload


def _base_policy(effort: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    bases = {
        "FAST": {
            "model_tier": "ECONOMY",
            "reasoning": "LOW",
            "max_parallel": 1,
            "context_budget": "MINIMAL",
            "repository_scope": "LOCAL",
            "verification": "TARGETED",
            "runtime": "WHEN_RELEVANT",
            "proof": "BRIEF",
        },
        "STANDARD": {
            "model_tier": "BALANCED",
            "reasoning": "MEDIUM",
            "max_parallel": 2,
            "context_budget": "FOCUSED",
            "repository_scope": "SUBSYSTEM",
            "verification": "STANDARD",
            "runtime": "WHEN_RELEVANT",
            "proof": "STANDARD",
        },
        "DEEP": {
            "model_tier": "STRONG",
            "reasoning": "HIGH",
            "max_parallel": 4,
            "context_budget": "EXPANDED",
            "repository_scope": "CROSS_CUTTING",
            "verification": "DEEP",
            "runtime": "WHEN_RELEVANT",
            "proof": "RICH",
        },
    }
    base = deepcopy(bases[effort])
    base["max_parallel"] = min(base["max_parallel"], int(policy["max_parallel_agents"]))
    return base


def _apply_preferences(base: dict[str, Any], project: Mapping[str, Any]) -> None:
    cost = str(project["cost_preference"])
    latency = str(project["latency_preference"])
    if cost == "ECONOMY":
        base["model_tier"] = _shift(base["model_tier"], MODEL_TIERS, -1)
        base["reasoning"] = _shift(base["reasoning"], REASONING_LEVELS, -1)
        base["max_parallel"] = min(base["max_parallel"], 2)
    elif cost == "QUALITY":
        base["model_tier"] = _shift(base["model_tier"], MODEL_TIERS, 1)
        base["reasoning"] = _shift(base["reasoning"], REASONING_LEVELS, 1)
    if latency == "FASTEST":
        base["model_tier"] = _shift(base["model_tier"], MODEL_TIERS, -1)
        base["max_parallel"] = min(
            int(project["max_parallel_agents"]), base["max_parallel"] + 1
        )
    elif latency == "QUALITY":
        base["model_tier"] = _shift(base["model_tier"], MODEL_TIERS, 1)


def _canonical_policy(
    effort: str,
    risk: str,
    traits: tuple[str, ...],
    constraints: tuple[str, ...],
    project: Mapping[str, Any],
) -> tuple[dict[str, Any], str, tuple[str, ...]]:
    trait_set = set(traits)
    constraint_set = set(constraints)
    escalations: list[str] = []
    effective_risk = risk
    if trait_set & HIGH_RISK_TRAITS and effective_risk != "HIGH":
        effective_risk = "HIGH"
        escalations.append("risk raised to HIGH by consequence-bearing task traits")
    elif (
        trait_set & {"MIGRATION", "EXTERNAL_WRITE", "DEPENDENCY_CHANGE"}
        and effective_risk == "NORMAL"
    ):
        effective_risk = "ELEVATED"
        escalations.append("risk raised to ELEVATED by task traits")

    active_project = dict(project)
    if "COST_SENSITIVE" in constraint_set:
        active_project["cost_preference"] = "ECONOMY"
        active_project["allow_model_upgrade"] = False
    if "LATENCY_SENSITIVE" in constraint_set:
        active_project["latency_preference"] = "FASTEST"

    base = _base_policy(effort, active_project)
    _apply_preferences(base, active_project)
    if effort == "FAST":
        base["max_parallel"] = 1
    if "STRONGEST_REASONING" in constraint_set:
        base["model_tier"] = "MAXIMUM"
        base["reasoning"] = "MAXIMUM"
        active_project["allow_model_upgrade"] = True

    roles: list[str] = []
    read_only = bool(
        trait_set & {"READ_ONLY"}
        or constraint_set & {"PLAN_ONLY", "NO_WRITE"}
    )
    if read_only:
        roles.append("evidence-explorer")
    else:
        roles.append("bounded-implementer")
    if effort == "DEEP" and "evidence-explorer" not in roles:
        roles.insert(0, "evidence-explorer")
    if trait_set & {"ARCHITECTURE", "MIGRATION", "PUBLIC_CONTRACT"}:
        roles.append("system-architect")
    if "RUNTIME" in trait_set:
        roles.append("runtime-ui-observer")

    independent = effort == "DEEP" or effective_risk == "HIGH"
    adversarial = bool(
        effort == "DEEP"
        and trait_set & {"ARCHITECTURE", "MIGRATION", "PUBLIC_CONTRACT"}
    ) or bool(trait_set & SECURITY_TRAITS)
    if independent:
        roles.append("independent-verifier")
    if adversarial:
        roles.append("adversarial-critic")
    roles = list(dict.fromkeys(roles))

    max_parallel = int(base["max_parallel"])
    if "NO_PARALLEL" in constraint_set:
        max_parallel = 1

    verification = str(base["verification"])
    if effective_risk == "ELEVATED" and verification == "TARGETED":
        verification = "STANDARD"
    if effective_risk == "HIGH":
        verification = "DEEP"

    write = "READ_ONLY" if read_only else "SCOPED_WRITE"
    repository_scope = str(base["repository_scope"])
    if effective_risk == "HIGH":
        write = "READ_ONLY" if read_only else "NARROW_SCOPED_WRITE"
        repository_scope = "RISK_RELEVANT"
    if "BOUNDED_SCOPE" in constraint_set:
        repository_scope = "BOUNDED"

    network_policy = str(active_project["allow_network"])
    network = {
        "NEVER": "DENY",
        "WHEN_REQUIRED": "DENY_UNLESS_REQUIRED",
        "ALLOW": "WHEN_REQUIRED",
    }[network_policy]
    if "NO_NETWORK" in constraint_set:
        network = "DENY"

    shell = "READ_ONLY" if read_only else "SCOPED"
    if constraint_set & {"NO_SHELL", "NO_WRITE", "PLAN_ONLY"}:
        shell = "DENY"
    external_writes = "DENY" if read_only else "CONFIRM"
    destructive = "DENY" if read_only else "CONFIRM"
    dependencies = "DENY" if read_only else "CONFIRM"
    if "NO_DEPENDENCIES" in constraint_set:
        dependencies = "DENY"

    checkpoint = bool(
        (effective_risk == "HIGH" and active_project["high_risk_requires_checkpoint"])
        or trait_set & {"DESTRUCTIVE", "EXTERNAL_WRITE", "MIGRATION"}
    )
    isolation = "PREFERRED" if effective_risk == "HIGH" else "NORMAL"
    if "ISOLATION_REQUIRED" in constraint_set:
        isolation = "REQUIRED"
    rollback = bool(trait_set & {"DESTRUCTIVE", "MIGRATION"})
    runtime = "REQUIRED" if "RUNTIME" in trait_set else str(base["runtime"])
    proof_depth = "HIGH_RISK" if effective_risk == "HIGH" else effort
    proof = "HIGH_RISK" if effective_risk == "HIGH" else str(base["proof"])
    tool_scope = "READ_ONLY" if read_only else (
        "LEAST_PRIVILEGE" if effective_risk == "HIGH" else "TASK_SCOPED"
    )
    mcp = "DENY" if constraint_set & {"NO_NETWORK", "NO_WRITE", "PLAN_ONLY"} else (
        "LEAST_PRIVILEGE" if effective_risk == "HIGH" or read_only else "TASK_SCOPED"
    )

    canonical = {
        "intelligence": {
            "model_tier": str(base["model_tier"]),
            "reasoning": str(base["reasoning"]),
            "allow_model_upgrade": bool(active_project["allow_model_upgrade"]),
        },
        "agents": {
            "max_parallel": max_parallel,
            "roles": roles,
            "one_writer": True,
            "independent_verifier": independent,
            "adversarial_critic": adversarial,
        },
        "context": {
            "budget": str(base["context_budget"]),
            "repository_scope": repository_scope,
            "provider_hard_limit": False,
        },
        "permissions": {
            "tool_scope": tool_scope,
            "write": write,
            "shell": shell,
            "network": network,
            "mcp": mcp,
            "external_writes": external_writes,
            "destructive_actions": destructive,
            "dependency_changes": dependencies,
        },
        "verification": {
            "depth": verification,
            "runtime": runtime,
            "security": bool(trait_set & SECURITY_TRAITS),
            "independent": independent,
        },
        "safety": {
            "checkpoint": checkpoint,
            "isolation": isolation,
            "rollback": rollback,
        },
        "proof": {"depth": proof, "compatibility_depth": proof_depth},
        "limits": {"max_iterations": int(active_project["iteration_limits"][effort])},
        "telemetry": {"capture": "OBSERVE_WHEN_AVAILABLE"},
    }
    return canonical, effective_risk, tuple(escalations)


def _effective_controls(
    desired: Mapping[str, Any],
    surface: Mapping[str, Any],
    control_plane: str,
    settings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    plane_key = "current_session" if control_plane == "CURRENT_SESSION" else "launcher"
    configurable = set(CAPABILITY_CONTROLS) - {
        "agent_roles",
        "checkpoints",
        "runtime_browser",
        "external_write_gating",
    }
    result: dict[str, Any] = {}
    for name in CAPABILITY_CONTROLS:
        capability = surface["controls"][name]
        selected = capability[plane_key]
        availability_state = selected["state"]
        matching = [setting for setting in settings if setting.get("control") == name]
        if availability_state == "UNAVAILABLE":
            state = "UNAVAILABLE"
            application = "UNAVAILABLE"
        elif matching:
            state = availability_state
            application = (
                "SUBAGENT_SETTING"
                if all(setting.get("applies_to") == "subagent" for setting in matching)
                else "SETTING_AVAILABLE"
            )
        elif availability_state == "NATIVE":
            state = "PARTIAL"
            application = "UNMAPPED"
        elif name in configurable:
            state = availability_state
            application = "WORKFLOW_FALLBACK"
        else:
            state = availability_state
            application = "SELECT_AT_USE"
        requested = _policy_value(desired, CONTROL_POLICY_PATHS[name])
        if isinstance(requested, tuple):
            requested = list(requested)
        result[name] = {
            "requested": requested,
            "platform_support": capability["support"],
            "availability_state": availability_state,
            "state": state,
            "origin": selected["origin"],
            "application": application,
            "enforcement_status": "NOT_APPLIED",
            "detail": selected["detail"],
            "source_ids": list(capability.get("source_ids", [])),
        }
    return result


def _native_settings(
    desired: Mapping[str, Any],
    platform: str,
    surface: Mapping[str, Any],
    control_plane: str,
    project: Mapping[str, Any],
) -> list[dict[str, Any]]:
    settings: list[dict[str, Any]] = []
    allow_upgrade = bool(desired["intelligence"]["allow_model_upgrade"])
    model_overrides = (
        project.get("adapter_overrides", {})
        .get(platform, {})
        .get("model_tiers", {})
    )
    for translation in surface.get("translations", []):
        if not isinstance(translation, Mapping):
            continue
        control = str(translation.get("control", ""))
        if control not in CAPABILITY_CONTROLS:
            continue
        applies_to = str(translation.get("applies_to", "LAUNCHER")).upper()
        if applies_to == "LAUNCHER" and control_plane != "LAUNCHER":
            continue
        if applies_to == "CURRENT_SESSION" and control_plane != "CURRENT_SESSION":
            continue
        if control == "model_selection" and not allow_upgrade:
            continue
        requested = _policy_value(desired, CONTROL_POLICY_PATHS[control])
        if (
            translation.get("requires_override", False)
            and str(requested) not in model_overrides
        ):
            continue
        values = translation.get("values")
        value = values.get(str(requested)) if isinstance(values, Mapping) else requested
        if control == "model_selection" and str(requested) in model_overrides:
            value = model_overrides[str(requested)]
        if value is None:
            continue
        settings.append(
            {
                "control": control,
                "setting": str(translation.get("setting", "")),
                "value": value,
                "applies_to": applies_to.lower(),
                "note": str(translation.get("note", "")),
            }
        )
    return settings


def _execution_decision(
    desired: Mapping[str, Any],
    controls: Mapping[str, Any],
    effective_risk: str,
    constraints: tuple[str, ...],
    traits: tuple[str, ...],
    control_plane: str,
    capability_status: str,
) -> tuple[str, list[str], list[str], list[str], str | None]:
    blockers: list[str] = []
    caveats: list[str] = []
    checkpoint_reasons: list[str] = []
    constraint_checkpoint = False
    constraint_set = set(constraints)
    trait_set = set(traits)

    if control_plane == "LAUNCHER" and capability_status != "CONTRACT":
        blockers.append(
            "A local launcher requires a validated capability contract and client version."
        )

    for name, record in controls.items():
        state = record["state"]
        if state in {"EMULATED", "UNAVAILABLE"}:
            caveats.append(
                f"{name.replace('_', ' ')} is {state.lower()} on this surface: {record['detail']}"
            )

    if desired["permissions"]["network"] == "DENY":
        state = controls["network_restriction"]["state"]
        if state != "NATIVE":
            source = (
                "explicit no-network constraint"
                if "NO_NETWORK" in constraint_set
                else "project network policy"
            )
            blockers.append(
                f"The {source} cannot be completely enforced on the selected surface."
            )
    hard_constraint_controls = {
        "PLAN_ONLY": (
            "filesystem_scope",
            "tool_restriction",
            "external_write_gating",
            "mcp_restriction",
        ),
        "NO_WRITE": (
            "filesystem_scope",
            "tool_restriction",
            "external_write_gating",
            "mcp_restriction",
        ),
        "NO_SHELL": ("shell_restriction",),
    }
    for constraint, control_names in hard_constraint_controls.items():
        if constraint not in constraint_set:
            continue
        unavailable = [
            name for name in control_names if controls[name]["state"] == "UNAVAILABLE"
        ]
        incomplete = [
            name for name in control_names if controls[name]["state"] != "NATIVE"
        ]
        if "filesystem_scope" in unavailable:
            blockers.append(
                f"The explicit {constraint} constraint has no credible enforcement path on the selected surface."
            )
        elif incomplete:
            constraint_checkpoint = True
            checkpoint_reasons.append(
                f"Explicit {constraint} has non-native enforcement for: "
                + ", ".join(name.replace("_", " ") for name in incomplete)
                + "."
            )
    if "NO_DEPENDENCIES" in constraint_set:
        constraint_checkpoint = True
        checkpoint_reasons.append(
            "Dependency changes have no universal host-native gate."
        )
    if (
        control_plane == "LAUNCHER"
        and controls["filesystem_scope"]["application"] != "SETTING_AVAILABLE"
    ):
        blockers.append(
            "The requested write scope has no concrete launcher mapping on the selected surface."
        )
    if (
        controls["filesystem_scope"]["origin"] == "behavioral_fallback"
        and desired["permissions"]["write"] != "READ_ONLY"
    ):
        constraint_checkpoint = True
        checkpoint_reasons.append(
            "Capability fallback cannot enforce scoped writes."
        )
    if desired["safety"]["isolation"] == "REQUIRED":
        state = controls["execution_isolation"]["state"]
        if state != "NATIVE":
            blockers.append(
                "Required execution isolation is not natively enforceable on the selected surface."
            )
    if (
        (desired["safety"]["checkpoint"] or constraint_checkpoint)
        and controls["checkpoints"]["state"] == "UNAVAILABLE"
    ):
        blockers.append(
            "A required checkpoint cannot be represented on the selected surface."
        )
    if blockers:
        return "STOP", blockers, caveats, checkpoint_reasons, None
    if desired["safety"]["checkpoint"] or constraint_checkpoint:
        if desired["safety"]["checkpoint"]:
            checkpoint_reasons.append(
                "The selected risk or task traits require approval before consequential mutation."
            )
        return (
            "CHECKPOINT",
            [],
            caveats,
            list(dict.fromkeys(checkpoint_reasons)),
            "before any write, dependency, destructive, external, or otherwise constraint-conflicting action",
        )
    if effective_risk == "HIGH" and any(
        controls[name]["state"] in {"PARTIAL", "EMULATED", "UNAVAILABLE"}
        for name in ("filesystem_scope", "network_restriction", "checkpoints")
    ):
        return (
            "CHECKPOINT",
            [],
            caveats,
            ["High-risk controls are not fully native on the selected surface."],
            "before the first consequential mutation",
        )
    if trait_set & {"DESTRUCTIVE", "EXTERNAL_WRITE"}:
        return (
            "CHECKPOINT",
            [],
            caveats,
            ["A destructive or external-write trait requires explicit approval."],
            "immediately before the destructive or external write",
        )
    return "PROCEED", [], caveats, [], None


def _economic_projection(
    desired: Mapping[str, Any],
    project: Mapping[str, Any],
    constraints: Sequence[str],
) -> dict[str, Any]:
    model_score = MODEL_TIERS.index(str(desired["intelligence"]["model_tier"]))
    reasoning_score = REASONING_LEVELS.index(str(desired["intelligence"]["reasoning"]))
    agent_score = min(3, max(0, int(desired["agents"]["max_parallel"]) - 1))
    cost_score = model_score + reasoning_score + agent_score
    relative_cost = ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")[
        min(3, cost_score // 2)
    ]
    verification_score = {"TARGETED": 0, "STANDARD": 1, "DEEP": 2}[
        str(desired["verification"]["depth"])
    ]
    latency_score = reasoning_score + verification_score
    if int(desired["agents"]["max_parallel"]) == 1 and latency_score >= 3:
        latency_score += 1
    likely_latency = ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")[
        min(3, latency_score // 2)
    ]
    override_impact: list[str] = []
    if project["cost_preference"] != "BALANCED":
        override_impact.append(
            f"cost preference {project['cost_preference']} adjusted intelligence and agent bounds"
        )
    if project["latency_preference"] != "BALANCED":
        override_impact.append(
            f"latency preference {project['latency_preference']} adjusted the resource mix"
        )
    if not project["allow_model_upgrade"]:
        override_impact.append("model upgrades disabled by project or task policy")
    for constraint in constraints:
        if constraint in {
            "NO_NETWORK",
            "NO_DEPENDENCIES",
            "NO_PARALLEL",
            "NO_SHELL",
            "COST_SENSITIVE",
            "LATENCY_SENSITIVE",
            "STRONGEST_REASONING",
            "ISOLATION_REQUIRED",
        }:
            override_impact.append(f"explicit {constraint} constraint preserved")
    return {
        "relative_cost": relative_cost,
        "likely_latency": likely_latency,
        "override_impact": override_impact,
    }


def resolve_policy(
    *,
    effort: str,
    risk: str,
    platform: str,
    surface: str | None = None,
    control_plane: str = "CURRENT_SESSION",
    constraints: Iterable[str] = (),
    traits: Iterable[str] = (),
    project_policy: Mapping[str, Any] | None = None,
    reasons: Iterable[str] = (),
    client_version: str | None = None,
) -> dict[str, Any]:
    normalized_effort = _enum(effort, EFFORTS, "effort")
    normalized_risk = _enum(risk, RISKS, "risk")
    normalized_platform = _enum(platform, ("CODEX", "CLAUDE", "COPILOT"), "platform").lower()
    normalized_plane = _enum(control_plane, CONTROL_PLANES, "control plane")
    normalized_constraints = _normalized_values(constraints, CONSTRAINTS, "constraint")
    normalized_traits = _normalized_values(traits, TASK_TRAITS, "task trait")
    project = validate_project_policy(project_policy or default_execution_policy())
    capability_status = "CONTRACT"
    capability_error: str | None = None
    try:
        manifest, selected_surface, surface_payload = capability_surface(
            normalized_platform, surface
        )
    except RuntimeError as exc:
        if str(exc).startswith(f"Unknown {normalized_platform} surface"):
            raise
        capability_status = "FALLBACK"
        capability_error = str(exc)
        manifest, selected_surface, surface_payload = _fallback_capability_surface(
            normalized_platform, surface, exc
        )
    if capability_status == "CONTRACT" and client_version is not None:
        validated_versions = manifest.get("validated_client_versions", [])
        if client_version not in validated_versions:
            failure = RuntimeError(
                f"Client version {client_version!r} is outside the validated contract set."
            )
            capability_status = "VERSION_MISMATCH"
            capability_error = str(failure)
            manifest, selected_surface, surface_payload = _fallback_capability_surface(
                normalized_platform, surface, failure
            )
    desired, effective_risk, escalations = _canonical_policy(
        normalized_effort,
        normalized_risk,
        normalized_traits,
        normalized_constraints,
        project,
    )
    settings = _native_settings(
        desired,
        normalized_platform,
        surface_payload,
        normalized_plane,
        project,
    )
    controls = _effective_controls(
        desired, surface_payload, normalized_plane, settings
    )
    decision, blockers, caveats, checkpoint_reasons, checkpoint_boundary = _execution_decision(
        desired,
        controls,
        effective_risk,
        normalized_constraints,
        normalized_traits,
        normalized_plane,
        capability_status,
    )
    reason_values = _normalized_reasons(reasons)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "classification": {
            "requested_effort": normalized_effort,
            "requested_risk": normalized_risk,
            "effective_effort": normalized_effort,
            "effective_risk": effective_risk,
            "compatibility_depth": desired["proof"]["compatibility_depth"],
            "escalations": list(escalations),
            "reasons": reason_values,
        },
        "inputs": {
            "constraints": list(normalized_constraints),
            "traits": list(normalized_traits),
            "project_policy": project,
        },
        "platform": {
            "name": normalized_platform,
            "display_name": manifest["display_name"],
            "surface": selected_surface,
            "surface_label": surface_payload["label"],
            "control_plane": normalized_plane,
            "capability_last_verified": manifest["last_verified"],
            "capability_status": capability_status,
            "capability_error": capability_error,
            "client_version": client_version,
        },
        "desired_policy": desired,
        "negotiation": {
            "decision": decision,
            "blocking_reasons": blockers,
            "checkpoint_reasons": checkpoint_reasons,
            "checkpoint_boundary": checkpoint_boundary,
            "caveats": caveats,
            "controls": controls,
            "native_settings": settings,
        },
        "telemetry": {
            "requested": {
                "model_tier": desired["intelligence"]["model_tier"],
                "reasoning": desired["intelligence"]["reasoning"],
                "max_parallel_agents": desired["agents"]["max_parallel"],
                "max_iterations": desired["limits"]["max_iterations"],
            },
            "estimated": {},
            "observed": {},
        },
    }
    if capability_status in {"FALLBACK", "VERSION_MISMATCH"}:
        report["negotiation"]["caveats"].insert(
            0,
            "Platform capability data could not be loaded; no native enforcement is claimed.",
        )
    compact = render_compact_policy(report)
    report["telemetry"]["estimated"] = {
        **_economic_projection(desired, project, normalized_constraints),
        "broker_compact_bytes": len(compact.encode("utf-8")),
        "broker_compact_tokens": (len(compact.encode("utf-8")) + 3) // 4,
        "method": "utf8-bytes-divided-by-four-ceiling",
    }
    return report


def render_compact_policy(report: Mapping[str, Any]) -> str:
    classification = report["classification"]
    desired = report["desired_policy"]
    negotiation = report["negotiation"]
    agents = desired["agents"]
    permissions = desired["permissions"]
    verification = desired["verification"]
    safety = desired["safety"]
    settings = negotiation["native_settings"]
    subagent_settings = [
        f"{item['setting']}={json.dumps(item['value'], separators=(',', ':'))}"
        for item in settings
        if item["applies_to"] == "subagent"
    ]
    critical_controls = ",".join(
        f"{label}:{negotiation['controls'][name]['state']}/"
        f"{negotiation['controls'][name]['enforcement_status']}"
        for label, name in (
            ("fs", "filesystem_scope"),
            ("net", "network_restriction"),
            ("shell", "shell_restriction"),
            ("gate", "checkpoints"),
        )
    )
    negotiated_checkpoint = negotiation["decision"] == "CHECKPOINT" or safety["checkpoint"]
    line = (
        f"{classification['effective_effort']}/{classification['effective_risk']} "
        f"model={desired['intelligence']['model_tier']} "
        f"reason={desired['intelligence']['reasoning']} "
        f"agents={agents['max_parallel']}[{','.join(agents['roles'])}] writer=1 "
        f"independent={int(agents['independent_verifier'])} "
        f"critic={int(agents['adversarial_critic'])} "
        f"context={desired['context']['budget']}/{desired['context']['repository_scope']} "
        f"write={permissions['write']} shell={permissions['shell']} "
        f"net={permissions['network']} tools={permissions['tool_scope']} "
        f"mcp={permissions['mcp']} external={permissions['external_writes']} "
        f"destructive={permissions['destructive_actions']} "
        f"deps={permissions['dependency_changes']} "
        f"turns={desired['limits']['max_iterations']} "
        f"checkpoint={int(negotiated_checkpoint)} "
        f"isolation={safety['isolation']} rollback={int(safety['rollback'])} "
        f"verify={verification['depth']}/{verification['runtime']} "
        f"security={int(verification['security'])} "
        f"proof={desired['proof']['depth']} "
        f"cap={report['platform']['capability_status']} "
        f"controls={critical_controls} decision={negotiation['decision']}"
    )
    if negotiation["blocking_reasons"]:
        line += " blocker=" + " | ".join(negotiation["blocking_reasons"])
    if negotiation.get("checkpoint_reasons"):
        line += " checkpoint=" + " | ".join(negotiation["checkpoint_reasons"])
        line += f" boundary={negotiation['checkpoint_boundary']}"
    if subagent_settings:
        line += " subagent_settings=" + ",".join(subagent_settings)
    return line + "\n"


def render_explanation(report: Mapping[str, Any]) -> str:
    classification = report["classification"]
    desired = report["desired_policy"]
    negotiation = report["negotiation"]
    platform = report["platform"]
    agents = desired["agents"]
    lines = [
        f"PowerKit Execution Policy: {classification['effective_effort']} effort × "
        f"{classification['effective_risk']} risk",
        "",
    ]
    reasons = classification.get("reasons", [])
    escalations = classification.get("escalations", [])
    if reasons or escalations:
        lines.append("Why")
        lines.extend(f"- {reason}" for reason in [*reasons, *escalations])
        lines.append("")
    lines.extend(
        [
            "Resources selected",
            f"- {desired['intelligence']['model_tier'].lower()} model tier; "
            f"{desired['intelligence']['reasoning'].lower()} reasoning",
            f"- Up to {agents['max_parallel']} parallel agent(s); one overlapping writer",
            f"- Roles: {', '.join(agents['roles'])}",
            f"- {desired['context']['budget'].lower()} PowerKit context; "
            f"{desired['context']['repository_scope'].lower()} repository scope",
            f"- {desired['verification']['depth'].lower()} verification; "
            f"{desired['proof']['depth'].lower()} proof",
            "",
            "Permissions and safety",
            f"- Write: {desired['permissions']['write'].lower()}",
            f"- Shell: {desired['permissions']['shell'].lower()}",
            f"- Network: {desired['permissions']['network'].lower()}",
            f"- External writes: {desired['permissions']['external_writes'].lower()}",
            f"- Destructive actions: {desired['permissions']['destructive_actions'].lower()}",
            f"- Dependency changes: {desired['permissions']['dependency_changes'].lower()}",
            f"- Checkpoint: {'required' if desired['safety']['checkpoint'] else 'not required'}",
            f"- Isolation: {desired['safety']['isolation'].lower()}",
            "",
            "Capability negotiation",
            f"- Surface: {platform['display_name']} / {platform['surface_label']}",
            f"- Control plane: {platform['control_plane'].lower()}",
            f"- Decision: {negotiation['decision']}",
        ]
    )
    if negotiation["blocking_reasons"]:
        lines.append("- Blocking reasons:")
        lines.extend(f"  - {reason}" for reason in negotiation["blocking_reasons"])
    if negotiation.get("checkpoint_reasons"):
        lines.append("- Checkpoint reasons:")
        lines.extend(f"  - {reason}" for reason in negotiation["checkpoint_reasons"])
        lines.append(f"- Checkpoint boundary: {negotiation['checkpoint_boundary']}")
    material = [
        (name, record)
        for name, record in negotiation["controls"].items()
        if record["state"] != "NATIVE"
    ]
    if material:
        lines.append("- Not fully native:")
        for name, record in material:
            lines.append(
                f"  - {name.replace('_', ' ')}: {record['state'].lower()} "
                f"({record['origin']})"
            )
    if negotiation["native_settings"]:
        lines.extend(["", "Native adapter settings"])
        for setting in negotiation["native_settings"]:
            lines.append(
                f"- {setting['setting']} = {json.dumps(setting['value'])} "
                f"[{setting['applies_to']}]"
            )
    return "\n".join(lines) + "\n"


def capability_report(
    platforms: Iterable[str] = ("codex", "claude", "copilot"),
    *,
    surface_filters: Mapping[str, Sequence[str]] | None = None,
    probe: bool = False,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for raw_platform in platforms:
        platform = _enum(raw_platform, ("CODEX", "CLAUDE", "COPILOT"), "platform").lower()
        manifest = load_capability_manifest(platform)
        selected_surfaces = (
            tuple(surface_filters.get(platform, ()))
            if surface_filters
            else tuple(manifest["surfaces"])
        )
        if not selected_surfaces:
            selected_surfaces = (str(manifest["default_surface"]),)
        for surface_name in selected_surfaces:
            if surface_name not in manifest["surfaces"]:
                raise RuntimeError(f"Unknown {platform} capability surface: {surface_name}")
            surface = manifest["surfaces"][surface_name]
            entries.append(
                {
                    "platform": platform,
                    "display_name": manifest["display_name"],
                    "surface": surface_name,
                    "surface_label": surface["label"],
                    "last_verified": manifest["last_verified"],
                    "validation": surface.get("validation", "SUPPORTED"),
                    "validation_detail": surface.get(
                        "validation_detail", "No validation detail recorded."
                    ),
                    "controls": {
                        name: {
                            "support": record["support"],
                            "detail": record.get("summary", record["launcher"]["detail"]),
                            "current_session": dict(record["current_session"]),
                            "launcher": dict(record["launcher"]),
                            "source_ids": list(record.get("source_ids", [])),
                        }
                        for name, record in surface["controls"].items()
                    },
                    "sources": manifest["sources"],
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_from": "versioned platform capability contracts",
        "entries": entries,
        "client_probes": probe_clients(platforms) if probe else [],
    }


def render_capability_report(report: Mapping[str, Any]) -> str:
    entries = report["entries"]
    lines = ["PowerKit Execution Capabilities", ""]
    for entry in entries:
        lines.append(f"{entry['display_name']} — {entry['surface_label']}")
        lines.append(
            f"  documented: {entry['last_verified']}  validation: {entry['validation']}"
        )
        lines.append(f"  validation detail: {entry['validation_detail']}")
        for name in CAPABILITY_CONTROLS:
            control = entry["controls"][name]
            lines.append(f"  {name:<24} {control['support']:<11} {control['detail']}")
            lines.append(
                f"    current={control['current_session']['state']} "
                f"({control['current_session']['origin']}); "
                f"launcher={control['launcher']['state']} "
                f"({control['launcher']['origin']})"
            )
        lines.append("")
    probes = report.get("client_probes", [])
    if probes:
        lines.append("Local client probes")
        for probe in probes:
            detail = f" — {probe['detail']}" if probe.get("detail") else ""
            lines.append(
                f"  {probe['platform']:<8} {probe['status']:<24} "
                f"{probe.get('version', '')}{detail}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _probe_candidates(platform: str) -> list[list[str]]:
    known = {
        "codex": [
            Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
            Path("/opt/homebrew/bin/codex"),
            Path("/usr/local/bin/codex"),
        ],
        "claude": [
            Path.home() / ".local/bin/claude",
            Path("/opt/homebrew/bin/claude"),
            Path("/usr/local/bin/claude"),
        ],
        "copilot": [
            Path("/opt/homebrew/bin/copilot"),
            Path("/usr/local/bin/copilot"),
        ],
    }[platform]
    return [
        [str(candidate.resolve()), "--version"]
        for candidate in known
        if candidate.is_file() and os.access(candidate, os.X_OK)
    ]


def _run_version_probe(command: Sequence[str]) -> tuple[int, str, str | None]:
    try:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=tempfile.gettempdir(),
            env={
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "LANG": os.environ.get("LANG", "C.UTF-8"),
            },
            start_new_session=os.name == "posix",
        )
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc
    chunks: list[bytes] = []
    byte_count = 0
    overflow = threading.Event()

    def stop_process_group() -> None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            elif process.poll() is None:
                process.kill()
        except (ProcessLookupError, PermissionError):
            if process.poll() is None:
                process.kill()

    def read_output() -> None:
        nonlocal byte_count
        assert process.stdout is not None
        while True:
            chunk = process.stdout.read(1024)
            if not chunk:
                return
            remaining = 4096 - byte_count
            if remaining > 0:
                chunks.append(chunk[:remaining])
                byte_count += min(len(chunk), remaining)
            if len(chunk) > remaining:
                overflow.set()
                stop_process_group()
                return

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        return_code = process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        stop_process_group()
        process.wait()
        raise
    finally:
        reader.join(timeout=1)
        if reader.is_alive():
            stop_process_group()
            reader.join(timeout=1)
        if process.stdout is not None:
            process.stdout.close()
    output = b"".join(chunks).decode("utf-8", errors="replace")
    return return_code, output, "output exceeded 4096 bytes" if overflow.is_set() else None


def _safe_diagnostic_text(value: str) -> str:
    return "".join(
        f"\\u{ord(character):04x}"
        if character in {"\n", "\r", "\t"}
        or unicodedata.category(character).startswith("C")
        else character
        for character in value
    )


def probe_clients(platforms: Iterable[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for raw_platform in platforms:
        platform = _enum(raw_platform, ("CODEX", "CLAUDE", "COPILOT"), "platform").lower()
        candidates = _probe_candidates(platform)
        if not candidates:
            results.append(
                {
                    "platform": platform,
                    "status": "UNAVAILABLE",
                    "version": "",
                    "detail": "no supported local client command found",
                }
            )
            continue
        errors: list[str] = []
        for command in candidates:
            try:
                return_code, captured, probe_error = _run_version_probe(command)
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{command[0]}: {exc}")
                continue
            output = captured.strip().splitlines()
            if return_code == 0 and probe_error is None:
                version = _safe_diagnostic_text(
                    output[0] if output else "version command succeeded"
                )
                results.append(
                    {
                        "platform": platform,
                        "status": "VERSION_PROBED",
                        "version": version,
                        "command": command,
                        "detail": "allowlisted local client version invocation succeeded; policy controls were not exercised",
                    }
                )
                break
            detail = (
                f"{command[0]} exited {return_code}: "
                + (output[0] if output else "no output")
                + (f" ({probe_error})" if probe_error else "")
            )
            errors.append(_safe_diagnostic_text(detail))
        else:
            results.append(
                {
                    "platform": platform,
                    "status": "PROBE_FAILED",
                    "version": "",
                    "detail": "; ".join(errors),
                }
            )
    return results


def write_trace(target: Path, relative_path: Path, report: Mapping[str, Any]) -> Path:
    if relative_path.is_absolute():
        raise RuntimeError("Broker trace path must be relative to the project.")
    pure = PurePosixPath(relative_path.as_posix())
    if (
        len(pure.parts) < 3
        or pure.parts[:2] != (".ai-powerkit", "traces")
        or any(part in {"", ".", ".."} for part in pure.parts)
        or any(not re.fullmatch(r"[A-Za-z0-9._-]+", part) for part in pure.parts[2:])
        or pure.suffix != ".json"
    ):
        raise RuntimeError(
            "Broker trace path must be a JSON file under .ai-powerkit/traces/."
        )
    destination = target / Path(*pure.parts)
    trace_record = report.get("trace")
    if (
        not isinstance(trace_record, Mapping)
        or trace_record.get("path") != pure.as_posix()
        or not isinstance(trace_record.get("task_id"), str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", trace_record["task_id"])
    ):
        raise RuntimeError("Broker trace requires a matching path and valid task identity.")
    ensure_managed_path(target, destination)
    if destination.is_symlink():
        raise RuntimeError(f"Refusing to replace symlinked broker trace: {destination}")
    atomic_write_text(destination, json.dumps(report, indent=2) + "\n", mode=0o600)
    return destination


def load_trace_binding(
    target: Path,
    relative_path: Path,
    proof_depth: str,
    task_id: str,
) -> VerifiedExecutionPolicy:
    if relative_path.is_absolute():
        raise RuntimeError("Broker trace path must be relative to the project.")
    pure = PurePosixPath(relative_path.as_posix())
    if (
        len(pure.parts) < 3
        or pure.parts[:2] != (".ai-powerkit", "traces")
        or any(part in {"", ".", ".."} for part in pure.parts)
        or any(not re.fullmatch(r"[A-Za-z0-9._-]+", part) for part in pure.parts[2:])
        or pure.suffix != ".json"
    ):
        raise RuntimeError(
            "Broker trace path must be a JSON file under .ai-powerkit/traces/."
        )
    path = target / Path(*pure.parts)
    ensure_managed_path(target, path)
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlinked broker trace: {path}")
    try:
        raw = path.read_bytes()
        report = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid broker trace {path}: {exc}") from exc
    if not isinstance(report, Mapping) or report.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported broker trace: {path}")
    classification = report.get("classification")
    negotiation = report.get("negotiation")
    platform = report.get("platform")
    inputs = report.get("inputs")
    if not all(
        isinstance(item, Mapping)
        for item in (classification, negotiation, platform, inputs)
    ):
        raise RuntimeError(f"Incomplete broker trace: {path}")
    if (
        classification.get("requested_effort") not in EFFORTS
        or classification.get("effective_effort") not in EFFORTS
        or classification.get("requested_risk") not in RISKS
        or classification.get("effective_risk") not in RISKS
        or platform.get("name") not in {"codex", "claude", "copilot"}
        or not isinstance(platform.get("surface"), str)
        or not platform.get("surface")
        or platform.get("control_plane") not in CONTROL_PLANES
    ):
        raise RuntimeError(f"Broker trace classification or platform is invalid: {path}")
    compatibility_depth = classification.get("compatibility_depth")
    if compatibility_depth != proof_depth:
        raise RuntimeError(
            "Proof depth does not match broker compatibility depth: "
            f"{proof_depth} != {compatibility_depth}."
        )
    desired = report.get("desired_policy")
    if (
        not isinstance(desired, Mapping)
        or not isinstance(desired.get("proof"), Mapping)
        or desired["proof"].get("compatibility_depth") != compatibility_depth
    ):
        raise RuntimeError(f"Broker trace proof compatibility is invalid: {path}")
    decision = negotiation.get("decision")
    checkpoint_resolution = "NOT_REQUIRED"
    application_status: str | None = None
    if decision == "CHECKPOINT":
        application = report.get("application")
        if (
            not isinstance(application, Mapping)
            or application.get("checkpoint_acknowledged") is not True
            or application.get("status") != "CLIENT_SUCCEEDED"
        ):
            raise RuntimeError(
                "A CHECKPOINT broker trace requires an acknowledged, successful broker launch before proof."
            )
        checkpoint_resolution = "ACKNOWLEDGED"
        application_status = "CLIENT_SUCCEEDED"
    elif decision != "PROCEED":
        raise RuntimeError(
            f"A {decision or 'malformed'} broker trace cannot authorize a completion proof."
        )
    trace_record = report.get("trace")
    if (
        not isinstance(trace_record, Mapping)
        or trace_record.get("path") != pure.as_posix()
        or trace_record.get("task_id") != task_id
    ):
        raise RuntimeError("Broker trace path or task does not match its embedded trace identity.")

    expected = resolve_policy(
        effort=str(classification["requested_effort"]),
        risk=str(classification["requested_risk"]),
        platform=str(platform["name"]),
        surface=str(platform["surface"]),
        control_plane=str(platform["control_plane"]),
        constraints=inputs.get("constraints", ()),
        traits=inputs.get("traits", ()),
        project_policy=inputs.get("project_policy"),
        reasons=classification.get("reasons", ()),
        client_version=platform.get("client_version"),
    )
    candidate = deepcopy(dict(report))
    candidate.pop("trace", None)
    application = candidate.pop("application", None)
    controls = candidate.get("negotiation", {}).get("controls", {})
    if not isinstance(controls, Mapping):
        raise RuntimeError(f"Broker trace controls are invalid: {path}")
    for record in controls.values():
        if not isinstance(record, dict):
            raise RuntimeError(f"Broker trace control is invalid: {path}")
        record["enforcement_status"] = "NOT_APPLIED"
    if candidate != expected:
        raise RuntimeError(
            "Broker trace does not match deterministic policy resolution."
        )
    if application is not None:
        if not isinstance(application, Mapping):
            raise RuntimeError(f"Broker trace application is invalid: {path}")
        expected_application_fields = {
            "status",
            "platform",
            "client",
            "command_preview",
            "passthrough_arg_count",
            "prompt_transport",
            "local_session_persistence",
            "settings",
            "checkpoint_acknowledged",
            "exit_code",
        }
        settings = application.get("settings")
        expected_settings = {
            (setting["control"], setting["setting"], json.dumps(setting["value"], sort_keys=True))
            for setting in expected["negotiation"]["native_settings"]
            if setting["applies_to"] == "launcher"
        }
        actual_settings = {
            (setting.get("control"), setting.get("setting"), json.dumps(setting.get("value"), sort_keys=True))
            for setting in settings
            if isinstance(setting, Mapping)
        } if isinstance(settings, list) else set()
        if (
            set(application) != expected_application_fields
            or application.get("status") not in {"CLIENT_SUCCEEDED", "CLIENT_FAILED"}
            or application.get("platform") != platform.get("name")
            or not isinstance(application.get("client"), str)
            or not application.get("client")
            or not isinstance(application.get("command_preview"), list)
            or application.get("passthrough_arg_count") != 1
            or application.get("prompt_transport") != "stdin"
            or application.get("local_session_persistence") != "disabled"
            or not isinstance(application.get("checkpoint_acknowledged"), bool)
            or not isinstance(application.get("exit_code"), int)
            or not isinstance(settings, list)
            or actual_settings != expected_settings
            or any(
                not isinstance(setting, Mapping)
                or set(setting) != {"control", "setting", "value", "status"}
                or setting.get("status")
                not in {"SETTINGS_PASSED", "APPLICATION_ATTEMPTED"}
                for setting in settings
            )
        ):
            raise RuntimeError(f"Broker trace application is invalid: {path}")
        if application.get("status") == "CLIENT_SUCCEEDED" and (
            application.get("exit_code") != 0
            or any(setting.get("status") != "SETTINGS_PASSED" for setting in settings)
        ):
            raise RuntimeError(f"Broker trace success lifecycle is invalid: {path}")
        if application.get("status") == "CLIENT_FAILED" and (
            application.get("exit_code") == 0
            or any(
                setting.get("status") != "APPLICATION_ATTEMPTED"
                for setting in settings
            )
        ):
            raise RuntimeError(f"Broker trace failure lifecycle is invalid: {path}")
        applied_controls = {str(setting["control"]) for setting in settings}
        for name, record in report["negotiation"]["controls"].items():
            expected_enforcement = (
                "APPLICATION_ATTEMPTED" if name in applied_controls else "NOT_APPLIED"
            )
            if record.get("enforcement_status") != expected_enforcement:
                raise RuntimeError(f"Broker trace enforcement lifecycle is invalid: {path}")
    if decision == "CHECKPOINT":
        assert isinstance(application, Mapping)
        settings = application.get("settings")
        if (
            application.get("platform") != platform.get("name")
            or not isinstance(settings, list)
            or not settings
            or application.get("exit_code") != 0
            or any(
                not isinstance(setting, Mapping)
                or setting.get("status") != "SETTINGS_PASSED"
                for setting in settings
            )
        ):
            raise RuntimeError(
                "A CHECKPOINT trace lacks verified broker launcher application evidence."
            )
    return VerifiedExecutionPolicy({
        "task_id": task_id,
        "repository": repository_fingerprint(target),
        "trace_path": pure.as_posix(),
        "trace_sha256": hashlib.sha256(raw).hexdigest(),
        "requested_effort": classification.get("requested_effort"),
        "effective_risk": classification.get("effective_risk"),
        "compatibility_depth": compatibility_depth,
        "platform": platform.get("name"),
        "surface": platform.get("surface"),
        "control_plane": platform.get("control_plane"),
        "decision": decision,
        "checkpoint_resolution": checkpoint_resolution,
        "application_status": application_status,
    })


def inspect_launcher_client(
    platform: str, target: Path, explicit: Path | None = None
) -> tuple[Path, str]:
    if explicit is not None:
        if not explicit.is_absolute():
            raise RuntimeError("An explicit broker launcher client path must be absolute.")
        candidates = [explicit]
    elif platform == "codex":
        candidates = [
            Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
            Path("/opt/homebrew/bin/codex"),
            Path("/usr/local/bin/codex"),
        ]
    elif platform == "claude":
        candidates = [
            Path.home() / ".local/bin/claude",
            Path("/opt/homebrew/bin/claude"),
            Path("/usr/local/bin/claude"),
        ]
    else:
        raise RuntimeError(
            "PowerKit has no safe local launcher adapter for Copilot; use the documented host surface."
        )
    resolved_target = target.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            continue
        try:
            resolved.relative_to(resolved_target)
        except ValueError:
            return_code, output, probe_error = _run_version_probe(
                [str(resolved), "--version"]
            )
            if (
                return_code != 0
                or probe_error is not None
                or platform not in output.lower()
            ):
                if explicit is not None:
                    raise RuntimeError(
                        f"Explicit client does not identify as {platform}: {resolved}"
                    )
                continue
            version = _client_version_token(output)
            if version is None:
                if explicit is not None:
                    raise RuntimeError(
                        f"Explicit {platform} client did not report a semantic version: {resolved}"
                    )
                continue
            return resolved, version
        raise RuntimeError("Refusing to execute a broker client from inside the target repository.")
    raise RuntimeError(f"No trusted executable {platform} client was found.")


def _trusted_client_path(platform: str, target: Path, explicit: Path | None = None) -> Path:
    resolved, version = inspect_launcher_client(platform, target, explicit)
    validated_versions = load_capability_manifest(platform).get(
        "validated_client_versions", []
    )
    if version not in validated_versions:
        raise RuntimeError(
            f"Explicit {platform} client version is not validated: {resolved}"
        )
    return resolved


def _reject_control_overrides(platform: str, client_args: Sequence[str]) -> None:
    del platform
    if len(client_args) != 1:
        raise RuntimeError(
            "Broker launch accepts exactly one prompt argument; additional client flags are not allowed."
        )
    if not client_args[0].strip() or client_args[0].startswith("-"):
        raise RuntimeError(
            "The broker prompt must be non-empty and must not be an option that could override controls."
        )


def build_launch_plan(
    report: Mapping[str, Any],
    target: Path,
    client_args: Sequence[str],
    *,
    client: Path | None = None,
    checkpoint_acknowledged: bool = False,
) -> dict[str, Any]:
    platform = str(report["platform"]["name"])
    if report["platform"]["control_plane"] != "LAUNCHER":
        raise RuntimeError("Broker launch requires a LAUNCHER policy report.")
    if report["platform"]["surface"] != "cli":
        raise RuntimeError("Local broker launch requires the platform's cli surface.")
    if report["negotiation"]["decision"] == "STOP":
        raise RuntimeError("Broker policy is STOP; no client will be launched.")
    _reject_control_overrides(platform, client_args)
    executable = _trusted_client_path(platform, target, client)
    desired = report["desired_policy"]
    settings = [
        dict(item)
        for item in report["negotiation"]["native_settings"]
        if item["applies_to"] == "launcher"
    ]
    settings_by_control = {item["control"]: item for item in settings}
    for control, required in (
        ("filesystem_scope", True),
        ("shell_restriction", desired["permissions"]["shell"] == "DENY"),
    ):
        if required and control not in settings_by_control:
            raise RuntimeError(
                f"The requested {control.replace('_', ' ')} has no concrete launcher setting; refusing launch."
            )

    argv = (
        [str(executable), "exec", "--ephemeral", "--ignore-user-config"]
        if platform == "codex"
        else [
            str(executable),
            "-p",
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--disable-slash-commands",
            "--no-chrome",
            "--strict-mcp-config",
        ]
    )
    environment: dict[str, str] = {}
    applied: list[dict[str, Any]] = []
    for setting in settings:
        name = str(setting["setting"])
        value = setting["value"]
        if platform == "codex":
            if name == "model":
                argv.extend(["--model", str(value)])
            elif name == "sandbox_mode":
                argv.extend(["--sandbox", str(value)])
            else:
                argv.extend(["--config", f"{name}={json.dumps(value, separators=(',', ':'))}"])
        elif name == "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS":
            environment[name] = str(value)
        elif name == "--strict-mcp-config":
            if value and name not in argv:
                argv.append(name)
        elif name == "--worktree":
            if value:
                argv.append(name)
        else:
            argv.extend([name, str(value)])
        applied.append(
            {
                "control": setting["control"],
                "setting": name,
                "value": value,
                "status": "PLANNED",
            }
        )
    checkpoint_directive = (
        "The required broker checkpoint was acknowledged for this launch; proceed only with "
        "the approved phase and keep every DENY constraint in force."
        if report["negotiation"]["decision"] == "CHECKPOINT"
        and checkpoint_acknowledged
        else "The broker checkpoint remains unresolved; do not cross its stated boundary."
        if report["negotiation"]["decision"] == "CHECKPOINT"
        else "No initial broker checkpoint is required; stop at any later consequential boundary."
    )
    policy_directive = (
        "Mandatory PowerKit execution policy for this task:\n"
        + render_compact_policy(report).strip()
        + "\nDo not weaken these constraints. "
        + checkpoint_directive
    )
    prompt = policy_directive + "\n\nUser task:\n" + client_args[0]
    if platform == "codex":
        argv.append("-")
    preview = [f"<{platform}-client>", *argv[1:]]
    return {
        "status": "PLANNED",
        "platform": platform,
        "client": f"{platform}-cli",
        "command_preview": preview,
        "passthrough_arg_count": len(client_args),
        "prompt_transport": "stdin",
        "local_session_persistence": "disabled",
        "checkpoint_acknowledged": checkpoint_acknowledged,
        "settings": applied,
        "_argv": argv,
        "_environment": environment,
        "_stdin": prompt,
        "_decision": report["negotiation"]["decision"],
        "_client_path": str(executable),
    }


def execute_launch(plan: Mapping[str, Any], target: Path) -> int:
    argv = plan.get("_argv")
    extra_environment = plan.get("_environment")
    prompt = plan.get("_stdin")
    if plan.get("_decision") == "CHECKPOINT" and not plan.get(
        "checkpoint_acknowledged"
    ):
        raise RuntimeError("Refusing to execute an unresolved broker checkpoint.")
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        raise RuntimeError("Broker launch plan has no valid argument vector.")
    if not isinstance(extra_environment, Mapping):
        raise RuntimeError("Broker launch plan has no valid environment overlay.")
    if not isinstance(prompt, str) or not prompt:
        raise RuntimeError("Broker launch plan has no valid stdin prompt.")
    environment = dict(os.environ)
    environment.update({str(key): str(value) for key, value in extra_environment.items()})
    try:
        completed = subprocess.run(
            argv,
            cwd=target,
            env=environment,
            input=prompt,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"Unable to launch broker client: {exc}") from exc
    return int(completed.returncode)


def public_launch_plan(
    plan: Mapping[str, Any],
    *,
    status: str | None = None,
    settings_status: str | None = None,
) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in plan.items() if not key.startswith("_")}
    if status is not None:
        result["status"] = status
    if settings_status is not None:
        for setting in result["settings"]:
            setting["status"] = settings_status
    return result

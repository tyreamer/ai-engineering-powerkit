"""Machine-readable project configuration and installation state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from powerkit.installer import (
    MANIFEST_PATH,
    atomic_write_text,
    ensure_managed_path,
    read_json_file,
)
from powerkit.resources import distribution_manifest, distribution_version


PROJECT_CONFIG_PATH = Path(".ai-powerkit/project.json")
SUPPORTED_PLATFORMS = ("codex", "claude", "copilot")
PLATFORM_ALIASES = {
    "codex": "codex",
    "claude": "claude",
    "claude-code": "claude",
    "copilot": "copilot",
    "github-copilot": "copilot",
}


@dataclass(frozen=True)
class ProjectSettings:
    version: str
    profiles: tuple[str, ...]
    platforms: tuple[str, ...]
    agents: bool
    hooks_staged: bool
    source: dict[str, Any]


def normalize_platforms(values: Iterable[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    unknown: set[str] = set()
    for value in values:
        key = value.strip().lower()
        if not key:
            continue
        platform = PLATFORM_ALIASES.get(key)
        if platform:
            normalized.add(platform)
        else:
            unknown.add(key)
    if unknown:
        raise RuntimeError(f"Unknown platforms: {', '.join(sorted(unknown))}")
    return tuple(sorted(normalized))


def load_project_config(target: Path, *, required: bool = True) -> dict[str, Any] | None:
    path = target / PROJECT_CONFIG_PATH
    ensure_managed_path(target, path)
    if not path.exists():
        if required:
            raise RuntimeError(
                f"PowerKit project configuration is missing: {PROJECT_CONFIG_PATH}. "
                "Run `powerkit init` for a new repository."
            )
        return None
    if path.is_symlink():
        raise RuntimeError(f"Refusing to use symlinked PowerKit project configuration: {path}")
    payload = read_json_file(path)
    if payload is None:
        raise RuntimeError(f"PowerKit project configuration is invalid JSON: {path}")
    if payload.get("schema_version") != 1:
        raise RuntimeError(
            f"Unsupported PowerKit project schema: {payload.get('schema_version')!r}"
        )
    return payload


def settings_from_config(payload: dict[str, Any]) -> ProjectSettings:
    powerkit = payload.get("powerkit")
    if not isinstance(powerkit, dict):
        raise RuntimeError("PowerKit project configuration has no `powerkit` object.")
    version = powerkit.get("version")
    profiles = powerkit.get("profiles")
    platforms = powerkit.get("platforms")
    source = powerkit.get("source")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError("PowerKit project configuration has no pinned version.")
    if not isinstance(profiles, list) or not profiles or not all(
        isinstance(item, str) and item.strip() for item in profiles
    ):
        raise RuntimeError("PowerKit project configuration has invalid profiles.")
    if not isinstance(platforms, list) or not platforms:
        raise RuntimeError("PowerKit project configuration has invalid platforms.")
    normalized_platforms = normalize_platforms(str(item) for item in platforms)
    if not isinstance(source, dict):
        raise RuntimeError("PowerKit project configuration has no source descriptor.")
    for field in ("repository", "version", "ref"):
        if not isinstance(source.get(field), str) or not source[field].strip():
            raise RuntimeError(f"PowerKit source descriptor has invalid {field}.")
    if source["version"] != version:
        raise RuntimeError("PowerKit source version does not match the project version pin.")
    expected_repository = str(distribution_manifest()["repository"])
    if source["repository"] != expected_repository:
        raise RuntimeError(
            "PowerKit project source does not match the running distribution repository."
        )
    agents = powerkit.get("agents", True)
    hooks_staged = powerkit.get("hooks_staged", False)
    if not isinstance(agents, bool) or not isinstance(hooks_staged, bool):
        raise RuntimeError("PowerKit agents and hooks_staged settings must be booleans.")
    return ProjectSettings(
        version=version,
        profiles=tuple(dict.fromkeys(item.strip().lower() for item in profiles)),
        platforms=normalized_platforms,
        agents=agents,
        hooks_staged=hooks_staged,
        source=dict(source),
    )


def source_descriptor(version: str | None = None) -> dict[str, str]:
    manifest = distribution_manifest()
    release = manifest.get("release", {})
    resolved_version = version or distribution_version()
    tag = release.get("tag") if isinstance(release, dict) else None
    return {
        "repository": str(manifest["repository"]),
        "version": resolved_version,
        "ref": str(tag or f"v{resolved_version}"),
    }


def build_project_config(
    target: Path,
    *,
    profiles: tuple[str, ...],
    platforms: tuple[str, ...],
    agents: bool,
    hooks_staged: bool,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(existing or {})
    payload["schema_version"] = 1
    payload.setdefault("project_name", target.name)
    existing_powerkit = payload.get("powerkit")
    existing_budgets = (
        existing_powerkit.get("context_budgets")
        if isinstance(existing_powerkit, dict)
        else None
    )
    default_budgets = distribution_manifest().get("context_budgets")
    payload["powerkit"] = {
        "version": distribution_version(),
        "source": source_descriptor(),
        "profiles": list(profiles),
        "platforms": list(platforms),
        "agents": agents,
        "hooks_staged": hooks_staged,
        "context_budgets": dict(
            existing_budgets
            if isinstance(existing_budgets, dict)
            else default_budgets
            if isinstance(default_budgets, dict)
            else {}
        ),
    }
    payload.setdefault(
        "verification",
        {"static": [], "targeted": [], "broader": [], "runtime": []},
    )
    payload.setdefault(
        "policy",
        {
            "ask_before_new_production_dependency": True,
            "single_writer_default": True,
            "require_runtime_proof_for_user_visible_changes": True,
        },
    )
    return payload


def write_project_config(target: Path, payload: dict[str, Any], *, dry_run: bool) -> bool:
    path = target / PROJECT_CONFIG_PATH
    ensure_managed_path(target, path)
    if path.is_symlink():
        raise RuntimeError(f"Refusing to replace symlinked PowerKit project configuration: {path}")
    rendered = json.dumps(payload, indent=2) + "\n"
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    if existing == rendered:
        return False
    if dry_run:
        return True
    atomic_write_text(path, rendered)
    return True


def load_install_manifest(target: Path) -> dict[str, Any] | None:
    path = target / MANIFEST_PATH
    ensure_managed_path(target, path)
    return read_json_file(path)


def detect_platforms(target: Path) -> dict[str, tuple[str, ...]]:
    """Return evidence signals without pretending they prove active use."""
    signals: dict[str, list[str]] = {platform: [] for platform in SUPPORTED_PLATFORMS}
    checks = {
        "codex": (("AGENTS.md", target / "AGENTS.md"), (".codex/", target / ".codex")),
        "claude": (("CLAUDE.md", target / "CLAUDE.md"), (".claude/", target / ".claude")),
        "copilot": (
            (".github/copilot-instructions.md", target / ".github/copilot-instructions.md"),
            (".github/agents/", target / ".github/agents"),
            (".github/instructions/", target / ".github/instructions"),
        ),
    }
    for platform, candidates in checks.items():
        for label, path in candidates:
            if path.exists():
                signals[platform].append(label)

    config = load_project_config(target, required=False)
    if config and isinstance(config.get("powerkit"), dict):
        configured = config["powerkit"].get("platforms", [])
        if isinstance(configured, list):
            for platform in normalize_platforms(str(item) for item in configured):
                signals[platform].append(".ai-powerkit/project.json")

    return {platform: tuple(values) for platform, values in signals.items() if values}

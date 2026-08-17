"""Deterministic, offline accounting for PowerKit-attributable context.

The auditor intentionally models PowerKit artifacts rather than total provider input.
It never imports or executes code from the target repository.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from powerkit.installer import (
    END,
    START,
    agent_operations,
    atomic_write_text,
    instruction_block,
    instruction_operations,
    normalized_legacy_inventory,
    safe_asset_path,
)
from powerkit.resources import catalog as distribution_catalog
from powerkit.resources import distribution_manifest, distribution_root, distribution_version
from powerkit.state import settings_from_config


SCHEMA_VERSION = 1
BASELINE_SCHEMA_VERSION = 1
DEFAULT_BASELINE_PATH = Path(".ai-powerkit/context-baseline.json")
PLATFORMS = ("codex", "claude", "copilot")
PLATFORM_LABELS = {"codex": "Codex", "claude": "Claude", "copilot": "Copilot"}
METRIC_BUDGET_KEYS = {
    "always_on_tokens": "always_on_tokens",
    "discovery_tokens": "discovery_tokens",
    "fast_path_tokens": "fast_path_tokens",
    "standard_path_tokens": "standard_path_tokens",
    "deep_path_tokens": "deep_path_tokens",
}
CI_REGRESSION_METRICS = (
    "always_on_tokens",
    "discovery_tokens",
    "fast_path_tokens",
    "standard_path_tokens",
)
DEFAULT_BUDGETS: dict[str, Any] = {
    # Derived from the v0.2 PowerKit source audit with roughly 15-30% headroom.
    # These are toolkit budgets, not model context-window limits.
    "policy": "warn",
    "always_on_tokens": 900,
    "discovery_tokens": 2100,
    "fast_path_tokens": 8000,
    "standard_path_tokens": 12000,
    "deep_path_tokens": 15000,
    "regression_percent": 20,
    "regression_tokens": 250,
}
PATH_SKILL_EXTRAS = {
    "standard": (
        "verification-loop",
        "anti-slop-review",
        "decision-handoff",
    ),
    "deep": (
        "repository-cartographer",
        "task-contract",
        "change-impact-analysis",
        "vertical-slice-planner",
        "implementation-planner",
        "test-gap-hunter",
        "anti-slop-review",
    ),
}
STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "before",
    "by",
    "do",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "use",
    "when",
    "with",
    "work",
}
SAFETY_TERMS = {
    "authorization",
    "credentials",
    "destructive",
    "permission",
    "privacy",
    "secret",
    "security",
    "tenant",
    "never overwrite",
    "preserve scope",
}


class ContextAuditError(RuntimeError):
    """Controlled failure caused by invalid or unsafe audit input."""


@dataclass(frozen=True)
class TokenMeasurement:
    bytes: int
    characters: int
    tokens: int
    quality: str = "estimated"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TokenEstimator:
    """Small estimator boundary so a future exact tokenizer can plug in safely."""

    identifier = "utf8-bytes-v1"
    label = "deterministic UTF-8 byte approximation"
    quality = "estimated"

    def measure(self, text: str, *, byte_count: int | None = None) -> TokenMeasurement:
        encoded = text.encode("utf-8")
        size = len(encoded) if byte_count is None else byte_count
        return TokenMeasurement(
            bytes=size,
            characters=len(text),
            tokens=math.ceil(size / 4) if size else 0,
            quality=self.quality,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.identifier,
            "label": self.label,
            "quality": self.quality,
            "note": (
                "Counts are deterministic estimates, not provider-billed tokens. "
                "The relevant host/model tokenizer is not assumed."
            ),
        }


@dataclass
class Artifact:
    artifact_id: str
    category: str
    path: str
    platforms: tuple[str, ...]
    measurement: TokenMeasurement
    evidence: str
    load_behavior: str
    content: str = field(repr=False)
    skill: str | None = None
    profile: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.artifact_id,
            "category": self.category,
            "path": safe_terminal_text(self.path),
            "platforms": list(self.platforms),
            "measurement": self.measurement.to_dict(),
            "evidence": self.evidence,
            "load_behavior": self.load_behavior,
        }
        if self.skill:
            payload["skill"] = self.skill
        if self.profile:
            payload["profile"] = self.profile
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: str
    recommendation_class: str
    priority: str
    what: str
    why: str
    suggested_change: str
    estimated_impact: str
    estimated_savings_tokens: int | None
    confidence: str
    evidence: str
    safety: str = "requires_review"
    affected_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.recommendation_id,
            "class": self.recommendation_class,
            "priority": self.priority,
            "what": safe_terminal_text(self.what),
            "why": safe_terminal_text(self.why),
            "suggested_change": safe_terminal_text(self.suggested_change),
            "estimated_impact": safe_terminal_text(self.estimated_impact),
            "estimated_savings_tokens": self.estimated_savings_tokens,
            "confidence": safe_terminal_text(self.confidence),
            "evidence": safe_terminal_text(self.evidence),
            "safety": self.safety,
            "affected_paths": [safe_terminal_text(path) for path in self.affected_paths],
        }


@dataclass(frozen=True)
class AuditResult:
    payload: dict[str, Any]
    ci_failed: bool


def safe_terminal_text(value: str) -> str:
    """Remove terminal control characters from target-controlled labels."""
    result: list[str] = []
    for char in value:
        if char in {"\n", "\r", "\t"} or unicodedata.category(char).startswith("C"):
            result.append(f"\\u{ord(char):04x}")
        else:
            result.append(char)
    return "".join(result)


def _artifact_id(category: str, path: str, platforms: Iterable[str], suffix: str = "") -> str:
    del platforms
    value = "\0".join((category, path, suffix))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _relative_label(target: Path, path: Path) -> str:
    try:
        return path.relative_to(target).as_posix()
    except ValueError:
        try:
            return "distribution:" + path.relative_to(distribution_root()).as_posix()
        except ValueError:
            return path.name


def _safe_known_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {".", ".."} for part in pure.parts):
        raise ContextAuditError(f"Unsafe PowerKit inventory path: {relative!r}")
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise ContextAuditError(f"Refusing symlinked PowerKit audit path: {current}")
    try:
        current.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ContextAuditError(f"PowerKit audit path escapes target: {relative!r}") from exc
    return current


def _read_text(path: Path) -> tuple[str, int, bool]:
    if path.is_symlink():
        raise ContextAuditError(f"Refusing symlinked PowerKit context artifact: {path}")
    if not path.is_file():
        raise ContextAuditError(f"PowerKit context artifact is not a regular file: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContextAuditError(f"Unable to read PowerKit context artifact {path}: {exc}") from exc
    try:
        return raw.decode("utf-8"), len(raw), False
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace"), len(raw), True


def _read_json(path: Path, *, required: bool = False) -> dict[str, Any] | None:
    if path.is_symlink():
        raise ContextAuditError(f"Refusing symlinked PowerKit JSON: {path}")
    if not path.exists():
        if required:
            raise ContextAuditError(f"Required PowerKit JSON is missing: {path}")
        return None
    text, _, malformed = _read_text(path)
    if malformed:
        raise ContextAuditError(f"PowerKit JSON is not valid UTF-8: {path}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContextAuditError(f"Invalid PowerKit JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContextAuditError(f"PowerKit JSON must contain an object: {path}")
    return payload


def _validate_install_manifest(payload: Mapping[str, Any]) -> None:
    if payload.get("toolkit") != "ai-engineering-powerkit":
        raise ContextAuditError("Installation manifest is not owned by PowerKit.")
    schema_version = payload.get("schema_version")
    if schema_version not in {1, 2}:
        raise ContextAuditError(
            f"Unsupported PowerKit installation manifest schema: {schema_version!r}"
        )
    if not isinstance(payload.get("version"), str) or not payload["version"].strip():
        raise ContextAuditError("Installation manifest has no PowerKit version.")
    if payload.get("scope") not in {"project", "user"}:
        raise ContextAuditError("Installation manifest has an invalid scope.")
    for field in ("profiles", "platforms", "skills"):
        values = payload.get(field)
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            raise ContextAuditError(f"Installation manifest has invalid {field}.")
        if len(values) != len(set(values)):
            raise ContextAuditError(f"Installation manifest has duplicate {field}.")
    if not all(value in PLATFORMS for value in payload["platforms"]):
        raise ContextAuditError(
            "Installation manifest platforms must use canonical codex, claude, or copilot IDs."
        )
    if not isinstance(payload.get("agents"), bool) or not isinstance(
        payload.get("hooks_staged"), bool
    ):
        raise ContextAuditError(
            "Installation manifest agents and hooks_staged fields must be booleans."
        )
    source = payload.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != distribution_manifest().get("repository")
        or source.get("version") != payload["version"]
    ):
        raise ContextAuditError("Installation manifest has an invalid PowerKit source descriptor.")
    if schema_version == 2:
        managed_assets = payload.get("managed_assets")
        if not isinstance(managed_assets, list) or not all(
            isinstance(asset, dict) for asset in managed_assets
        ):
            raise ContextAuditError("Installation manifest has invalid managed_assets.")
    else:
        try:
            normalized_legacy_inventory(dict(payload))
        except RuntimeError as exc:
            raise ContextAuditError(str(exc)) from exc


def _expected_context_assets(
    target: Path,
    payload: Mapping[str, Any],
    expected_skills: Sequence[str],
) -> dict[str, dict[str, Any]]:
    scope = str(payload["scope"])
    platforms = {str(value) for value in payload["platforms"]}
    expected: dict[str, dict[str, Any]] = {
        destination.relative_to(target).as_posix(): {"kind": "instruction-block"}
        for destination, _ in instruction_operations(target, scope, platforms)
    }
    if bool(payload.get("agents")):
        operations, _ = agent_operations(target, scope, platforms)
        expected.update(
            {
                destination.relative_to(target).as_posix(): {"kind": "managed-file"}
                for _, destination in operations
            }
        )
    skill_roots: list[str] = []
    if platforms & {"codex", "copilot"}:
        skill_roots.append(".agents/skills")
    if "claude" in platforms:
        skill_roots.append(".claude/skills")
    for root in skill_roots:
        for skill in expected_skills:
            expected[f"{root}/{skill}"] = {"kind": "skill", "skill": skill}
    if scope == "project" and "copilot" in platforms and "pk" in expected_skills:
        expected[".github/prompts/pk.prompt.md"] = {"kind": "managed-file"}
    return expected


def _validate_manifest_inventory(
    target: Path,
    payload: Mapping[str, Any],
    expected_skills: Sequence[str],
) -> dict[str, dict[str, Any]]:
    schema_version = payload["schema_version"]
    raw_assets = payload.get("managed_assets", [])
    assets: list[dict[str, Any]] = [
        asset for asset in raw_assets if isinstance(asset, dict)
    ] if isinstance(raw_assets, list) else []
    asset_paths: set[str] = set()
    assets_by_path: dict[str, dict[str, Any]] = {}
    if schema_version == 2:
        for asset in assets:
            path = asset.get("path")
            if not isinstance(path, str) or not path or safe_asset_path(target, path) is None:
                raise ContextAuditError(f"Unsafe managed asset path in installation manifest: {path!r}")
            if path in asset_paths:
                raise ContextAuditError(f"Duplicate managed asset path in installation manifest: {path!r}")
            asset_paths.add(path)
            assets_by_path[path] = asset
    else:
        try:
            asset_paths = normalized_legacy_inventory(dict(payload))
        except RuntimeError as exc:
            raise ContextAuditError(str(exc)) from exc

    manifest_skills = payload["skills"]
    assert isinstance(manifest_skills, list)
    if set(manifest_skills) != set(expected_skills) or len(manifest_skills) != len(expected_skills):
        missing_skills = sorted(set(expected_skills) - set(manifest_skills))
        unexpected_skills = sorted(set(manifest_skills) - set(expected_skills))
        detail = ""
        if missing_skills:
            detail += " Missing: " + ", ".join(missing_skills) + "."
        if unexpected_skills:
            detail += " Unexpected: " + ", ".join(unexpected_skills) + "."
        raise ContextAuditError(
            "Installation manifest skill selection disagrees with its configured profiles."
            + detail
        )

    expected_assets = _expected_context_assets(target, payload, expected_skills)
    missing = set(expected_assets) - asset_paths
    if missing:
        rendered = ", ".join(sorted(missing)[:4])
        raise ContextAuditError(
            "Installation manifest omits expected PowerKit context artifacts: " + rendered
        )
    for path, expected in expected_assets.items():
        candidate = safe_asset_path(target, path)
        assert candidate is not None
        if expected["kind"] == "skill":
            present = candidate.is_dir()
        else:
            present = candidate.is_file()
        if not present:
            raise ContextAuditError(f"Managed PowerKit context artifact is missing: {path}")
        if schema_version == 2 and assets_by_path[path].get("kind") != expected["kind"]:
            raise ContextAuditError(
                f"Installation manifest has the wrong asset kind for PowerKit context artifact: {path}"
            )
    return expected_assets


def _frontmatter(text: str, path: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ContextAuditError(f"Skill has no frontmatter: {path}")
    try:
        boundary = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ContextAuditError(f"Skill frontmatter is not closed: {path}") from exc
    metadata: dict[str, str] = {}
    in_nested_metadata = False
    for line in lines[1:boundary]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("metadata:"):
            in_nested_metadata = True
            continue
        if line[:1].isspace():
            continue
        in_nested_metadata = False
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if in_nested_metadata:
            continue
        rendered = value.strip()
        if len(rendered) >= 2 and rendered[0] == rendered[-1] and rendered[0] in {"\"", "'"}:
            rendered = rendered[1:-1]
        normalized_key = key.strip()
        if normalized_key in metadata:
            raise ContextAuditError(
                f"Skill frontmatter repeats {normalized_key!r}: {path}"
            )
        metadata[normalized_key] = rendered
    if not metadata.get("name") or not metadata.get("description"):
        raise ContextAuditError(f"Skill discovery metadata is incomplete: {path}")
    body = "\n".join(lines[boundary + 1 :]).strip() + "\n"
    return metadata, body


def _platform_for_instruction(path: str, scope: str) -> str | None:
    if path == "AGENTS.md" or (scope == "user" and path == ".codex/AGENTS.md"):
        return "codex"
    if path == "CLAUDE.md" or (scope == "user" and path == ".claude/CLAUDE.md"):
        return "claude"
    if path == ".github/copilot-instructions.md":
        return "copilot"
    return None


def _platform_for_agent(path: str, scope: str) -> str | None:
    if path.startswith(".codex/agents/"):
        return "codex"
    if path.startswith(".claude/agents/"):
        return "claude"
    if path.startswith(".github/agents/") or (scope == "user" and path.startswith(".copilot/agents/")):
        return "copilot"
    return None


def _selected_skill_names(
    source_catalog: Mapping[str, Any], profiles: Sequence[str]
) -> tuple[str, ...]:
    skills = source_catalog.get("skills", [])
    all_names = tuple(
        sorted(
            str(item["name"])
            for item in skills
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        )
    )
    if not profiles or "all" in profiles:
        return all_names
    profile_payload = source_catalog.get("profiles", {})
    if not isinstance(profile_payload, dict):
        raise ContextAuditError("PowerKit catalog profiles are invalid.")
    selected: set[str] = set()
    for profile in profiles:
        payload = profile_payload.get(profile)
        if not isinstance(payload, dict) or not isinstance(payload.get("skills"), list):
            raise ContextAuditError(f"Unknown or invalid PowerKit profile: {profile}")
        selected.update(str(name) for name in payload["skills"])
    unknown = selected - set(all_names)
    if unknown:
        raise ContextAuditError(f"PowerKit profiles reference unknown skills: {', '.join(sorted(unknown))}")
    return tuple(sorted(selected))


class ContextInventory:
    def __init__(self, target: Path, estimator: TokenEstimator) -> None:
        self.target = target.expanduser().resolve()
        self.estimator = estimator
        self.artifacts: list[Artifact] = []
        self.warnings: list[str] = []
        self.source_kind = "unknown"
        self.inventory_source = "unknown"
        self.scope = "project"
        self.profiles: tuple[str, ...] = ()
        self.config: dict[str, Any] | None = None
        self.manifest: dict[str, Any] | None = None
        self.source_catalog: dict[str, Any] = {}
        self.skill_names: tuple[str, ...] = ()
        self.platforms: tuple[str, ...] = ()
        self.configured_platforms: tuple[str, ...] = ()
        self.version = distribution_version()
        self._skill_roots: dict[Path, tuple[str, ...]] = {}

    def build(self, requested_platforms: tuple[str, ...] | None) -> "ContextInventory":
        if not self.target.is_dir():
            raise ContextAuditError(f"Target directory does not exist: {self.target}")
        self.config = _read_json(self.target / ".ai-powerkit/project.json")
        self.manifest = _read_json(self.target / ".ai-powerkit/install-manifest.json")
        source_candidate = (self.target / "catalog.json").is_file() and (
            self.target / ".agents/skills"
        ).is_dir()
        source_catalog = (
            _read_json(self.target / "catalog.json", required=True)
            if source_candidate
            else None
        )
        source_manifest = (
            _read_json(self.target / "manifests/powerkit.json", required=True)
            if source_candidate
            else None
        )
        is_source = bool(
            source_candidate
            and source_catalog
            and source_manifest
            and source_catalog.get("name") == "AI Engineering PowerKit"
            and source_catalog.get("canonical_skill_root") == ".agents/skills"
            and source_manifest.get("repository")
            == distribution_manifest().get("repository")
            and source_manifest.get("powerkit_version") == source_catalog.get("version")
        )
        if source_candidate and not is_source:
            raise ContextAuditError(
                "Target has a skill catalog but is not a recognized PowerKit distribution source."
            )
        if self.manifest is not None:
            _validate_install_manifest(self.manifest)
        config_settings = None
        if self.config is not None and not is_source:
            try:
                config_settings = settings_from_config(self.config)
            except RuntimeError as exc:
                raise ContextAuditError(str(exc)) from exc
        if is_source:
            self.source_kind = "distribution-source"
            self.inventory_source = "canonical source tree"
            self.source_catalog = source_catalog or {}
            self.profiles = ("all",)
            self.scope = "project"
            self.version = str(self.source_catalog.get("version", distribution_version()))
        else:
            if self.config is None and self.manifest is None:
                raise ContextAuditError(
                    "No PowerKit source tree, project configuration, or installation manifest was found."
                )
            self.source_kind = "installed" if self.manifest else "desired-installation"
            self.inventory_source = (
                ".ai-powerkit/install-manifest.json"
                if self.manifest
                else ".ai-powerkit/project.json + pinned distribution"
            )
            self.source_catalog = distribution_catalog()
            powerkit = self.config.get("powerkit") if isinstance(self.config, dict) else None
            configured_profiles = powerkit.get("profiles") if isinstance(powerkit, dict) else None
            manifest_profiles = self.manifest.get("profiles") if isinstance(self.manifest, dict) else None
            raw_profiles = (
                manifest_profiles
                if self.manifest and isinstance(manifest_profiles, list)
                else configured_profiles
            )
            self.profiles = tuple(str(value) for value in raw_profiles) if isinstance(raw_profiles, list) else ("all",)
            self.scope = str(self.manifest.get("scope", "project")) if self.manifest else "project"
            manifest_version = self.manifest.get("version") if self.manifest else None
            config_powerkit = self.config.get("powerkit") if self.config else None
            configured_version = (
                config_powerkit.get("version") if isinstance(config_powerkit, dict) else None
            )
            self.version = str(
                manifest_version
                if isinstance(manifest_version, str)
                else configured_version
                if isinstance(configured_version, str)
                else distribution_version()
            )
            if self.manifest and self.version != distribution_version():
                raise ContextAuditError(
                    f"Installed PowerKit {self.version} must be audited with its pinned distribution, "
                    f"not {distribution_version()}."
                )
            if not self.manifest and self.config and isinstance(self.config.get("powerkit"), dict):
                pinned = self.config["powerkit"].get("version")
                if isinstance(pinned, str) and pinned != distribution_version():
                    raise ContextAuditError(
                        f"Project pins PowerKit {pinned}, but the running distribution is "
                        f"{distribution_version()}; run the pinned release to audit desired state."
                    )
            if self.manifest:
                expected_skills = _selected_skill_names(self.source_catalog, self.profiles)
                expected_assets = _validate_manifest_inventory(
                    self.target, self.manifest, expected_skills
                )
                if self.manifest.get("schema_version") == 1:
                    normalized_manifest = dict(self.manifest)
                    normalized_manifest["managed_assets"] = [
                        {"path": path, **metadata}
                        for path, metadata in sorted(expected_assets.items())
                    ]
                    self.manifest = normalized_manifest
                if config_settings is not None:
                    manifest_source = self.manifest.get("source")
                    state_matches = (
                        config_settings.version == self.manifest.get("version")
                        and isinstance(manifest_source, dict)
                        and manifest_source.get("version") == config_settings.version
                        and list(config_settings.profiles) == self.manifest.get("profiles")
                        and list(config_settings.platforms) == self.manifest.get("platforms")
                        and config_settings.agents == bool(self.manifest.get("agents"))
                        and config_settings.hooks_staged == bool(self.manifest.get("hooks_staged"))
                    )
                    if not state_matches:
                        raise ContextAuditError(
                            "PowerKit project configuration and installed manifest disagree; run the pinned release's `powerkit sync`."
                        )
        manifest_skills = self.manifest.get("skills") if self.manifest else None
        if isinstance(manifest_skills, list) and all(
            isinstance(name, str) and name for name in manifest_skills
        ):
            known = {
                str(item["name"])
                for item in self.source_catalog.get("skills", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            unknown = set(manifest_skills) - known
            if unknown:
                raise ContextAuditError(
                    "Installation manifest references unknown skills: "
                    + ", ".join(sorted(unknown))
                )
            self.skill_names = tuple(dict.fromkeys(str(name) for name in manifest_skills))
        else:
            self.skill_names = _selected_skill_names(self.source_catalog, self.profiles)
        self.configured_platforms = self._infer_platforms(is_source)
        self.platforms = requested_platforms or self.configured_platforms
        if not self.platforms:
            raise ContextAuditError(
                "No PowerKit platform could be inferred; pass --platform codex, claude, copilot, or all."
            )
        self._add_always_on(is_source)
        self._prepare_skill_roots(is_source)
        self._add_skills()
        self._add_agents_and_adapters(is_source)
        return self

    def _infer_platforms(self, is_source: bool) -> tuple[str, ...]:
        if self.manifest and isinstance(self.manifest.get("platforms"), list):
            normalized = normalize_platforms(str(value) for value in self.manifest["platforms"])
            if normalized:
                return normalized
        if self.config and isinstance(self.config.get("powerkit"), dict):
            values = self.config["powerkit"].get("platforms")
            if isinstance(values, list):
                normalized = normalize_platforms(str(value) for value in values)
                if normalized:
                    return normalized
        detected: list[str] = []
        paths = {
            "codex": self.target / (".codex/AGENTS.md" if self.scope == "user" else "AGENTS.md"),
            "claude": self.target / (".claude/CLAUDE.md" if self.scope == "user" else "CLAUDE.md"),
            "copilot": self.target / ".github/copilot-instructions.md",
        }
        for platform, path in paths.items():
            if path.exists():
                detected.append(platform)
        if is_source and not detected:
            return PLATFORMS
        return tuple(detected)

    def _append_artifact(
        self,
        *,
        category: str,
        path: str,
        platforms: Iterable[str],
        content: str,
        byte_count: int | None,
        evidence: str,
        load_behavior: str,
        skill: str | None = None,
        profile: str | None = None,
        metadata: dict[str, Any] | None = None,
        suffix: str = "",
    ) -> None:
        artifact_platforms = tuple(sorted(set(platforms) & set(self.platforms)))
        if not artifact_platforms:
            return
        self.artifacts.append(
            Artifact(
                artifact_id=_artifact_id(category, path, artifact_platforms, suffix),
                category=category,
                path=path,
                platforms=artifact_platforms,
                measurement=self.estimator.measure(content, byte_count=byte_count),
                evidence=evidence,
                load_behavior=load_behavior,
                content=content,
                skill=skill,
                profile=profile,
                metadata=metadata or {},
            )
        )

    def _add_always_on(self, is_source: bool) -> None:
        if self.manifest and isinstance(self.manifest.get("managed_assets"), list):
            for asset in self.manifest["managed_assets"]:
                if not isinstance(asset, dict) or asset.get("kind") != "instruction-block":
                    continue
                raw_path = asset.get("path")
                if not isinstance(raw_path, str):
                    raise ContextAuditError("Installation manifest has an invalid instruction path.")
                path = safe_asset_path(self.target, raw_path)
                if path is None:
                    raise ContextAuditError(f"Unsafe instruction path in installation manifest: {raw_path!r}")
                platform = _platform_for_instruction(raw_path, self.scope)
                if not platform or platform not in self.platforms:
                    continue
                if not path.exists():
                    raise ContextAuditError(
                        f"Managed PowerKit instruction artifact is missing: {raw_path}"
                    )
                block = instruction_block(path)
                if block is None:
                    raise ContextAuditError(f"Managed PowerKit instruction block is malformed: {path}")
                self._append_artifact(
                    category="always_on_instruction",
                    path=raw_path,
                    platforms=(platform,),
                    content=block,
                    byte_count=len(block.encode("utf-8")),
                    evidence="observed managed instruction block",
                    load_behavior="always-on",
                )
            return

        if is_source:
            candidates = {
                "codex": "AGENTS.md",
                "claude": "CLAUDE.md",
                "copilot": ".github/copilot-instructions.md",
            }
            for platform, relative in candidates.items():
                if platform not in self.platforms:
                    continue
                path = _safe_known_path(self.target, relative)
                if not path.exists():
                    continue
                text, byte_count, malformed = _read_text(path)
                if malformed:
                    self.warnings.append(f"{relative} contained malformed UTF-8 and was decoded with replacement characters.")
                self._append_artifact(
                    category="always_on_instruction",
                    path=relative,
                    platforms=(platform,),
                    content=text,
                    byte_count=byte_count,
                    evidence="canonical source instruction",
                    load_behavior="always-on",
                )
            return

        templates = {
            "codex": ("AGENTS.md", "templates/instructions/AGENTS.block.md"),
            "claude": ("CLAUDE.md", "templates/instructions/CLAUDE.block.md"),
            "copilot": (
                ".github/copilot-instructions.md",
                "templates/instructions/copilot-instructions.block.md",
            ),
        }
        for platform, (destination, source) in templates.items():
            if platform not in self.platforms or platform not in self.configured_platforms:
                continue
            path = _safe_known_path(distribution_root(), source)
            text, byte_count, malformed = _read_text(path)
            if malformed:
                raise ContextAuditError(f"Distribution instruction template is malformed UTF-8: {path}")
            wrapped = f"{START}\n{text.strip()}\n{END}"
            self._append_artifact(
                category="always_on_instruction",
                path=destination,
                platforms=(platform,),
                content=wrapped,
                byte_count=len(wrapped.encode("utf-8")),
                evidence="configured distribution template (static potential)",
                load_behavior="always-on after sync",
            )

    def _prepare_skill_roots(self, is_source: bool) -> None:
        if is_source:
            self._skill_roots[self.target / ".agents/skills"] = self.platforms
            return
        active_platforms = set(self.platforms) & set(self.configured_platforms)
        canonical_platforms = tuple(platform for platform in active_platforms if platform in {"codex", "copilot"})
        canonical_root = self.target / ".agents/skills"
        claude_root = self.target / ".claude/skills"
        if canonical_root.is_symlink():
            raise ContextAuditError(f"Refusing symlinked PowerKit skill root: {canonical_root}")
        if claude_root.is_symlink():
            raise ContextAuditError(f"Refusing symlinked PowerKit skill root: {claude_root}")
        if canonical_platforms and canonical_root.is_dir() and not canonical_root.is_symlink():
            self._skill_roots[canonical_root] = canonical_platforms
        if "claude" in active_platforms and claude_root.is_dir() and not claude_root.is_symlink():
            self._skill_roots[claude_root] = ("claude",)
        missing = active_platforms - {
            platform for platforms in self._skill_roots.values() for platform in platforms
        }
        if missing:
            self._skill_roots[distribution_root() / ".agents/skills"] = tuple(sorted(missing))
            self.warnings.append(
                "One or more configured skill roots are not installed; modeled the pinned distribution as static potential."
            )

    def _profile_for_skill(self, name: str) -> str | None:
        for item in self.source_catalog.get("skills", []):
            if isinstance(item, dict) and item.get("name") == name:
                profile = item.get("profile")
                return str(profile) if isinstance(profile, str) else None
        return None

    def _add_skills(self) -> None:
        for root, platforms in self._skill_roots.items():
            if root.is_symlink():
                raise ContextAuditError(f"Refusing symlinked PowerKit skill root: {root}")
            for name in self.skill_names:
                skill_dir = _safe_known_path(root, name)
                skill_path = _safe_known_path(skill_dir, "SKILL.md")
                if not skill_path.is_file():
                    self.warnings.append(f"Configured skill is unavailable for audit: {name}")
                    continue
                text, byte_count, malformed = _read_text(skill_path)
                relative = _relative_label(self.target, skill_path)
                if malformed:
                    self.warnings.append(
                        f"{relative} contained malformed UTF-8 and was decoded with replacement characters."
                    )
                frontmatter, body = _frontmatter(text, relative)
                if frontmatter["name"] != name:
                    raise ContextAuditError(
                        f"Skill name {frontmatter['name']!r} does not match inventory path {name!r}."
                    )
                profile = self._profile_for_skill(name)
                discovery = f"name: {frontmatter['name']}\ndescription: {frontmatter['description']}\n"
                common_metadata = {
                    "description": frontmatter["description"],
                    "body_tokens": self.estimator.measure(body).tokens,
                }
                self._append_artifact(
                    category="skill_discovery_metadata",
                    path=relative,
                    platforms=platforms,
                    content=discovery,
                    byte_count=None,
                    evidence="skill frontmatter fields exposed for discovery",
                    load_behavior="discovery",
                    skill=name,
                    profile=profile,
                    metadata={
                        "description": frontmatter["description"],
                        "description_tokens": self.estimator.measure(frontmatter["description"]).tokens,
                    },
                    suffix="discovery",
                )
                self._append_artifact(
                    category="selected_skill_body",
                    path=relative,
                    platforms=platforms,
                    content=text,
                    byte_count=byte_count,
                    evidence="canonical or installed skill body",
                    load_behavior="selected only",
                    skill=name,
                    profile=profile,
                    metadata=common_metadata,
                    suffix="body",
                )
                references = skill_dir / "references"
                if references.exists():
                    if references.is_symlink() or not references.is_dir():
                        raise ContextAuditError(f"Unsafe skill references path: {references}")
                    for reference in sorted(references.rglob("*")):
                        if reference.is_symlink():
                            raise ContextAuditError(f"Refusing symlinked skill reference: {reference}")
                        if not reference.is_file():
                            continue
                        try:
                            reference.resolve().relative_to(references.resolve())
                        except ValueError as exc:
                            raise ContextAuditError(f"Skill reference escapes its root: {reference}") from exc
                        ref_text, ref_bytes, ref_malformed = _read_text(reference)
                        ref_label = _relative_label(self.target, reference)
                        if ref_malformed:
                            self.warnings.append(
                                f"{ref_label} contained malformed UTF-8 and was decoded with replacement characters."
                            )
                        self._append_artifact(
                            category="skill_reference",
                            path=ref_label,
                            platforms=platforms,
                            content=ref_text,
                            byte_count=ref_bytes,
                            evidence="reference beneath selected skill",
                            load_behavior="only when explicitly needed",
                            skill=name,
                            profile=profile,
                            suffix=reference.relative_to(references).as_posix(),
                        )

    def _add_agents_and_adapters(self, is_source: bool) -> None:
        if is_source:
            for platform in self.platforms:
                agent_root = self.target / "adapters" / platform / "agents"
                if agent_root.is_symlink():
                    raise ContextAuditError(f"Refusing symlinked agent adapter root: {agent_root}")
                if not agent_root.is_dir():
                    continue
                for path in sorted(agent_root.iterdir()):
                    if not path.is_file():
                        continue
                    text, byte_count, malformed = _read_text(path)
                    label = _relative_label(self.target, path)
                    if malformed:
                        self.warnings.append(f"{label} contained malformed UTF-8.")
                    self._append_artifact(
                        category="agent_instruction",
                        path=label,
                        platforms=(platform,),
                        content=text,
                        byte_count=byte_count,
                        evidence="platform agent adapter",
                        load_behavior="isolated agent only",
                        metadata={"agent": _agent_name(path.name)},
                    )
            if "copilot" in self.platforms:
                adapter = self.target / "adapters/copilot/prompts/pk.prompt.md"
                if adapter.is_file():
                    text, byte_count, malformed = _read_text(adapter)
                    if malformed:
                        self.warnings.append("Copilot pk prompt adapter contained malformed UTF-8.")
                    self._append_artifact(
                        category="platform_adapter",
                        path=_relative_label(self.target, adapter),
                        platforms=("copilot",),
                        content=text,
                        byte_count=byte_count,
                        evidence="canonical platform adapter",
                        load_behavior="pk invocation only",
                    )
            return

        assets = self.manifest.get("managed_assets", []) if self.manifest else []
        if not isinstance(assets, list):
            raise ContextAuditError("Installation manifest managed_assets must be an array.")
        for asset in assets:
            if not isinstance(asset, dict) or asset.get("kind") != "managed-file":
                continue
            raw_path = asset.get("path")
            if not isinstance(raw_path, str):
                raise ContextAuditError("Installation manifest has an invalid managed file path.")
            path = safe_asset_path(self.target, raw_path)
            if path is None:
                raise ContextAuditError(f"Unsafe managed file path in installation manifest: {raw_path!r}")
            if not path.is_file():
                continue
            platform = _platform_for_agent(raw_path, self.scope)
            category = "agent_instruction" if platform else None
            load_behavior = "isolated agent only"
            metadata: dict[str, Any] = {}
            if raw_path == ".github/prompts/pk.prompt.md":
                platform = "copilot"
                category = "platform_adapter"
                load_behavior = "pk invocation only"
            elif platform:
                metadata["agent"] = _agent_name(path.name)
            if not category or not platform or platform not in self.platforms:
                continue
            text, byte_count, malformed = _read_text(path)
            if malformed:
                self.warnings.append(f"{raw_path} contained malformed UTF-8.")
            self._append_artifact(
                category=category,
                path=raw_path,
                platforms=(platform,),
                content=text,
                byte_count=byte_count,
                evidence="observed managed platform artifact",
                load_behavior=load_behavior,
                metadata=metadata,
            )


def _agent_name(filename: str) -> str:
    for suffix in (".agent.md", ".toml", ".md"):
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return filename


def normalize_platforms(values: Iterable[str]) -> tuple[str, ...]:
    result: set[str] = set()
    unknown: set[str] = set()
    for value in values:
        rendered = value.strip().lower()
        if not rendered:
            continue
        if rendered == "all":
            result.update(PLATFORMS)
        elif rendered in PLATFORMS:
            result.add(rendered)
        else:
            unknown.add(rendered)
    if unknown:
        raise ContextAuditError(
            "Unknown context audit platform(s): " + ", ".join(sorted(unknown))
        )
    return tuple(platform for platform in PLATFORMS if platform in result)


def _skill_artifact_map(
    artifacts: Sequence[Artifact], platform: str, category: str
) -> dict[str, Artifact]:
    return {
        artifact.skill: artifact
        for artifact in artifacts
        if artifact.category == category
        and platform in artifact.platforms
        and artifact.skill is not None
    }


def _load_command_manifest(artifacts: Sequence[Artifact], platform: str) -> dict[str, Any] | None:
    matches = [
        artifact
        for artifact in artifacts
        if artifact.category == "skill_reference"
        and artifact.skill == "pk"
        and artifact.path.endswith("references/command-manifest.json")
        and platform in artifact.platforms
    ]
    if not matches:
        raise ContextAuditError(
            f"PowerKit command manifest is missing for installed pk on {platform}."
        )
    try:
        payload = json.loads(matches[0].content)
    except json.JSONDecodeError as exc:
        raise ContextAuditError(
            f"PowerKit command manifest is invalid JSON for {platform}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ContextAuditError(f"PowerKit command manifest must be an object for {platform}.")
    if payload.get("schema_version") != 1 or payload.get("command") != "pk":
        raise ContextAuditError(f"PowerKit command manifest has an unsupported contract for {platform}.")
    global_skills = payload.get("global_skills")
    modes = payload.get("modes")
    if not isinstance(global_skills, list) or not all(
        isinstance(name, str) and name for name in global_skills
    ) or not isinstance(modes, dict):
        raise ContextAuditError(f"PowerKit command manifest is structurally incomplete for {platform}.")
    if not {"feature", "deep"} <= set(modes):
        raise ContextAuditError(
            f"PowerKit command manifest omits path-model modes for {platform}."
        )
    required_globals = {"prompt-preflight", "workload-router"}
    if not required_globals <= set(global_skills):
        raise ContextAuditError(
            f"PowerKit command manifest omits required global routing skills for {platform}."
        )
    for mode_name, mode in modes.items():
        if not isinstance(mode_name, str) or not isinstance(mode, dict):
            raise ContextAuditError(f"PowerKit command manifest has an invalid mode for {platform}.")
        for field in ("primary_skills", "conditional_skills"):
            values = mode.get(field)
            if not isinstance(values, list) or not all(
                isinstance(name, str) and name for name in values
            ):
                raise ContextAuditError(
                    f"PowerKit command manifest mode {mode_name!r} has invalid {field}."
                )
    required_mode_skills = {
        "feature": {"engineering-task-orchestrator", "repository-cartographer", "task-contract"},
        "deep": {"engineering-task-orchestrator", "verification-loop", "adversarial-review", "decision-handoff"},
    }
    for mode_name, required in required_mode_skills.items():
        primary = modes[mode_name]["primary_skills"]
        if not required <= set(primary):
            raise ContextAuditError(
                f"PowerKit command manifest mode {mode_name!r} omits required routing skills."
            )
    return payload


def _path_skill_names(
    manifest: Mapping[str, Any] | None, depth: str
) -> tuple[str, ...]:
    global_skills = manifest.get("global_skills", []) if manifest else []
    selected: list[str] = ["pk"]
    if isinstance(global_skills, list):
        selected.extend(str(name) for name in global_skills)
    modes = manifest.get("modes", {}) if manifest else {}
    if depth in {"standard", "deep"} and isinstance(modes, dict):
        feature = modes.get("feature", {})
        if isinstance(feature, dict) and isinstance(feature.get("primary_skills"), list):
            selected.extend(str(name) for name in feature["primary_skills"])
        selected.extend(PATH_SKILL_EXTRAS["standard"])
    if depth == "deep" and isinstance(modes, dict):
        deep = modes.get("deep", {})
        if isinstance(deep, dict) and isinstance(deep.get("primary_skills"), list):
            selected.extend(str(name) for name in deep["primary_skills"])
        selected.extend(PATH_SKILL_EXTRAS["deep"])
    return tuple(dict.fromkeys(selected))


def _platform_summary(
    artifacts: Sequence[Artifact], platform: str, *, configured: bool
) -> dict[str, Any]:
    if not configured:
        empty_path = {
            "status": "not_configured",
            "tokens": None,
            "missing_skills": [],
            "components": {
                "always_on": None,
                "discovery": None,
                "selected_skills": None,
                "skill_references": None,
                "platform_adapter": None,
                "generated_task_context": None,
            },
            "skills": [],
        }
        return {
            "name": platform,
            "label": PLATFORM_LABELS[platform],
            "configuration_status": "not_configured",
            "loading_model": {
                "always_on": "not installed for this target",
                "discovery": "not installed for this target",
                "selected_skill": "not installed for this target",
                "references": "not installed for this target",
                "agents": "not installed for this target",
            },
            "observation": {
                "status": "unsupported",
                "detail": "Platform is not configured for this target; no loading estimate is claimed.",
            },
            "totals": {
                "always_on_tokens": None,
                "discovery_tokens": None,
                "agent_instruction_tokens": None,
                "adapter_tokens": None,
                "discoverable_skills": 0,
                "discovery_bytes": 0,
                "average_description_tokens": 0,
            },
            "paths": {depth: dict(empty_path) for depth in ("fast", "standard", "deep")},
        }
    relevant = [artifact for artifact in artifacts if platform in artifact.platforms]
    always_on = sum(
        artifact.measurement.tokens
        for artifact in relevant
        if artifact.category == "always_on_instruction"
    )
    discovery = sum(
        artifact.measurement.tokens
        for artifact in relevant
        if artifact.category == "skill_discovery_metadata"
    )
    agents = sum(
        artifact.measurement.tokens
        for artifact in relevant
        if artifact.category == "agent_instruction"
    )
    adapter = sum(
        artifact.measurement.tokens
        for artifact in relevant
        if artifact.category == "platform_adapter"
    )
    skills = _skill_artifact_map(artifacts, platform, "selected_skill_body")
    manifest = _load_command_manifest(artifacts, platform) if "pk" in skills else None
    refs = [
        artifact
        for artifact in relevant
        if artifact.category == "skill_reference"
        and artifact.skill == "pk"
        and artifact.path.endswith("references/routing.md")
    ]
    routing_tokens = sum(artifact.measurement.tokens for artifact in refs)
    mode_tokens = sum(
        artifact.measurement.tokens
        for artifact in relevant
        if artifact.category == "skill_reference"
        and artifact.skill == "pk"
        and artifact.path.endswith("references/modes.md")
    )
    paths: dict[str, Any] = {}
    for depth in ("fast", "standard", "deep"):
        required = _path_skill_names(manifest, depth)
        missing = [name for name in required if name not in skills]
        selected_tokens = sum(skills[name].measurement.tokens for name in required if name in skills)
        adapter_tokens = adapter if "pk" in required else 0
        reference_tokens = routing_tokens + (mode_tokens if depth in {"standard", "deep"} else 0)
        total = None if missing else always_on + discovery + selected_tokens + reference_tokens + adapter_tokens
        paths[depth] = {
            "status": "partial" if missing else "estimated",
            "tokens": total,
            "missing_skills": missing,
            "components": {
                "always_on": always_on,
                "discovery": discovery,
                "selected_skills": selected_tokens,
                "skill_references": reference_tokens,
                "platform_adapter": adapter_tokens,
                "generated_task_context": None,
            },
            "skills": list(required),
        }
    return {
        "name": platform,
        "label": PLATFORM_LABELS[platform],
        "configuration_status": "configured",
        "loading_model": {
            "always_on": "platform instruction file or managed block",
            "discovery": "skill name and description frontmatter",
            "selected_skill": "full SKILL.md after selection",
            "references": "only when the selected skill directs deeper loading",
            "agents": "isolated specialized-agent context; excluded from primary paths",
        },
        "observation": {
            "status": "unsupported",
            "detail": "No live-client context trace was supplied; all values are static estimates.",
        },
        "totals": {
            "always_on_tokens": always_on,
            "discovery_tokens": discovery,
            "agent_instruction_tokens": agents,
            "adapter_tokens": adapter,
            "discoverable_skills": len(skills),
            "discovery_bytes": sum(
                artifact.measurement.bytes
                for artifact in relevant
                if artifact.category == "skill_discovery_metadata"
            ),
            "average_description_tokens": round(
                sum(
                    int(artifact.metadata.get("description_tokens", 0))
                    for artifact in relevant
                    if artifact.category == "skill_discovery_metadata"
                )
                / max(1, len(skills)),
                1,
            ),
        },
        "paths": paths,
    }


def _configured_budgets(config: Mapping[str, Any] | None) -> dict[str, Any]:
    budgets = dict(DEFAULT_BUDGETS)
    manifest_budgets = distribution_manifest().get("context_budgets")
    if isinstance(manifest_budgets, dict):
        budgets.update(manifest_budgets)
    powerkit = config.get("powerkit") if isinstance(config, Mapping) else None
    project_budgets = powerkit.get("context_budgets") if isinstance(powerkit, Mapping) else None
    if isinstance(project_budgets, dict):
        budgets.update(project_budgets)
    policy = budgets.get("policy")
    if policy not in {"warn", "fail_ci", "disabled"}:
        raise ContextAuditError("context_budgets.policy must be warn, fail_ci, or disabled.")
    for key in (
        "always_on_tokens",
        "discovery_tokens",
        "fast_path_tokens",
        "standard_path_tokens",
        "deep_path_tokens",
        "regression_percent",
        "regression_tokens",
    ):
        value = budgets.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ContextAuditError(f"context_budgets.{key} must be a non-negative integer.")
    return budgets


def _metric_value(platform: Mapping[str, Any], metric: str) -> int | None:
    if platform.get("configuration_status") == "not_configured":
        return None
    totals = platform["totals"]
    if metric == "always_on_tokens":
        value = totals["always_on_tokens"]
        return int(value) if isinstance(value, int) else None
    if metric == "discovery_tokens":
        value = totals["discovery_tokens"]
        return int(value) if isinstance(value, int) else None
    depth = metric.removesuffix("_path_tokens")
    value = platform["paths"][depth]["tokens"]
    return int(value) if isinstance(value, int) else None


def _evaluate_budgets(platforms: Sequence[dict[str, Any]], budgets: Mapping[str, Any]) -> list[dict[str, Any]]:
    if budgets["policy"] == "disabled":
        return []
    evaluations: list[dict[str, Any]] = []
    for platform in platforms:
        for metric, budget_key in METRIC_BUDGET_KEYS.items():
            current = _metric_value(platform, metric)
            maximum = int(budgets[budget_key])
            if current is None:
                status = "not_measurable"
            elif current > maximum:
                status = "exceeded"
            elif current >= math.floor(maximum * 0.8):
                status = "watch"
            else:
                status = "within_budget"
            evaluations.append(
                {
                    "platform": platform["name"],
                    "metric": metric,
                    "current": current,
                    "maximum": maximum,
                    "status": status,
                    "over_by": current - maximum if current is not None and current > maximum else 0,
                }
            )
    return evaluations


def _resolve_baseline_path(target: Path, baseline_path: Path | None) -> Path | None:
    candidate = baseline_path or DEFAULT_BASELINE_PATH
    path = candidate if candidate.is_absolute() else target / candidate
    try:
        relative = path.resolve().relative_to(target.resolve())
    except ValueError as exc:
        raise ContextAuditError("Context baseline must stay inside the audit target.") from exc
    current = target
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ContextAuditError(f"Refusing symlinked context baseline path: {current}")
    if path.exists() and not path.is_file():
        raise ContextAuditError(f"Context baseline is not a regular file: {path}")
    if baseline_path is not None and not path.exists():
        raise ContextAuditError(f"Requested context baseline does not exist: {path}")
    return path if path.is_file() else None


def _baseline_comparison(
    target: Path,
    baseline_path: Path | None,
    platforms: Sequence[dict[str, Any]],
    estimator: TokenEstimator,
    budgets: Mapping[str, Any],
) -> dict[str, Any]:
    resolved = _resolve_baseline_path(target, baseline_path)
    if resolved is None:
        return {"status": "unavailable", "path": str(baseline_path or DEFAULT_BASELINE_PATH), "comparisons": []}
    baseline = _read_json(resolved, required=True) or {}
    if baseline.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise ContextAuditError(f"Unsupported context baseline schema: {baseline.get('schema_version')!r}")
    if not isinstance(baseline.get("powerkit_version"), str) or not baseline["powerkit_version"].strip():
        raise ContextAuditError("Context baseline has no PowerKit version.")
    estimator_payload = baseline.get("estimator")
    if (
        not isinstance(estimator_payload, dict)
        or not isinstance(estimator_payload.get("id"), str)
        or estimator_payload.get("quality") not in {"exact", "estimated"}
    ):
        raise ContextAuditError("Context baseline has invalid estimator metadata.")
    baseline_platforms = baseline.get("platforms")
    if not isinstance(baseline_platforms, dict) or not baseline_platforms:
        raise ContextAuditError("Context baseline platforms must be a non-empty object.")
    for platform_name, previous in baseline_platforms.items():
        if platform_name not in PLATFORMS or not isinstance(previous, dict) or not previous:
            raise ContextAuditError(
                f"Context baseline has an invalid platform entry: {platform_name!r}."
            )
        unknown_metrics = set(previous) - set(METRIC_BUDGET_KEYS)
        if unknown_metrics:
            raise ContextAuditError(
                f"Context baseline {platform_name} has unknown metrics: "
                + ", ".join(sorted(unknown_metrics))
            )
        for metric, value in previous.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ContextAuditError(
                    f"Context baseline {platform_name}.{metric} must be a non-negative integer."
                )
    if estimator_payload.get("id") != estimator.identifier:
        return {
            "status": "incompatible_estimator",
            "path": _relative_label(target, resolved),
            "comparisons": [],
            "detail": "Baseline and current audit use different estimators.",
        }
    coverage_gaps: list[str] = []
    for platform in platforms:
        if platform.get("configuration_status") != "configured":
            continue
        previous = baseline_platforms.get(platform["name"])
        if not isinstance(previous, dict):
            coverage_gaps.append(f"{platform['name']}:all")
            continue
        for metric in CI_REGRESSION_METRICS:
            if _metric_value(platform, metric) is not None and metric not in previous:
                coverage_gaps.append(f"{platform['name']}:{metric}")
    if coverage_gaps:
        return {
            "status": "incomplete_baseline",
            "path": _relative_label(target, resolved),
            "comparisons": [],
            "detail": "Baseline lacks measurable CI metrics: " + ", ".join(coverage_gaps),
        }
    comparisons: list[dict[str, Any]] = []
    for platform in platforms:
        previous = baseline_platforms.get(platform["name"])
        if not isinstance(previous, dict):
            continue
        for metric in METRIC_BUDGET_KEYS:
            current = _metric_value(platform, metric)
            old = previous.get(metric)
            if current is None or old is None:
                continue
            delta = current - old
            percent = round((delta / old) * 100, 1) if old else (100.0 if delta else 0.0)
            meaningful = (
                metric in CI_REGRESSION_METRICS
                and delta >= int(budgets["regression_tokens"])
                and percent >= float(budgets["regression_percent"])
            )
            comparisons.append(
                {
                    "platform": platform["name"],
                    "metric": metric,
                    "baseline": old,
                    "current": current,
                    "delta": delta,
                    "percent": percent,
                    "meaningful_regression": meaningful,
                }
            )
    return {
        "status": "compared",
        "path": _relative_label(target, resolved),
        "comparisons": comparisons,
    }


def _words(value: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z][a-z0-9-]{2,}", value.lower())
        if word not in STOP_WORDS
    }


def _normalized_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        normalized = re.sub(r"[`*_>#\-]+", " ", block.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if len(normalized) >= 90:
            blocks.append(normalized)
    return blocks


def _safety_sensitive(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in SAFETY_TERMS)


def _recommendations(
    artifacts: Sequence[Artifact],
    platforms: Sequence[dict[str, Any]],
    budgets: Mapping[str, Any],
) -> tuple[list[Recommendation], int]:
    findings: list[Recommendation] = []
    protected_repetitions = 0
    seen: set[str] = set()

    def add(finding: Recommendation) -> None:
        if finding.recommendation_id not in seen:
            seen.add(finding.recommendation_id)
            findings.append(finding)

    for artifact in artifacts:
        if artifact.category == "always_on_instruction" and artifact.measurement.tokens > int(
            budgets["always_on_tokens"]
        ):
            savings = artifact.measurement.tokens - int(budgets["always_on_tokens"])
            add(
                Recommendation(
                    recommendation_id=f"always-on:{artifact.artifact_id}",
                    recommendation_class="oversized_always_on",
                    priority="highest_impact",
                    what=f"{artifact.path} exceeds the always-on budget.",
                    why="Always-on instructions are paid on every request for that platform.",
                    suggested_change=(
                        "Keep universal invariants here; move task-specific procedures behind the owning skill or reference."
                    ),
                    estimated_impact=f"About {savings} tokens above the configured per-platform budget.",
                    estimated_savings_tokens=savings,
                    confidence="high",
                    evidence=f"Static measurement: {artifact.measurement.tokens} estimated tokens.",
                    affected_paths=(artifact.path,),
                )
            )

    discovery_artifacts = [
        artifact for artifact in artifacts if artifact.category == "skill_discovery_metadata"
    ]
    unique_discovery: dict[str, Artifact] = {}
    for artifact in discovery_artifacts:
        if artifact.skill and artifact.skill not in unique_discovery:
            unique_discovery[artifact.skill] = artifact
    for artifact in unique_discovery.values():
        description_tokens = int(artifact.metadata.get("description_tokens", 0))
        description = str(artifact.metadata.get("description", ""))
        if description_tokens <= 64 or (
            description_tokens <= 96 and _safety_sensitive(description)
        ):
            continue
        savings = max(1, description_tokens - 48)
        add(
            Recommendation(
                recommendation_id=f"description:{artifact.skill}",
                recommendation_class="oversized_skill_description",
                priority="worth_doing",
                what=f"{artifact.skill} uses {description_tokens} estimated tokens for discovery description text.",
                why="Discovery metadata may be exposed on every request even when the skill is never selected.",
                suggested_change=(
                    "Keep positive and negative activation boundaries in the description; move workflow detail into SKILL.md."
                ),
                estimated_impact=f"Roughly {savings} fewer discovery tokens per platform.",
                estimated_savings_tokens=savings,
                confidence="high",
                evidence=f"Static frontmatter measurement in {artifact.path}.",
                affected_paths=(artifact.path,),
            )
        )

    max_discovery = max(
        (
            int(platform["totals"]["discovery_tokens"])
            for platform in platforms
            if isinstance(platform["totals"]["discovery_tokens"], int)
        ),
        default=0,
    )
    skill_count = max(
        (int(platform["totals"]["discoverable_skills"]) for platform in platforms),
        default=0,
    )
    if skill_count >= 50 or max_discovery >= math.floor(int(budgets["discovery_tokens"]) * 0.8):
        add(
            Recommendation(
                recommendation_id="metadata:catalog-scale",
                recommendation_class="metadata_explosion",
                priority="highest_impact" if max_discovery > int(budgets["discovery_tokens"]) else "worth_doing",
                what=f"{skill_count} discoverable skills consume up to {max_discovery} estimated tokens.",
                why="Discovery metadata grows with every installed skill and can make all requests heavier.",
                suggested_change=(
                    "Shorten the largest activation descriptions first; consider optional profile-level discovery only when measured growth justifies it."
                ),
                estimated_impact="Reduces context on every request where the host exposes the full catalog.",
                estimated_savings_tokens=None,
                confidence="high",
                evidence="Static count of unique skill name and description frontmatter.",
            )
        )

    bodies = {
        artifact.skill: artifact
        for artifact in artifacts
        if artifact.category == "selected_skill_body" and artifact.skill
    }
    references_by_skill: dict[str, list[Artifact]] = defaultdict(list)
    for artifact in artifacts:
        if artifact.category == "skill_reference" and artifact.skill:
            references_by_skill[artifact.skill].append(artifact)
    for skill, body in bodies.items():
        references = references_by_skill.get(skill, [])
        if body.measurement.tokens > 1400 and not references:
            add(
                Recommendation(
                    recommendation_id=f"body:{skill}",
                    recommendation_class="reference_candidate",
                    priority="worth_doing",
                    what=f"{skill} has a {body.measurement.tokens}-token body and no progressively loaded references.",
                    why="Rare domain guidance may be entering context whenever the skill is selected.",
                    suggested_change=(
                        "Keep the decision procedure in SKILL.md and move clearly separable deep guidance into a reference."
                    ),
                    estimated_impact="Likely reduces selected-skill context; exact savings depend on the split.",
                    estimated_savings_tokens=None,
                    confidence="medium",
                    evidence=f"Static skill and reference inventory for {body.path}.",
                    affected_paths=(body.path,),
                )
            )
        eager_marker = "for every other request" in body.content.lower() or "always read" in body.content.lower()
        for reference in references:
            if reference.measurement.tokens > 1000 and eager_marker and reference.path.endswith("references/routing.md"):
                savings = max(0, reference.measurement.tokens - 700)
                add(
                    Recommendation(
                        recommendation_id=f"eager-reference:{reference.artifact_id}",
                        recommendation_class="reference_loaded_too_eagerly",
                        priority="highest_impact",
                        what=f"{reference.path} is a {reference.measurement.tokens}-token reference directed for every non-help pk request.",
                        why="Rare explicit-mode detail is paid even on ordinary FAST routing.",
                        suggested_change=(
                            "Keep intent and depth selection in routing.md; move detailed mode recipes and examples to a second reference loaded only after that decision."
                        ),
                        estimated_impact=f"Up to about {savings} tokens on common pk invocations.",
                        estimated_savings_tokens=savings,
                        confidence="high",
                        evidence="Static link wording in pk/SKILL.md plus reference size.",
                        affected_paths=(body.path, reference.path),
                    )
                )

    for artifact in artifacts:
        if artifact.category != "agent_instruction" or artifact.measurement.tokens <= 800:
            continue
        agent = str(artifact.metadata.get("agent", artifact.path))
        add(
            Recommendation(
                recommendation_id=f"agent-prompt:{artifact.artifact_id}",
                recommendation_class="agent_prompt_bloat",
                priority="worth_doing",
                what=f"The isolated {agent} agent prompt is {artifact.measurement.tokens} estimated tokens.",
                why="Specialized agents should receive role-specific context instead of a generic engineering handbook.",
                suggested_change=(
                    "Keep role boundaries and proof requirements in the agent definition; move unrelated workflows behind selected skills or references."
                ),
                estimated_impact="Reduces isolated subagent context when this role is spawned; common primary-agent requests are unaffected.",
                estimated_savings_tokens=None,
                confidence="high",
                evidence=f"Static agent adapter measurement in {artifact.path}.",
                affected_paths=(artifact.path,),
            )
        )

    block_locations: dict[str, set[str]] = defaultdict(set)
    block_text: dict[str, str] = {}
    for artifact in artifacts:
        if artifact.category not in {
            "always_on_instruction",
            "selected_skill_body",
            "skill_reference",
            "agent_instruction",
            "platform_adapter",
        }:
            continue
        for block in _normalized_blocks(artifact.content):
            digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
            block_locations[digest].add(artifact.path)
            block_text[digest] = block
    duplicate_groups = [
        (digest, sorted(paths)) for digest, paths in block_locations.items() if len(paths) >= 2
    ]
    duplicate_groups.sort(key=lambda item: (-len(item[1]), item[0]))
    for digest, paths in duplicate_groups[:8]:
        text = block_text[digest]
        if all("/agents/" in f"/{path}" for path in paths):
            # Adapter parity is reported once, with the platform-isolation tradeoff.
            continue
        logical_skill_paths = {
            path.replace(".claude/skills/", ".agents/skills/") for path in paths
        }
        if len(logical_skill_paths) == 1:
            # Claude skill copies and canonical skill roots are mutually exclusive per host.
            continue
        if _safety_sensitive(text) or len(text) < 180:
            protected_repetitions += 1
            continue
        tokens = TokenEstimator().measure(text).tokens
        savings = tokens * (len(paths) - 1)
        add(
            Recommendation(
                recommendation_id=f"duplicate:{digest[:12]}",
                recommendation_class="duplicate_instruction",
                priority="worth_doing" if savings >= 100 else "minor_cleanup",
                what=f"A {tokens}-token instruction block is repeated across {len(paths)} artifacts.",
                why="Large repeated procedure can drift and may load more than once in composed workflows.",
                suggested_change=(
                    "Keep activation boundaries local, but consolidate the shared procedure into one canonical reference where platform reliability allows."
                ),
                estimated_impact=f"Up to about {savings} duplicated tokens across the affected artifacts.",
                estimated_savings_tokens=savings,
                confidence="high",
                evidence="Exact normalized static block match.",
                affected_paths=tuple(paths),
            )
        )

    agent_groups: dict[str, list[Artifact]] = defaultdict(list)
    for artifact in artifacts:
        if artifact.category == "agent_instruction" and artifact.metadata.get("agent"):
            agent_groups[str(artifact.metadata["agent"])].append(artifact)
    repeated_agents = [
        (name, values)
        for name, values in agent_groups.items()
        if len({platform for item in values for platform in item.platforms}) >= 2
    ]
    if repeated_agents:
        paths = tuple(sorted({item.path for _, values in repeated_agents for item in values}))
        add(
            Recommendation(
                recommendation_id="adapter:agent-parity",
                recommendation_class="adapter_duplication",
                priority="minor_cleanup",
                what=f"{len(repeated_agents)} agent roles have self-contained adapters for multiple platforms.",
                why="The duplication is isolated from normal primary-agent context and each host currently requires a self-contained format.",
                suggested_change=(
                    "Intentionally keep the adapters; retain deterministic parity validation and revisit generation only if adapter scale grows."
                ),
                estimated_impact="No common-request token savings; affects isolated agent context and maintenance.",
                estimated_savings_tokens=None,
                confidence="high",
                evidence="Static platform agent inventory grouped by canonical role name.",
                affected_paths=paths,
            )
        )

    descriptions = list(unique_discovery.values())
    overlap_candidates: list[tuple[float, Artifact, Artifact, list[str]]] = []
    for index, left in enumerate(descriptions):
        left_words = _words(str(left.metadata.get("description", "")))
        for right in descriptions[index + 1 :]:
            right_words = _words(str(right.metadata.get("description", "")))
            union = left_words | right_words
            shared = sorted(left_words & right_words)
            score = len(shared) / len(union) if union else 0.0
            if score >= 0.42 and len(shared) >= 5:
                overlap_candidates.append((score, left, right, shared))
    overlap_candidates.sort(key=lambda item: (-item[0], item[1].skill or "", item[2].skill or ""))
    for score, left, right, shared in overlap_candidates[:3]:
        add(
            Recommendation(
                recommendation_id=f"overlap:{left.skill}:{right.skill}",
                recommendation_class="cross_skill_overlap",
                priority="minor_cleanup",
                what=f"{left.skill} and {right.skill} have possible routing overlap.",
                why=f"Their discovery descriptions share: {', '.join(shared[:8])}.",
                suggested_change="Review activation boundaries; keep separate skills when their decisions and negative routes differ.",
                estimated_impact="May reduce accidental multi-skill activation; exact savings depend on host routing.",
                estimated_savings_tokens=None,
                confidence="medium",
                evidence=f"Deterministic description-term overlap ({score:.0%} Jaccard similarity).",
                affected_paths=(left.path, right.path),
            )
        )

    priority_order = {"highest_impact": 0, "worth_doing": 1, "minor_cleanup": 2}
    findings.sort(
        key=lambda finding: (
            priority_order[finding.priority],
            -(finding.estimated_savings_tokens or 0),
            finding.recommendation_id,
        )
    )
    return findings, protected_repetitions


def _summary(
    platforms: Sequence[dict[str, Any]],
    evaluations: Sequence[dict[str, Any]],
    baseline: Mapping[str, Any],
    recommendations: Sequence[Recommendation],
) -> dict[str, Any]:
    exceeded = [item for item in evaluations if item["status"] == "exceeded"]
    watch = [item for item in evaluations if item["status"] == "watch"]
    regressions = [
        item for item in baseline.get("comparisons", []) if item.get("meaningful_regression")
    ]
    incompatible_baseline = baseline.get("status") in {
        "incompatible_estimator",
        "incomplete_baseline",
    }
    if exceeded or regressions or incompatible_baseline:
        status = "needs_attention"
    elif watch:
        status = "watch"
    else:
        status = "healthy"
    actionable = [
        finding
        for finding in recommendations
        if not finding.suggested_change.casefold().startswith("intentionally keep")
    ]
    highest = actionable[0].what if actionable else None
    numeric_savings = [
        finding.estimated_savings_tokens
        for finding in actionable[:5]
        if finding.estimated_savings_tokens
    ]
    return {
        "status": status,
        "platform_count": len(platforms),
        "budget_exceeded_count": len(exceeded),
        "budget_watch_count": len(watch),
        "meaningful_regression_count": len(regressions),
        "highest_value_opportunity": highest,
        "estimated_top_savings_tokens": max(numeric_savings, default=0),
        "powerkit_attributable_only": True,
        "observed_runtime_context": "unavailable",
    }


def audit_context(
    target: Path,
    *,
    platforms: tuple[str, ...] | None = None,
    baseline_path: Path | None = None,
    ci: bool = False,
    estimator: TokenEstimator | None = None,
) -> AuditResult:
    estimator = estimator or TokenEstimator()
    inventory = ContextInventory(target, estimator).build(platforms)
    platform_payloads = [
        _platform_summary(
            inventory.artifacts,
            platform,
            configured=platform in inventory.configured_platforms,
        )
        for platform in inventory.platforms
    ]
    budgets = _configured_budgets(inventory.config)
    evaluations = _evaluate_budgets(platform_payloads, budgets)
    baseline = _baseline_comparison(
        inventory.target,
        baseline_path,
        platform_payloads,
        estimator,
        budgets,
    )
    recommendations, protected_repetitions = _recommendations(
        inventory.artifacts,
        platform_payloads,
        budgets,
    )
    summary = _summary(platform_payloads, evaluations, baseline, recommendations)
    ci_enforced = budgets["policy"] == "fail_ci" or ci
    ci_failed = bool(
        budgets["policy"] != "disabled"
        and ci_enforced
        and (
            any(item["status"] == "exceeded" for item in evaluations)
            or baseline.get("status") in {"incompatible_estimator", "incomplete_baseline"}
            or any(
                item.get("meaningful_regression")
                for item in baseline.get("comparisons", [])
            )
        )
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "scope": {
            "target": str(inventory.target),
            "kind": inventory.source_kind,
            "inventory_source": inventory.inventory_source,
            "install_scope": inventory.scope,
            "profiles": list(inventory.profiles),
            "powerkit_version": inventory.version,
        },
        "estimator": estimator.to_dict(),
        "summary": summary,
        "platforms": platform_payloads,
        "artifacts": [artifact.to_dict() for artifact in inventory.artifacts],
        "recommendations": [finding.to_dict() for finding in recommendations],
        "protected_repetitions": protected_repetitions,
        "budgets": {
            "policy": budgets["policy"],
            "configured": dict(budgets),
            "evaluations": evaluations,
            "ci_enforced": ci_enforced,
            "ci_failed": ci_failed,
        },
        "baseline_comparison": baseline,
        "warnings": [safe_terminal_text(warning) for warning in inventory.warnings],
        "limitations": [
            "Static estimates describe PowerKit-attributable context, not total model input.",
            "Observed loading, activation rates, repeated cross-agent packets, and generated repository context require live-client instrumentation.",
            "No exact tokenizer is assumed because the active host/model tokenizer is not known.",
        ],
    }
    return AuditResult(payload=payload, ci_failed=ci_failed)


def baseline_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    platforms: dict[str, dict[str, int]] = {}
    for platform in report.get("platforms", []):
        if not isinstance(platform, dict) or not isinstance(platform.get("name"), str):
            continue
        values: dict[str, int] = {}
        for metric in METRIC_BUDGET_KEYS:
            current = _metric_value(platform, metric)
            if current is not None:
                values[metric] = current
        if values:
            # Explicitly requested but unconfigured platforms are not measurable and
            # therefore must not become empty, apparently valid baseline entries.
            platforms[platform["name"]] = values
    if not platforms:
        raise ContextAuditError(
            "Cannot write a context baseline because no requested platform is configured and measurable."
        )
    estimator = report.get("estimator", {})
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "powerkit_version": report.get("scope", {}).get(
            "powerkit_version", distribution_version()
        ),
        "estimator": {
            "id": estimator.get("id"),
            "quality": estimator.get("quality"),
        },
        "platforms": platforms,
    }


def write_baseline(target: Path, path: Path, report: Mapping[str, Any]) -> Path:
    target = target.expanduser().resolve()
    destination = path if path.is_absolute() else target / path
    try:
        relative = destination.resolve().relative_to(target)
    except ValueError as exc:
        raise ContextAuditError("Context baseline destination must stay inside the audit target.") from exc
    current = target
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ContextAuditError(f"Refusing symlinked context baseline destination: {current}")
    rendered = json.dumps(baseline_payload(report), indent=2, sort_keys=True) + "\n"
    atomic_write_text(destination, rendered)
    return destination


def _format_tokens(value: int | None) -> str:
    if value is None:
        return "Not measurable"
    return f"~{value:,} estimated tokens"


def _evaluation_status(
    evaluations: Sequence[Mapping[str, Any]], platform: str, metric: str
) -> str:
    match = next(
        (
            item
            for item in evaluations
            if item.get("platform") == platform and item.get("metric") == metric
        ),
        None,
    )
    if match is None:
        return ""
    labels = {
        "within_budget": "✓ within budget",
        "watch": "⚠ nearing budget",
        "exceeded": f"✗ exceeds by ~{match.get('over_by', 0):,}",
        "not_measurable": "· not measurable",
    }
    return labels.get(str(match.get("status")), "")


def render_context_report(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    status_labels = {
        "healthy": "Healthy overall.",
        "watch": "Healthy, with items to watch.",
        "needs_attention": "Needs attention.",
    }
    lines = [
        "PowerKit Context Audit",
        "",
        "Overall",
        f"  {status_labels.get(summary['status'], summary['status'])}",
        "",
        "PowerKit-attributable estimated context",
    ]
    platforms = report["platforms"]
    evaluations = report["budgets"]["evaluations"]
    for platform in platforms:
        name = platform["name"]
        totals = platform["totals"]
        lines.extend(
            [
                "",
                f"{platform['label']}",
                f"  Always loaded     {_format_tokens(totals['always_on_tokens']):<28} {_evaluation_status(evaluations, name, 'always_on_tokens')}",
                f"  Skill discovery   {_format_tokens(totals['discovery_tokens']):<28} {_evaluation_status(evaluations, name, 'discovery_tokens')}",
                f"  Typical FAST      {_format_tokens(platform['paths']['fast']['tokens']):<28} {_evaluation_status(evaluations, name, 'fast_path_tokens')}",
                f"  Typical STANDARD  {_format_tokens(platform['paths']['standard']['tokens']):<28} {_evaluation_status(evaluations, name, 'standard_path_tokens')}",
                f"  Typical DEEP      {_format_tokens(platform['paths']['deep']['tokens']):<28} {_evaluation_status(evaluations, name, 'deep_path_tokens')}",
                f"  Agent prompts     {_format_tokens(totals['agent_instruction_tokens']):<28} · isolated, not in primary path",
            ]
        )

    recommendations = report.get("recommendations", [])
    actionable = [
        finding
        for finding in recommendations
        if not str(finding.get("suggested_change", "")).casefold().startswith("intentionally keep")
    ]
    reviewed_tradeoffs = [finding for finding in recommendations if finding not in actionable]
    lines.extend(["", "Top opportunities"])
    if not actionable:
        lines.append("  No material static context waste detected.")
    else:
        for index, finding in enumerate(actionable[:5], start=1):
            lines.extend(
                [
                    "",
                    f"{index}. {finding['what']}",
                    f"   Why: {finding['why']}",
                    f"   Fix: {finding['suggested_change']}",
                    f"   Impact: {finding['estimated_impact']}",
                    f"   Evidence: {finding['evidence']} ({finding['confidence']} confidence)",
                    "   Safety: review required; no prompt text is auto-rewritten",
                ]
            )
    if reviewed_tradeoffs:
        lines.extend(["", "Reviewed tradeoffs"])
        for finding in reviewed_tradeoffs[:3]:
            lines.append(f"  {finding['what']} {finding['suggested_change']}")

    baseline = report.get("baseline_comparison", {})
    if baseline.get("status") == "compared":
        changed = [item for item in baseline.get("comparisons", []) if item.get("delta")]
        lines.extend(["", "Baseline"])
        if not changed:
            lines.append("  No measured path changes.")
        else:
            for item in changed[:6]:
                sign = "+" if item["delta"] > 0 else ""
                lines.append(
                    f"  {PLATFORM_LABELS.get(item['platform'], item['platform'])} {item['metric']}: "
                    f"{item['baseline']:,} → {item['current']:,} ({sign}{item['delta']:,}, {sign}{item['percent']}%)"
                )
    elif baseline.get("status") == "incompatible_estimator":
        lines.extend(
            [
                "",
                "Baseline",
                "  Cannot compare: the baseline uses a different token estimator.",
            ]
        )
    elif baseline.get("status") == "incomplete_baseline":
        lines.extend(
            [
                "",
                "Baseline",
                f"  Cannot compare: {baseline.get('detail', 'required CI metrics are missing.')}",
            ]
        )

    lines.extend(
        [
            "",
            "What I'd change",
        ]
    )
    if actionable:
        for index, finding in enumerate(actionable[:3], start=1):
            lines.append(f"  {index}. {finding['suggested_change']}")
        savings = int(summary.get("estimated_top_savings_tokens", 0))
        if savings:
            lines.append(f"  Largest single measured opportunity: up to ~{savings:,} estimated tokens.")
    else:
        lines.append("  No prompt changes recommended. Re-run after adding skills, adapters, or persistent instructions.")
    lines.extend(
        [
            "",
            "Notes",
            "  Estimated, not provider-billed. Observed client loading is unavailable.",
            "  Safety and correctness rules are protected from automatic removal.",
        ]
    )
    if report.get("warnings"):
        lines.extend(["", "Warnings"])
        lines.extend(f"  {warning}" for warning in report["warnings"])
    return "\n".join(lines) + "\n"

"""Actionable health checks for installed PowerKit state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from powerkit.installer import (
    START,
    agent_operations,
    command_operations,
    hook_operations,
    has_managed_marker,
    instruction_operations,
    load_command_manifest,
    project_destinations,
    selected_skills,
    verify_removable_asset,
)
from powerkit.resources import catalog, distribution_manifest, distribution_version
from powerkit.state import (
    PROJECT_CONFIG_PATH,
    ProjectSettings,
    load_install_manifest,
    load_project_config,
    settings_from_config,
)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    fix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HealthReport:
    target: str
    version: str | None
    checks: tuple[Check, ...]

    @property
    def healthy(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "version": self.version,
            "healthy": self.healthy,
            "checks": [check.to_dict() for check in self.checks],
        }


def discover_owned_paths(target: Path) -> set[str]:
    owned: set[str] = set()
    for root in (target / ".agents/skills", target / ".claude/skills"):
        if root.is_symlink() or not root.is_dir():
            continue
        for child in root.iterdir():
            if (
                not child.is_symlink()
                and child.is_dir()
                and (child / ".powerkit-origin.json").is_file()
            ):
                owned.add(child.relative_to(target).as_posix())
    for root in (
        target / ".codex/agents",
        target / ".claude/agents",
        target / ".github/agents",
        target / ".github/prompts",
    ):
        if root.is_symlink() or not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_symlink() or not child.is_file():
                continue
            try:
                if has_managed_marker(child.read_text(encoding="utf-8")):
                    owned.add(child.relative_to(target).as_posix())
            except UnicodeDecodeError:
                continue
    for path in (
        target / "AGENTS.md",
        target / "CLAUDE.md",
        target / ".github/copilot-instructions.md",
    ):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            if START in path.read_text(encoding="utf-8"):
                owned.add(path.relative_to(target).as_posix())
        except UnicodeDecodeError:
            continue
    return owned


def expected_asset_kinds(
    target: Path,
    settings: ProjectSettings,
    expected_skills: list[str],
) -> dict[str, str]:
    expected: dict[str, str] = {}
    for skill_root in project_destinations(target, set(settings.platforms)).values():
        for skill in expected_skills:
            expected[(skill_root / skill).relative_to(target).as_posix()] = "skill"
    expected.update(
        {
            destination.relative_to(target).as_posix(): "instruction-block"
            for destination, _ in instruction_operations(
                target, "project", set(settings.platforms)
            )
        }
    )
    if settings.agents:
        agent_ops, _ = agent_operations(target, "project", set(settings.platforms))
        expected.update(
            {
                destination.relative_to(target).as_posix(): "managed-file"
                for _, destination in agent_ops
            }
        )
    command_ops = command_operations(
        target,
        "project",
        set(settings.platforms),
        set(expected_skills),
        load_command_manifest(),
    )
    expected.update(
        {
            destination.relative_to(target).as_posix(): "managed-file"
            for _, destination in command_ops
        }
    )
    if settings.hooks_staged:
        expected.update(
            {
                destination.relative_to(target).as_posix(): "staged-file"
                for _, destination in hook_operations(target, set(settings.platforms))
            }
        )
    return expected


def run_health_checks(target: Path) -> HealthReport:
    target = target.expanduser().resolve()
    checks: list[Check] = []

    try:
        dist = distribution_manifest()
        catalog_payload = catalog()
        version = distribution_version()
        dist_ok = (
            dist.get("powerkit_version") == version
            and catalog_payload.get("version") == version
            and dist.get("bootstrap") == "BOOTSTRAP.md"
        )
        checks.append(
            Check(
                "distribution",
                dist_ok,
                f"PowerKit distribution {version}" if dist_ok else "distribution metadata disagrees",
                None if dist_ok else "Reinstall the pinned PowerKit release.",
            )
        )
    except RuntimeError as exc:
        return HealthReport(
            target=str(target),
            version=None,
            checks=(Check("distribution", False, str(exc), "Reinstall PowerKit."),),
        )

    try:
        config = load_project_config(target)
        assert config is not None
        settings = settings_from_config(config)
        expected_skills = selected_skills(catalog_payload, settings.profiles)
        config_ok = True
        config_detail = (
            f"{', '.join(settings.platforms)}; profiles {', '.join(settings.profiles)}"
        )
    except (RuntimeError, ValueError) as exc:
        config = None
        settings = None
        expected_skills = []
        config_ok = False
        config_detail = str(exc)
    checks.append(
        Check(
            "project configuration",
            config_ok,
            config_detail,
            None if config_ok else "Run `powerkit init` or repair .ai-powerkit/project.json.",
        )
    )

    manifest = load_install_manifest(target)
    manifest_ok = bool(
        manifest
        and manifest.get("toolkit") == "ai-engineering-powerkit"
        and manifest.get("schema_version") in {1, 2}
    )
    checks.append(
        Check(
            "installation manifest",
            manifest_ok,
            (
                f"schema {manifest.get('schema_version')}, version {manifest.get('version')}"
                if manifest_ok and manifest
                else "missing or invalid .ai-powerkit/install-manifest.json"
            ),
            None if manifest_ok else "Run `powerkit sync` after verifying project configuration.",
        )
    )

    if settings and manifest_ok and manifest:
        manifest_source = manifest.get("source")
        state_ok = (
            settings.version == manifest.get("version")
            and isinstance(manifest_source, dict)
            and manifest_source.get("version") == settings.version
            and list(settings.profiles) == manifest.get("profiles")
            and expected_skills == manifest.get("skills")
            and list(settings.platforms) == manifest.get("platforms")
            and settings.agents == bool(manifest.get("agents"))
            and settings.hooks_staged == bool(manifest.get("hooks_staged"))
        )
        checks.append(
            Check(
                "desired state",
                state_ok,
                (
                    f"project and installed state agree at {settings.version}"
                    if state_ok
                    else "project and installed selections differ"
                ),
                None if state_ok else "Run the pinned release's `powerkit sync`.",
            )
        )

        pin_ok = settings.version == version
        checks.append(
            Check(
                "version pin",
                pin_ok,
                (
                    f"running and project versions are {version}"
                    if pin_ok
                    else f"project pins {settings.version}; running distribution is {version}"
                ),
                None if pin_ok else f"Run PowerKit {settings.version}, or deliberately update the pin.",
            )
        )

    if manifest_ok and manifest:
        assets = manifest.get("managed_assets")
        if manifest.get("schema_version") == 1:
            checks.append(
                Check(
                    "managed assets",
                    False,
                    "legacy manifest has no ownership digests",
                    "Run `powerkit sync` to upgrade the installation manifest.",
                )
            )
        elif not isinstance(assets, list):
            checks.append(
                Check(
                    "managed assets",
                    False,
                    "managed_assets must be an array",
                    "Run `powerkit sync` after reviewing the manifest.",
                )
            )
        else:
            failures: list[str] = []
            asset_kinds = {
                str(asset.get("path")): str(asset.get("kind"))
                for asset in assets
                if isinstance(asset, dict) and isinstance(asset.get("path"), str)
            }
            expected_kinds = (
                expected_asset_kinds(target, settings, expected_skills) if settings else {}
            )
            if len(asset_kinds) != len(assets):
                failures.append("manifest contains invalid or duplicate asset paths")
            missing_from_manifest = sorted(expected_kinds.keys() - asset_kinds.keys())
            unexpected_in_manifest = sorted(asset_kinds.keys() - expected_kinds.keys())
            wrong_kinds = sorted(
                path
                for path in expected_kinds.keys() & asset_kinds.keys()
                if expected_kinds[path] != asset_kinds[path]
            )
            untracked_owned = sorted(discover_owned_paths(target) - asset_kinds.keys())
            if missing_from_manifest:
                failures.append(
                    "manifest omits expected assets: " + ", ".join(missing_from_manifest[:3])
                )
            if unexpected_in_manifest:
                failures.append(
                    "manifest contains unexpected assets: "
                    + ", ".join(unexpected_in_manifest[:3])
                )
            if wrong_kinds:
                failures.append(
                    "manifest has incorrect ownership kinds: " + ", ".join(wrong_kinds[:3])
                )
            if untracked_owned:
                failures.append(
                    "owned assets are not tracked by the manifest: "
                    + ", ".join(untracked_owned[:3])
                )
            for asset in assets:
                if not isinstance(asset, dict):
                    failures.append("invalid asset entry")
                    continue
                path, error = verify_removable_asset(target, asset)
                if error:
                    failures.append(error)
                elif path is not None and not path.exists():
                    failures.append(f"missing {asset.get('path')}")
            checks.append(
                Check(
                    "managed assets",
                    not failures,
                    (
                        f"{len(assets)} managed assets verified"
                        if not failures
                        else "; ".join(failures[:5])
                    ),
                    (
                        None
                        if not failures
                        else (
                            "Review and remove or re-adopt untracked legacy assets, then rerun doctor."
                            if untracked_owned
                            else "Run `powerkit sync`; resolve unmanaged conflicts first."
                        )
                    ),
                )
            )

    if config is not None:
        verification = config.get("verification")
        verification_ok = isinstance(verification, dict)
        if verification_ok:
            for level in ("static", "targeted", "broader", "runtime"):
                commands = verification.get(level)
                if not isinstance(commands, list) or any(
                    not isinstance(command, str) or not command.strip()
                    for command in commands
                ):
                    verification_ok = False
                    break
        checks.append(
            Check(
                "verification configuration",
                verification_ok,
                (
                    f"{PROJECT_CONFIG_PATH} verification policy is present"
                    if verification_ok
                    else f"{PROJECT_CONFIG_PATH} verification policy is invalid"
                ),
                None
                if verification_ok
                else "Add a verification object; do not invent unverified commands.",
            )
        )

    return HealthReport(target=str(target), version=version, checks=tuple(checks))

"""Agent-oriented command line interface for AI Engineering PowerKit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from powerkit.health import HealthReport, run_health_checks
from powerkit.installer import InstallRequest, csv_values, execute_install
from powerkit.lifecycle import execute_uninstall
from powerkit.resources import distribution_manifest, distribution_version
from powerkit.state import (
    PROJECT_CONFIG_PATH,
    build_project_config,
    detect_platforms,
    load_install_manifest,
    load_project_config,
    normalize_platforms,
    settings_from_config,
    source_descriptor,
    write_project_config,
)


def target_path(value: Path) -> Path:
    target = value.expanduser().resolve()
    if not target.is_dir():
        raise RuntimeError(f"Target directory does not exist: {target}")
    return target


def comma_values(value: str | None) -> tuple[str, ...]:
    return tuple(csv_values(value or ""))


def default_profiles() -> tuple[str, ...]:
    setup = distribution_manifest().get("default_setup", {})
    profiles = setup.get("profiles", []) if isinstance(setup, dict) else []
    if not isinstance(profiles, list) or not profiles:
        raise RuntimeError("PowerKit distribution has no default profiles.")
    return tuple(str(profile) for profile in profiles)


def stable_version_key(value: str) -> tuple[int, ...] | None:
    parts = value.split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def render_health(report: HealthReport) -> None:
    for check in report.checks:
        print(f"{'✓' if check.ok else '✗'} {check.name}: {check.detail}")
        if not check.ok and check.fix:
            print(f"  Fix: {check.fix}")
    print()
    print("PowerKit is healthy." if report.healthy else "PowerKit needs attention.")


def require_confirmation(args: argparse.Namespace, summary: Sequence[str]) -> None:
    if getattr(args, "dry_run", False) or getattr(args, "yes", False):
        return
    if not sys.stdin.isatty():
        raise RuntimeError("Non-interactive mutation requires `--yes`.")
    print("PowerKit will configure:")
    for item in summary:
        print(f"  {item}")
    answer = input("Continue? [Y/n] ").strip().lower()
    if answer not in {"", "y", "yes"}:
        raise RuntimeError("Cancelled; no changes were made.")


def existing_settings(target: Path) -> tuple[dict[str, Any] | None, Any | None]:
    config = load_project_config(target, required=False)
    if config is None or not isinstance(config.get("powerkit"), dict):
        return config, None
    return config, settings_from_config(config)


def choose_platforms(
    target: Path,
    explicit: str | None,
    configured: Any | None,
) -> tuple[str, ...]:
    if explicit:
        platforms = normalize_platforms(comma_values(explicit))
    elif configured is not None:
        platforms = configured.platforms
    else:
        evidence = detect_platforms(target)
        platforms = tuple(sorted(evidence))
    if not platforms:
        raise RuntimeError(
            "No coding-assistant platform could be inferred. The active agent should pass "
            "`--platforms codex`, `--platforms claude`, or `--platforms copilot`."
        )
    return platforms


def choose_profiles(explicit: str | None, configured: Any | None) -> tuple[str, ...]:
    profiles = comma_values(explicit) if explicit else (
        configured.profiles if configured is not None else default_profiles()
    )
    if not profiles:
        raise RuntimeError("At least one profile is required.")
    return profiles


def command_init(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    existing, configured = existing_settings(target)
    if configured is not None and configured.version != distribution_version():
        raise RuntimeError(
            f"This project pins PowerKit {configured.version}; `init` will not change that pin. "
            "Run that release's `powerkit sync`, or deliberately run `powerkit update` from "
            "the selected new release."
        )
    platforms = choose_platforms(target, args.platforms, configured)
    profiles = choose_profiles(args.profiles, configured)
    agents = configured.agents if configured is not None and args.agents is None else (
        True if args.agents is None else args.agents
    )
    hooks_staged = (
        configured.hooks_staged
        if configured is not None and args.stage_hooks is None
        else bool(args.stage_hooks)
    )
    payload = build_project_config(
        target,
        profiles=profiles,
        platforms=platforms,
        agents=agents,
        hooks_staged=hooks_staged,
        existing=existing,
    )

    require_confirmation(
        args,
        [
            f"target: {target}",
            f"platforms: {', '.join(platforms)}",
            f"profiles: {', '.join(profiles)}",
            f"agents: {'yes' if agents else 'no'}",
            f"project state: {PROJECT_CONFIG_PATH}",
        ],
    )
    result = execute_install(
        InstallRequest(
            base=target,
            profiles=profiles,
            platforms=frozenset(platforms),
            include_agents=agents,
            stage_hooks=hooks_staged,
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
        )
    )
    config_changed = write_project_config(target, payload, dry_run=args.dry_run)
    changed = result.changed or config_changed

    if args.dry_run:
        print(
            f"Dry run complete: {len(result.skills)} skills for {', '.join(platforms)}; "
            f"changes {'required' if changed else 'not required'}."
        )
        return 0

    report = run_health_checks(target)
    print(f"PowerKit {result.version} {'configured' if changed else 'already current'}.")
    print(f"Platforms: {', '.join(platforms)}")
    print(f"Capabilities: {len(result.skills)} skills; agents {'enabled' if agents else 'disabled'}")
    print(f"Verification: {'healthy' if report.healthy else 'needs attention'}")
    print()
    print("Ready: invoke `/pk` (or the platform's native `pk` skill command) and describe the task.")
    return 0 if report.healthy else 1


def command_sync(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    config = load_project_config(target)
    assert config is not None
    settings = settings_from_config(config)
    running_version = distribution_version()
    if settings.version != running_version:
        raise RuntimeError(
            f"Project pins PowerKit {settings.version}, but the running distribution is "
            f"{running_version}. Resolve and run the pinned release, or use `powerkit update` "
            "from the deliberately selected new release."
        )
    result = execute_install(
        InstallRequest(
            base=target,
            profiles=settings.profiles,
            platforms=frozenset(settings.platforms),
            include_agents=settings.agents,
            stage_hooks=settings.hooks_staged,
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
        )
    )
    if args.dry_run:
        print(f"Dry run complete: sync {'would change files' if result.changed else 'is current'}.")
        return 0
    report = run_health_checks(target)
    print(f"PowerKit {running_version} {'synchronized' if result.changed else 'already current'}.")
    print(f"Verification: {'healthy' if report.healthy else 'needs attention'}")
    return 0 if report.healthy else 1


def status_payload(target: Path) -> dict[str, Any]:
    config = load_project_config(target, required=False)
    manifest = load_install_manifest(target)
    running = distribution_version()
    if config is None and manifest is None:
        return {
            "state": "not-installed",
            "running_version": running,
            "target": str(target),
            "detected_platforms": detect_platforms(target),
        }
    if config is None or manifest is None:
        return {
            "state": "partial",
            "running_version": running,
            "target": str(target),
            "project_config": bool(config),
            "install_manifest": bool(manifest),
        }
    try:
        settings = settings_from_config(config)
    except RuntimeError as exc:
        return {
            "state": "invalid",
            "running_version": running,
            "target": str(target),
            "error": str(exc),
        }
    report = run_health_checks(target)
    if settings.version != manifest.get("version"):
        state = "partial"
    elif settings.version != running:
        pinned_key = stable_version_key(settings.version)
        running_key = stable_version_key(running)
        if pinned_key is not None and running_key is not None and pinned_key < running_key:
            state = "update-available"
        elif pinned_key is not None and running_key is not None and pinned_key > running_key:
            state = "running-older-than-pin"
        else:
            state = "pinned-other-version"
    else:
        state = "current" if report.healthy else "unhealthy"
    skills = manifest.get("skills")
    return {
        "state": state,
        "running_version": running,
        "installed_version": manifest.get("version"),
        "pinned_version": settings.version,
        "target": str(target),
        "profiles": list(settings.profiles),
        "platforms": list(settings.platforms),
        "skills": len(skills) if isinstance(skills, list) else None,
        "agents": settings.agents,
        "healthy": report.healthy,
    }


def command_status(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    payload = status_payload(target)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"PowerKit {payload['running_version']}")
        print(f"State: {payload['state']}")
        if payload.get("pinned_version"):
            print(f"Pinned: {payload['pinned_version']}")
        if payload.get("profiles"):
            print(f"Profiles: {', '.join(payload['profiles'])}")
        if payload.get("platforms"):
            print(f"Platforms: {', '.join(payload['platforms'])}")
        if payload.get("skills") is not None:
            print(f"Skills: {payload['skills']}")
    return 0 if payload["state"] in {"current", "not-installed"} else 1


def command_doctor(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    report = run_health_checks(target)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        render_health(report)
    return 0 if report.healthy else 1


def command_update(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    selected_version = args.version or distribution_version()
    running_version = distribution_version()
    if selected_version != running_version:
        raise RuntimeError(
            f"This distribution is PowerKit {running_version}; it cannot install {selected_version}. "
            "Resolve the requested tagged release first, then rerun its update command."
        )
    config = load_project_config(target)
    assert config is not None
    settings = settings_from_config(config)
    require_confirmation(
        args,
        [
            f"target: {target}",
            f"version: {settings.version} → {running_version}",
            f"platforms: {', '.join(settings.platforms)}",
        ],
    )
    result = execute_install(
        InstallRequest(
            base=target,
            profiles=settings.profiles,
            platforms=frozenset(settings.platforms),
            include_agents=settings.agents,
            stage_hooks=settings.hooks_staged,
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
        )
    )
    updated = dict(config)
    powerkit = dict(updated["powerkit"])
    powerkit["version"] = running_version
    powerkit["source"] = source_descriptor(running_version)
    updated["powerkit"] = powerkit
    config_changed = write_project_config(target, updated, dry_run=args.dry_run)
    if args.dry_run:
        print(
            f"Dry run complete: update {'would change files' if result.changed or config_changed else 'is current'}."
        )
        return 0
    report = run_health_checks(target)
    print(f"PowerKit updated to {running_version}.")
    print(f"Verification: {'healthy' if report.healthy else 'needs attention'}")
    return 0 if report.healthy else 1


def command_uninstall(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    require_confirmation(
        args,
        [
            f"target: {target}",
            "only assets proven owned by the installation manifest",
            (
                "project configuration: remove"
                if args.purge_config
                else "project configuration: preserve"
            ),
        ],
    )
    result = execute_uninstall(
        target,
        dry_run=args.dry_run,
        purge_config=args.purge_config,
        verbose=args.verbose,
    )
    action = "would remove" if args.dry_run else "removed"
    print(f"PowerKit {action} {len(result.removed)} managed assets.")
    if result.preserved_config:
        print(f"Preserved team configuration: {PROJECT_CONFIG_PATH}")
    return 0


def command_config(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    config = load_project_config(target)
    assert config is not None
    if args.path:
        print(target / PROJECT_CONFIG_PATH)
    else:
        print(json.dumps(config, indent=2))
    return 0


def command_version(args: argparse.Namespace) -> int:
    del args
    print(distribution_version())
    return 0


def add_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", type=Path, default=Path("."))


def add_install_options(parser: argparse.ArgumentParser) -> None:
    add_target(parser)
    parser.add_argument("--platforms", help="Comma-separated: codex, claude, copilot")
    parser.add_argument("--profiles", help="Comma-separated PowerKit profiles")
    agents = parser.add_mutually_exclusive_group()
    agents.add_argument("--agents", dest="agents", action="store_true")
    agents.add_argument("--no-agents", dest="agents", action="store_false")
    parser.set_defaults(agents=None, stage_hooks=None)
    parser.add_argument("--stage-hooks", action="store_true", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Approve non-interactive changes")
    parser.add_argument("--force", action="store_true", help="Overwrite reviewed conflicts")
    parser.add_argument("--verbose", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="powerkit",
        description="Deterministic bootstrap tooling for AI Engineering PowerKit agents.",
    )
    parser.add_argument("--version", action="version", version=distribution_version())
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "install"):
        command = subparsers.add_parser(
            name,
            help="Create or refresh project PowerKit configuration",
        )
        add_install_options(command)
        command.set_defaults(handler=command_init)

    sync = subparsers.add_parser("sync", help="Reconcile managed assets from project state")
    add_target(sync)
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--force", action="store_true", help="Overwrite reviewed conflicts")
    sync.add_argument("--verbose", action="store_true")
    sync.set_defaults(handler=command_sync)

    status = subparsers.add_parser("status", help="Show concise project installation state")
    add_target(status)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=command_status)

    doctor = subparsers.add_parser("doctor", help="Validate configuration and managed assets")
    add_target(doctor)
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=command_doctor)

    update = subparsers.add_parser("update", help="Apply a deliberately resolved release")
    add_target(update)
    update.add_argument("--version")
    update.add_argument("--dry-run", action="store_true")
    update.add_argument("--yes", action="store_true")
    update.add_argument("--force", action="store_true", help="Overwrite reviewed conflicts")
    update.add_argument("--verbose", action="store_true")
    update.set_defaults(handler=command_update)

    uninstall = subparsers.add_parser("uninstall", help="Remove only proven managed assets")
    add_target(uninstall)
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--yes", action="store_true")
    uninstall.add_argument("--purge-config", action="store_true")
    uninstall.add_argument("--verbose", action="store_true")
    uninstall.set_defaults(handler=command_uninstall)

    config = subparsers.add_parser("config", help="Print project PowerKit configuration")
    add_target(config)
    config.add_argument("--path", action="store_true")
    config.set_defaults(handler=command_config)

    version = subparsers.add_parser("version", help="Print the running distribution version")
    version.set_defaults(handler=command_version)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

"""Agent-oriented command line interface for AI Engineering PowerKit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from powerkit.broker import (
    CONSTRAINTS,
    CONTROL_PLANES,
    EFFORTS,
    RISKS,
    TASK_TRAITS,
    build_launch_plan,
    capability_report,
    configured_execution_policy,
    execute_launch,
    inspect_launcher_client,
    load_trace_binding,
    public_launch_plan,
    render_capability_report,
    render_compact_policy,
    render_explanation,
    resolve_policy,
    write_trace,
)
from powerkit.certification import (
    build_pilot_result,
    load_case_corpus,
    load_trace as load_certification_trace,
    pilot_exit_code,
    render_pilot_result,
)
from powerkit.context_budget import (
    DEFAULT_BASELINE_PATH,
    audit_context,
    normalize_platforms as normalize_audit_platforms,
    render_context_report,
    safe_terminal_text,
    write_baseline,
)
from powerkit.health import HealthReport, run_health_checks
from powerkit.installer import InstallRequest, csv_values, execute_install
from powerkit.lifecycle import execute_uninstall
from powerkit.proof import (
    build_proof,
    configured_proof_root,
    delete_proof,
    load_proof,
    load_task_spec,
    open_report,
    proof_directories,
    proof_freshness,
    refresh_report,
    render_completion_brief,
    resolve_proof_directory,
)
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
from powerkit.verification import (
    load_evidence,
    repository_fingerprint,
    run_verification,
    utc_now as verification_utc_now,
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
        symbol = "✗" if not check.ok else ("⚠" if check.warning else "✓")
        name = safe_terminal_text(check.name)
        detail = safe_terminal_text(check.detail)
        print(f"{symbol} {name}: {detail}")
        if check.fix and (not check.ok or check.warning):
            print(f"  Fix: {safe_terminal_text(check.fix)}")
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


def command_certify_pilot(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    corpus_path = args.corpus
    if corpus_path is not None and not corpus_path.is_absolute():
        corpus_path = target / corpus_path
    corpus = load_case_corpus(corpus_path, asset_root=target if corpus_path else None)
    cases = {case["id"]: case for case in corpus["cases"]}
    traces = []
    for path in args.trace or ():
        trace_path = path if path.is_absolute() else target / path
        traces.append(load_certification_trace(trace_path, cases))
    result = build_pilot_result(corpus, traces)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_pilot_result(result), end="")
    return pilot_exit_code(result)


def broker_platforms(values: Sequence[str] | None) -> tuple[str, ...]:
    raw: list[str] = []
    for value in values or ("codex,claude,copilot",):
        raw.extend(comma_values(value))
    normalized = tuple(dict.fromkeys(value.lower() for value in raw))
    unknown = sorted(set(normalized) - {"codex", "claude", "copilot"})
    if unknown:
        raise RuntimeError("Unknown broker platforms: " + ", ".join(unknown))
    return normalized


def broker_surface_filters(
    values: Sequence[str] | None, platforms: Sequence[str]
) -> dict[str, tuple[str, ...]] | None:
    if not values:
        return None
    filters: dict[str, list[str]] = {platform: [] for platform in platforms}
    for raw in values:
        if ":" in raw:
            platform, surface = raw.split(":", 1)
            platform = platform.strip().lower()
        elif len(platforms) == 1:
            platform, surface = platforms[0], raw
        else:
            raise RuntimeError(
                "Broker surfaces must use platform:surface when more than one platform is selected."
            )
        if platform not in filters or not surface.strip():
            raise RuntimeError(f"Invalid broker surface selector: {raw!r}")
        filters[platform].append(surface.strip())
    return {platform: tuple(surfaces) for platform, surfaces in filters.items() if surfaces}


def command_broker_capabilities(args: argparse.Namespace) -> int:
    platforms = broker_platforms(args.platform)
    report = capability_report(
        platforms,
        surface_filters=broker_surface_filters(args.surface, platforms),
        probe=bool(args.probe),
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_capability_report(report), end="")
    return 0


def command_broker_explain(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    report = resolve_policy(
        effort=args.effort,
        risk=args.risk,
        platform=args.platform,
        surface=args.surface,
        control_plane=args.control_plane,
        constraints=args.constraint or (),
        traits=args.trait or (),
        project_policy=configured_execution_policy(target),
        reasons=args.reason or (),
        client_version=args.client_version,
    )
    if args.trace:
        if not args.task_id:
            raise RuntimeError("Broker traces require --task-id.")
        report["trace"] = {
            "path": args.trace.as_posix(),
            "task_id": args.task_id,
        }
        write_trace(target, args.trace, report)
    if args.json:
        print(json.dumps(report, indent=2))
    elif args.compact:
        print(render_compact_policy(report), end="")
    else:
        print(render_explanation(report), end="")
        if args.trace:
            print(f"Broker trace: {report['trace']['path']}")
    return {"STOP": 3, "CHECKPOINT": 4}.get(report["negotiation"]["decision"], 0)


def command_broker_launch(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    selected_surface = args.surface or "cli"
    if selected_surface != "cli":
        raise RuntimeError("Local broker launch requires --surface cli.")
    resolution_inputs = {
        "effort": args.effort,
        "risk": args.risk,
        "platform": args.platform,
        "surface": selected_surface,
        "control_plane": "LAUNCHER",
        "constraints": args.constraint or (),
        "traits": args.trait or (),
        "project_policy": configured_execution_policy(target),
        "reasons": args.reason or (),
    }
    report = resolve_policy(**resolution_inputs)
    if report["negotiation"]["decision"] == "STOP":
        print(render_explanation(report), end="")
        return 3
    client_path, client_version = inspect_launcher_client(
        args.platform, target, args.client
    )
    report = resolve_policy(
        **resolution_inputs,
        client_version=client_version,
    )
    decision = report["negotiation"]["decision"]
    if decision == "STOP":
        print(render_explanation(report), end="")
        return 3
    if decision == "CHECKPOINT" and not args.ack_checkpoint and not args.dry_run:
        print(render_explanation(report), end="")
        return 4
    client_args = list(args.client_args or ())
    if client_args[:1] == ["--"]:
        client_args = client_args[1:]
    plan = build_launch_plan(
        report,
        target,
        client_args,
        client=client_path,
        checkpoint_acknowledged=bool(args.ack_checkpoint),
    )
    if args.dry_run:
        report["application"] = public_launch_plan(plan)
        if args.trace:
            if not args.task_id:
                raise RuntimeError("Broker traces require --task-id.")
            report["trace"] = {
                "path": args.trace.as_posix(),
                "task_id": args.task_id,
            }
            write_trace(target, args.trace, report)
        print(json.dumps(report, indent=2) if args.json else json.dumps(report["application"], indent=2))
        return 0
    exit_code = execute_launch(plan, target)
    application_status = "CLIENT_SUCCEEDED" if exit_code == 0 else "CLIENT_FAILED"
    settings_status = "SETTINGS_PASSED" if exit_code == 0 else "APPLICATION_ATTEMPTED"
    report["application"] = public_launch_plan(
        plan,
        status=application_status,
        settings_status=settings_status,
    )
    report["application"]["exit_code"] = exit_code
    for item in report["application"]["settings"]:
        report["negotiation"]["controls"][item["control"]]["enforcement_status"] = (
            "APPLICATION_ATTEMPTED"
        )
    if args.trace:
        if not args.task_id:
            raise RuntimeError("Broker traces require --task-id.")
        report["trace"] = {
            "path": args.trace.as_posix(),
            "task_id": args.task_id,
        }
        write_trace(target, args.trace, report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Broker launch status: {application_status}; client exit: {exit_code}")
    return exit_code


def proof_levels(depth: str, explicit: str | None) -> tuple[str, ...]:
    if explicit:
        return tuple(item.strip() for item in explicit.split(",") if item.strip())
    return {
        "FAST": ("targeted",),
        "STANDARD": ("static", "targeted"),
        "DEEP": ("static", "targeted", "broader", "runtime"),
        "HIGH_RISK": ("static", "targeted", "broader", "runtime"),
    }[depth]


def empty_verification_evidence(target: Path, levels: Sequence[str]) -> dict[str, Any]:
    records = [
        {
            "level": level,
            "label": f"{level.title()} verification",
            "status": "skipped",
            "reason": "No PowerKit project verification config was available.",
            "command": None,
            "exit_code": None,
            "duration_seconds": None,
            "started_at": None,
            "provenance": "configured-command-runner",
        }
        for level in levels
    ]
    return {
        "format": "powerkit-verification-evidence",
        "schema_version": 1,
        "generated_at": verification_utc_now(),
        "repository": repository_fingerprint(target),
        "requested_levels": list(levels),
        "records": records,
        "summary": {"executed": 0, "passed": 0, "failed": 0, "skipped": len(records)},
    }


def command_proof_create(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    spec_path = args.input if args.input.is_absolute() else target / args.input
    spec = load_task_spec(spec_path)
    execution_policy = None
    if args.broker_trace:
        execution_policy = load_trace_binding(
            target,
            args.broker_trace,
            spec["task"]["depth"],
            spec["task"]["id"],
        )
    root = configured_proof_root(target, args.output)
    levels = proof_levels(spec["task"]["depth"], args.levels)
    verification_exit = 0
    trust_current_run = False
    if args.evidence:
        evidence_path = args.evidence if args.evidence.is_absolute() else target / args.evidence
        evidence = load_evidence(evidence_path)
    else:
        config_path = args.config if args.config.is_absolute() else target / args.config
        if config_path.is_file():
            evidence, verification_exit = run_verification(
                target,
                config_path,
                levels,
                timeout=args.timeout,
                keep_going=args.keep_going,
                allow_empty=args.allow_empty,
                stream=args.stream_output,
            )
            trust_current_run = True
        elif args.allow_empty:
            evidence = empty_verification_evidence(target, levels)
            trust_current_run = True
        else:
            raise RuntimeError(
                f"Verification config does not exist: {config_path}. "
                "Use --allow-empty only when missing proof is intentional."
            )
    proof_dir, proof = build_proof(
        target,
        spec,
        evidence,
        output_root=root,
        replace=args.replace,
        explicit_html=args.html,
        trust_current_run=trust_current_run,
        execution_policy=execution_policy,
    )
    print()
    print(render_completion_brief(proof), end="")
    print()
    print(f"Machine proof: {proof_dir / 'proof.json'}")
    report = proof["presentation"]["report"]
    if report.get("status") == "generated":
        print(f"Proof Report: {proof_dir / 'report.html'}")
    elif report.get("status") == "failed":
        print(
            "Implementation evidence was preserved, but the Proof Report could not be generated: "
            f"{report.get('error')}"
        )
    if any(record.get("status") in {"failed", "timed_out"} for record in proof["verification"]):
        verification_exit = verification_exit or 1
    return verification_exit


def command_proof_list(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    root = configured_proof_root(target, args.output)
    rows = []
    for proof_dir in proof_directories(root):
        try:
            proof = load_proof(proof_dir)
            freshness = proof_freshness(target, proof, proof_dir)
        except RuntimeError as exc:
            rows.append({"id": proof_dir.name, "state": "invalid", "error": str(exc)})
            continue
        rows.append(
            {
                "id": proof["task"]["id"],
                "title": proof["task"]["title"],
                "outcome": proof["outcome"]["status"],
                "freshness": freshness["status"],
                "generated_at": proof["generated_at"],
            }
        )
    if args.json:
        print(json.dumps({"proofs": rows}, indent=2))
    elif not rows:
        print(f"No proofs found under {root}")
    else:
        for row in rows:
            if row.get("state") == "invalid":
                print(f"{row['id']}: invalid — {row['error']}")
            else:
                print(
                    f"{row['id']}: {row['title']} — "
                    f"{row['outcome'].lower().replace('_', ' ')} · {row['freshness']}"
                )
    return 0


def command_proof_show(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    root = configured_proof_root(target, args.output)
    proof_dir = resolve_proof_directory(target, args.task_id, output_root=root)
    proof = load_proof(proof_dir)
    freshness = proof_freshness(target, proof, proof_dir)
    report_path: Path | None = None
    if args.refresh_report:
        report_path = refresh_report(target, proof_dir, proof)
    if args.open:
        report_path = open_report(target, proof_dir, proof)
    if args.json:
        print(json.dumps({"proof": proof, "current_freshness": freshness}, indent=2))
    else:
        print(render_completion_brief(proof), end="")
        print()
        if freshness["status"] == "stale":
            print("Freshness: This proof no longer matches the current code.")
            for path in freshness["changed_files"]:
                print(f"  changed: {path}")
        else:
            print(f"Freshness: {freshness['status']}")
        print(f"Machine proof: {proof_dir / 'proof.json'}")
        report = proof.get("presentation", {}).get("report", {})
        if isinstance(report, dict) and report.get("path") == "report.html":
            print(f"Proof Report: {report_path or proof_dir / 'report.html'}")
    return 0 if freshness["status"] == "current" else 1


def command_proof_delete(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    root = configured_proof_root(target, args.output)
    proof_dir = resolve_proof_directory(target, args.task_id, output_root=root)
    require_confirmation(args, [f"delete generated proof: {proof_dir}"])
    if args.dry_run:
        print(f"Would delete proof: {proof_dir}")
        return 0
    deleted = delete_proof(target, root, args.task_id)
    print(f"Deleted proof: {deleted}")
    return 0


def command_context_audit(args: argparse.Namespace) -> int:
    target = target_path(args.target)
    platforms = (
        normalize_audit_platforms(part for value in args.platform for part in value.split(","))
        if args.platform
        else None
    )
    try:
        result = audit_context(
            target,
            platforms=platforms,
            baseline_path=args.baseline,
            ci=bool(args.ci),
        )
        if args.write_baseline is not None:
            destination = write_baseline(target, args.write_baseline, result.payload)
            result.payload["baseline_written"] = str(destination.relative_to(target))
    except RuntimeError as exc:
        raise RuntimeError(safe_terminal_text(str(exc))) from exc
    if args.json:
        print(json.dumps(result.payload, indent=2))
    else:
        print(render_context_report(result.payload), end="")
        if args.write_baseline is not None:
            print(f"Baseline written: {result.payload['baseline_written']}")
    return 1 if result.ci_failed else 0


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

    certify = subparsers.add_parser(
        "certify", help="Plan and score live-client certification evidence"
    )
    certify_commands = certify.add_subparsers(dest="certify_command", required=True)
    pilot = certify_commands.add_parser(
        "pilot", help="Validate the six-case pilot or score supplied paired traces"
    )
    add_target(pilot)
    pilot.add_argument(
        "--corpus",
        type=Path,
        help="Versioned case corpus (default: bundled six-case pilot)",
    )
    pilot.add_argument(
        "--trace",
        type=Path,
        action="append",
        help="Certification trace to score; repeat for each run",
    )
    pilot.add_argument("--json", action="store_true", help="Print the stable result contract")
    pilot.set_defaults(handler=command_certify_pilot)

    broker = subparsers.add_parser(
        "broker",
        help="Resolve execution policy and inspect platform capabilities",
    )
    broker_commands = broker.add_subparsers(dest="broker_command", required=True)
    capabilities = broker_commands.add_parser(
        "capabilities",
        help="Show documented platform capability contracts",
    )
    capabilities.add_argument(
        "--platform",
        action="append",
        help="codex, claude, copilot, or a comma-separated list (default: all)",
    )
    capabilities.add_argument(
        "--surface",
        action="append",
        help="surface or platform:surface; repeat for multiple surfaces",
    )
    capabilities.add_argument(
        "--probe",
        action="store_true",
        help="Actively run bounded version commands from allowlisted local client paths",
    )
    capabilities.add_argument("--json", action="store_true", help="Print stable JSON")
    capabilities.set_defaults(handler=command_broker_capabilities)

    explain = broker_commands.add_parser(
        "explain",
        help="Resolve desired and effective execution policy from router output",
    )
    add_target(explain)
    explain.add_argument("--effort", required=True, choices=EFFORTS)
    explain.add_argument("--risk", required=True, choices=RISKS)
    explain.add_argument(
        "--platform", required=True, choices=("codex", "claude", "copilot")
    )
    explain.add_argument("--surface")
    explain.add_argument(
        "--control-plane",
        default="CURRENT_SESSION",
        choices=CONTROL_PLANES,
        help="CURRENT_SESSION for $pk, LAUNCHER when starting a new host task",
    )
    explain.add_argument(
        "--constraint",
        action="append",
        choices=CONSTRAINTS,
        help="Explicit user constraint; repeat as needed",
    )
    explain.add_argument(
        "--trait",
        action="append",
        choices=TASK_TRAITS,
        help="Risk/work trait selected by the workload router; repeat as needed",
    )
    explain.add_argument(
        "--reason",
        action="append",
        help="Human-readable routing reason; repeat as needed",
    )
    explain.add_argument(
        "--client-version",
        help="Known client version; unvalidated versions degrade to behavioral fallback",
    )
    output = explain.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print stable JSON")
    output.add_argument("--compact", action="store_true", help="Print the small agent directive")
    explain.add_argument(
        "--trace",
        type=Path,
        help="Write JSON under .ai-powerkit/traces/",
    )
    explain.add_argument("--task-id", help="Proof task identity recorded in --trace")
    explain.set_defaults(handler=command_broker_explain)

    launch = broker_commands.add_parser(
        "launch",
        help="Resolve policy, pass supported settings, and start an allowlisted local client",
    )
    add_target(launch)
    launch.add_argument("--effort", required=True, choices=EFFORTS)
    launch.add_argument("--risk", required=True, choices=RISKS)
    launch.add_argument("--platform", required=True, choices=("codex", "claude"))
    launch.add_argument("--surface")
    launch.add_argument("--constraint", action="append", choices=CONSTRAINTS)
    launch.add_argument("--trait", action="append", choices=TASK_TRAITS)
    launch.add_argument("--reason", action="append")
    launch.add_argument("--client", type=Path, help="Absolute trusted client executable")
    launch.add_argument("--ack-checkpoint", action="store_true")
    launch.add_argument("--dry-run", action="store_true")
    launch.add_argument("--json", action="store_true")
    launch.add_argument("--trace", type=Path)
    launch.add_argument("--task-id", help="Proof task identity recorded in --trace")
    launch.add_argument(
        "client_args",
        nargs=argparse.REMAINDER,
        help="Client arguments after --; broker-controlled flags are rejected",
    )
    launch.set_defaults(handler=command_broker_launch)

    proof = subparsers.add_parser("proof", help="Create and inspect local completion proof")
    proof_subparsers = proof.add_subparsers(dest="proof_command", required=True)

    proof_create = proof_subparsers.add_parser(
        "create", help="Run or import verification and build a Proof Pack"
    )
    add_target(proof_create)
    proof_create.add_argument("--input", type=Path, required=True, help="Proof task specification")
    proof_create.add_argument("--config", type=Path, default=PROJECT_CONFIG_PATH)
    proof_create.add_argument("--levels", help="Comma-separated verification levels")
    proof_create.add_argument("--timeout", type=int, default=900)
    proof_create.add_argument("--keep-going", action="store_true")
    proof_create.add_argument("--allow-empty", action="store_true")
    proof_create.add_argument(
        "--stream-output",
        action="store_true",
        help="Stream trusted verification command output to the terminal",
    )
    proof_create.add_argument("--evidence", type=Path, help="Previously recorded execution evidence")
    proof_create.add_argument(
        "--broker-trace",
        type=Path,
        help="Bind the proof to a compatible trace under .ai-powerkit/traces/",
    )
    proof_create.add_argument("--html", action="store_true", help="Generate HTML for STANDARD work")
    proof_create.add_argument("--replace", action="store_true")
    proof_create.add_argument("--output", type=Path)
    proof_create.set_defaults(handler=command_proof_create)

    proof_list = proof_subparsers.add_parser("list", help="List generated proofs")
    add_target(proof_list)
    proof_list.add_argument("--output", type=Path)
    proof_list.add_argument("--json", action="store_true")
    proof_list.set_defaults(handler=command_proof_list)

    proof_show = proof_subparsers.add_parser("show", help="Show a proof and check freshness")
    proof_show.add_argument("task_id", help="Proof task id or latest")
    add_target(proof_show)
    proof_show.add_argument("--output", type=Path)
    proof_show.add_argument("--json", action="store_true")
    proof_show.add_argument("--refresh-report", action="store_true")
    proof_show.add_argument("--open", action="store_true")
    proof_show.set_defaults(handler=command_proof_show)

    proof_delete = proof_subparsers.add_parser("delete", help="Delete one generated proof")
    proof_delete.add_argument("task_id")
    add_target(proof_delete)
    proof_delete.add_argument("--output", type=Path)
    proof_delete.add_argument("--dry-run", action="store_true")
    proof_delete.add_argument("--yes", action="store_true")
    proof_delete.set_defaults(handler=command_proof_delete)
    context = subparsers.add_parser(
        "context",
        help="Inspect PowerKit-attributable coding-agent context",
    )
    context_commands = context.add_subparsers(dest="context_command", required=True)
    audit = context_commands.add_parser(
        "audit",
        help="Measure context layers and recommend safe progressive-disclosure improvements",
    )
    add_target(audit)
    audit.add_argument(
        "--platform",
        action="append",
        help="codex, claude, copilot, or all; repeat or comma-separate values",
    )
    audit.add_argument("--json", action="store_true", help="Print the stable JSON report")
    audit.add_argument(
        "--ci",
        action="store_true",
        help="Fail on configured budget breaches or meaningful baseline regressions",
    )
    audit.add_argument(
        "--baseline",
        type=Path,
        help=f"Compare with a baseline (default: {DEFAULT_BASELINE_PATH})",
    )
    audit.add_argument(
        "--write-baseline",
        type=Path,
        nargs="?",
        const=DEFAULT_BASELINE_PATH,
        help=f"Write a static baseline (default: {DEFAULT_BASELINE_PATH})",
    )
    audit.set_defaults(handler=command_context_audit)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except RuntimeError as exc:
        print(f"error: {safe_terminal_text(str(exc))}", file=sys.stderr)
        return 2

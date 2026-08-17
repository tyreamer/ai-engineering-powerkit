"""Canonical PowerKit proof manifests and lifecycle."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import shutil
import tempfile
import webbrowser
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from powerkit.installer import atomic_write_text
from powerkit.privacy import redact_text, redact_value
from powerkit.verification import repository_fingerprint


PROOF_SCHEMA_VERSION = 1
PROOF_ROOT = Path(".ai-powerkit/proofs")
DEPTHS = {"FAST", "STANDARD", "DEEP", "HIGH_RISK"}
IMPLEMENTATION_STATES = {"complete", "partial", "analysis"}
VERIFICATION_STATES = {"passed", "failed", "timed_out", "skipped"}
REQUIRED_LEVELS = {
    "FAST": {"targeted"},
    "STANDARD": {"static", "targeted"},
    "DEEP": {"static", "targeted", "broader", "runtime"},
    "HIGH_RISK": {"static", "targeted", "broader", "runtime"},
}
STATUS_LABELS = {
    "IMPLEMENTED": "Complete",
    "PARTIALLY_VERIFIED": "Implemented; verification is partial",
    "VERIFIED": "Complete and verified",
    "VERIFIED_WITH_CAVEATS": "Verified with caveats",
    "FAILED_VERIFICATION": "Verification failed",
    "UNABLE_TO_VERIFY": "Implemented; unable to verify",
}
TASK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
MAX_ARTIFACTS = 100
MAX_ARTIFACT_BYTES = 25 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 100 * 1024 * 1024


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label.title()} must be a JSON object: {path}")
    return payload


def _required_text(payload: dict[str, Any], field: str, label: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} requires a non-empty `{field}` string.")
    return redact_text(value.strip())


def _text_list(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise RuntimeError(f"{label} must be an array of non-empty strings.")
    return [redact_text(item.strip()) for item in value]


def load_task_spec(path: Path) -> dict[str, Any]:
    raw = read_json_object(path, "proof task specification")
    if raw.get("schema_version") != 1:
        raise RuntimeError(
            f"Unsupported proof task specification schema: {raw.get('schema_version')!r}"
        )
    task = raw.get("task")
    if not isinstance(task, dict):
        raise RuntimeError("Proof task specification requires a `task` object.")
    task_id = _required_text(task, "id", "task")
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise RuntimeError(
            "task.id must start with a lowercase letter or digit and contain only "
            "lowercase letters, digits, dots, underscores, or hyphens."
        )
    depth_value = task.get("depth")
    depth = depth_value.strip().upper() if isinstance(depth_value, str) else ""
    if depth not in DEPTHS:
        raise RuntimeError(f"task.depth must be one of: {', '.join(sorted(DEPTHS))}.")
    raw_types = task.get("types", ["general"])
    if not isinstance(raw_types, list) or not raw_types:
        raise RuntimeError("task.types must be a non-empty array.")
    task_types = tuple(dict.fromkeys(str(item).strip().lower() for item in raw_types))
    invalid_types = sorted(
        task_type
        for task_type in task_types
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", task_type)
    )
    if invalid_types:
        raise RuntimeError(f"Invalid proof task types: {', '.join(invalid_types)}")
    state_value = task.get("implementation_state", "complete")
    implementation_state = state_value.strip().lower() if isinstance(state_value, str) else ""
    if implementation_state not in IMPLEMENTATION_STATES:
        raise RuntimeError(
            "task.implementation_state must be complete, partial, or analysis."
        )

    changes = raw.get("changes", [])
    if not isinstance(changes, list):
        raise RuntimeError("changes must be an array.")
    normalized_changes: list[dict[str, Any]] = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            raise RuntimeError(f"changes[{index}] must be an object.")
        path_value = change.get("path")
        summary_value = change.get("summary")
        if not isinstance(path_value, str) or not path_value.strip():
            raise RuntimeError(f"changes[{index}].path is required.")
        if not isinstance(summary_value, str) or not summary_value.strip():
            raise RuntimeError(f"changes[{index}].summary is required.")
        change_type = str(change.get("change_type", "modified")).strip().lower()
        if change_type not in {"added", "modified", "deleted", "renamed"}:
            raise RuntimeError(f"changes[{index}].change_type is invalid.")
        normalized_changes.append(
            {
                "path": path_value.strip(),
                "summary": redact_text(summary_value.strip()),
                "change_type": change_type,
                "component": redact_text(change.get("component", "")),
            }
        )

    normalized = {
        "schema_version": 1,
        "task": {
            "id": task_id,
            "title": _required_text(task, "title", "task"),
            "summary": _required_text(task, "summary", "task"),
            "depth": depth,
            "types": list(task_types),
            "implementation_state": implementation_state,
            "requested": _text_list(task.get("requested"), "task.requested"),
            "delivered": _text_list(task.get("delivered"), "task.delivered"),
            "not_included": _text_list(task.get("not_included"), "task.not_included"),
        },
        "changes": normalized_changes,
        "understand": redact_value(raw.get("understand", [])),
        "preserved": _text_list(raw.get("preserved"), "preserved"),
        "caveats": _text_list(raw.get("caveats"), "caveats"),
        "risks": redact_value(raw.get("risks", [])),
        "modules": redact_value(raw.get("modules", {})),
        "artifacts": redact_value(raw.get("artifacts", [])),
        "independent_verification_path": raw.get("independent_verification_path"),
    }
    for field, expected in (
        ("understand", list),
        ("risks", list),
        ("modules", dict),
        ("artifacts", list),
    ):
        if not isinstance(normalized[field], expected):
            raise RuntimeError(f"{field} must be {'an array' if expected is list else 'an object'}.")
    independent_path = normalized["independent_verification_path"]
    if independent_path is not None and (
        not isinstance(independent_path, str) or not independent_path.strip()
    ):
        raise RuntimeError("independent_verification_path must be a non-empty string.")
    return normalized


def safe_project_path(target: Path, raw: object, label: str) -> tuple[Path, str]:
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError(f"{label} must be a non-empty relative path.")
    relative = PurePosixPath(raw.strip())
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise RuntimeError(f"Unsafe {label}: {raw!r}")
    candidate = target.joinpath(*relative.parts)
    current = target
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"Refusing symlinked {label}: {relative.as_posix()}")
    try:
        candidate.resolve().relative_to(target.resolve())
    except ValueError as exc:
        raise RuntimeError(f"{label.title()} escapes the project: {raw!r}") from exc
    return candidate, relative.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_changes(target: Path, changes: list[dict[str, Any]]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for change in changes:
        path, relative = safe_project_path(target, change["path"], "changed file path")
        if path.exists() and not path.is_file():
            raise RuntimeError(f"Changed path is not a regular file: {relative}")
        if path.is_file():
            state = "present"
            sha256 = file_sha256(path)
        elif change["change_type"] == "deleted":
            state = "deleted"
            sha256 = None
        else:
            raise RuntimeError(f"Changed file does not exist: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(state.encode("ascii"))
        digest.update((sha256 or "").encode("ascii"))
        files.append({"path": relative, "state": state, "sha256": sha256})
    return {
        "algorithm": "sha256",
        "digest": digest.hexdigest(),
        "files": files,
        "repository": repository_fingerprint(target),
    }


def proof_freshness(
    target: Path,
    proof: dict[str, Any],
    proof_dir: Path | None = None,
) -> dict[str, Any]:
    recorded = proof.get("source_snapshot")
    if not isinstance(recorded, dict) or not isinstance(recorded.get("files"), list):
        return {"status": "unknown", "changed_files": [], "checked_at": utc_now()}
    changed: list[str] = []
    recorded_repository = recorded.get("repository")
    current_repository = repository_fingerprint(target)
    if (
        not isinstance(recorded_repository, dict)
        or not isinstance(recorded_repository.get("digest"), str)
        or not isinstance(current_repository.get("digest"), str)
    ):
        return {"status": "unknown", "changed_files": [], "checked_at": utc_now()}
    if recorded_repository != current_repository:
        changed.append("repository worktree")
    for item in recorded["files"]:
        if not isinstance(item, dict):
            return {"status": "unknown", "changed_files": [], "checked_at": utc_now()}
        try:
            path, relative = safe_project_path(target, item.get("path"), "snapshot path")
        except RuntimeError:
            changed.append(str(item.get("path")))
            continue
        if path.is_file():
            if item.get("state") != "present" or file_sha256(path) != item.get("sha256"):
                changed.append(relative)
        elif item.get("state") != "deleted":
            changed.append(relative)
    if proof_dir is not None:
        for artifact in proof.get("artifacts", []):
            if not isinstance(artifact, dict) or artifact.get("status") != "available":
                continue
            try:
                validated_bundle_artifact_path(proof_dir, artifact)
            except RuntimeError:
                changed.append(f"artifact: {artifact.get('label', artifact.get('id', 'unknown'))}")
        independent = proof.get("independent_verification", {})
        provenance = independent.get("provenance") if isinstance(independent, dict) else None
        if isinstance(provenance, dict) and isinstance(provenance.get("source_path"), str):
            try:
                verifier_path, _ = safe_project_path(
                    target,
                    provenance["source_path"],
                    "independent verifier evidence path",
                )
                if (
                    not verifier_path.is_file()
                    or file_sha256(verifier_path) != provenance.get("sha256")
                ):
                    changed.append("independent verifier evidence")
            except RuntimeError:
                changed.append("independent verifier evidence")
    return {
        "status": "stale" if changed else "current",
        "changed_files": changed,
        "checked_at": utc_now(),
    }


def validated_bundle_artifact_path(
    proof_dir: Path,
    artifact: dict[str, Any],
) -> Path:
    raw = artifact.get("stored_path")
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError("Available artifact has no stored path.")
    relative = PurePosixPath(raw.strip())
    if (
        relative.is_absolute()
        or len(relative.parts) != 2
        or relative.parts[0] != "artifacts"
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise RuntimeError("Artifact stored path is outside the proof bundle.")
    path = proof_dir.joinpath(*relative.parts)
    current = proof_dir
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError("Artifact stored path contains a symlink.")
    try:
        path.resolve().relative_to(proof_dir.resolve())
    except ValueError as exc:
        raise RuntimeError("Artifact stored path escapes the proof bundle.") from exc
    if not path.is_file():
        raise RuntimeError("Artifact file is missing from the proof bundle.")
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise RuntimeError("Artifact exceeds the proof bundle size limit.")
    recorded_hash = artifact.get("sha256")
    if (
        not isinstance(recorded_hash, str)
        or not re.fullmatch(r"[a-f0-9]{64}", recorded_hash)
        or file_sha256(path) != recorded_hash
    ):
        raise RuntimeError("Artifact integrity check failed.")
    return path


def _normalize_repository_binding(raw: object, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError(f"{label} requires a repository binding.")
    mode = raw.get("mode")
    commit = raw.get("git_commit")
    digest = raw.get("digest")
    if mode != "git-worktree":
        raise RuntimeError(f"{label} has an unsupported repository mode.")
    if not isinstance(commit, str) or not re.fullmatch(r"[a-fA-F0-9]{40,64}", commit):
        raise RuntimeError(f"{label} has an invalid Git commit binding.")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise RuntimeError(f"{label} has an invalid repository digest binding.")
    return {"mode": mode, "git_commit": commit, "digest": digest}


def _normalize_verification_record(raw: dict[str, Any], index: int) -> dict[str, Any]:
    level = raw.get("level")
    status = raw.get("status")
    if status not in VERIFICATION_STATES or level not in REQUIRED_LEVELS["DEEP"]:
        raise RuntimeError(f"Verification record {index} has an invalid state or level.")
    if raw.get("provenance") != "configured-command-runner":
        raise RuntimeError(f"Verification record {index} has unsupported provenance.")
    label = raw.get("label")
    command = raw.get("command")
    reason = raw.get("reason")
    exit_code = raw.get("exit_code")
    duration = raw.get("duration_seconds")
    started_at = raw.get("started_at")
    if not isinstance(label, str) or not label.strip():
        raise RuntimeError(f"Verification record {index} requires a label.")
    if command is not None and (not isinstance(command, str) or not command.strip()):
        raise RuntimeError(f"Verification record {index} has an invalid command.")
    if reason is not None and not isinstance(reason, str):
        raise RuntimeError(f"Verification record {index} has an invalid reason.")
    if exit_code is not None and (not isinstance(exit_code, int) or isinstance(exit_code, bool)):
        raise RuntimeError(f"Verification record {index} has an invalid exit code.")
    if duration is not None and (
        not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or duration < 0
    ):
        raise RuntimeError(f"Verification record {index} has an invalid duration.")
    if started_at is not None and not isinstance(started_at, str):
        raise RuntimeError(f"Verification record {index} has an invalid start time.")
    if status in {"passed", "failed", "timed_out"} and (
        command is None or started_at is None or duration is None
    ):
        raise RuntimeError(f"Executed verification record {index} is incomplete.")
    if status == "passed" and exit_code != 0:
        raise RuntimeError(f"Passed verification record {index} must have exit code 0.")
    if status == "failed" and (exit_code is None or exit_code == 0):
        raise RuntimeError(f"Failed verification record {index} requires a non-zero exit code.")
    if status == "timed_out" and exit_code is not None:
        raise RuntimeError(f"Timed-out verification record {index} cannot have an exit code.")
    if status == "skipped" and any(
        value is not None for value in (exit_code, duration, started_at)
    ):
        raise RuntimeError(f"Skipped verification record {index} cannot claim execution metadata.")
    return redact_value(
        {
            "level": level,
            "label": label.strip(),
            "status": status,
            "reason": reason,
            "command": command.strip() if isinstance(command, str) else None,
            "exit_code": exit_code,
            "duration_seconds": duration,
            "started_at": started_at,
            "provenance": "configured-command-runner",
        }
    )


def normalize_verification_evidence(
    target: Path,
    evidence: dict[str, Any] | None,
    *,
    trust_current_run: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if evidence is None:
        return [], {"fresh": False, "reason": "No execution evidence was supplied."}
    if (
        evidence.get("format") != "powerkit-verification-evidence"
        or evidence.get("schema_version") != 1
        or not isinstance(evidence.get("records"), list)
    ):
        raise RuntimeError("Verification evidence has an unsupported schema.")
    requested = evidence.get("requested_levels")
    if (
        not isinstance(requested, list)
        or not requested
        or any(level not in REQUIRED_LEVELS["DEEP"] for level in requested)
        or len(set(requested)) != len(requested)
    ):
        raise RuntimeError("Verification evidence has invalid requested levels.")
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(evidence["records"]):
        if not isinstance(raw, dict):
            raise RuntimeError(f"Verification record {index} must be an object.")
        record = _normalize_verification_record(raw, index)
        if record["level"] not in requested:
            raise RuntimeError(f"Verification record {index} was not requested.")
        records.append(record)
    if any(not any(record["level"] == level for record in records) for level in requested):
        raise RuntimeError("Verification evidence omits a requested level.")
    summary = evidence.get("summary")
    expected_summary = {
        "executed": sum(record["status"] != "skipped" for record in records),
        "passed": sum(record["status"] == "passed" for record in records),
        "failed": sum(record["status"] in {"failed", "timed_out"} for record in records),
        "skipped": sum(record["status"] == "skipped" for record in records),
    }
    if summary != expected_summary:
        raise RuntimeError("Verification evidence summary does not match its records.")
    current_repository = repository_fingerprint(target)
    recorded_repository = _normalize_repository_binding(
        evidence.get("repository"), "Verification evidence"
    )
    fresh = trust_current_run or (
        recorded_repository == current_repository
    )
    return records, {
        "fresh": fresh,
        "reason": (
            "Evidence matches the current repository state."
            if fresh
            else "Evidence was captured against a different or unverifiable repository state."
        ),
        "recorded_repository": recorded_repository,
    }


def load_independent_verification(
    target: Path,
    raw_path: object,
    *,
    task_id: str,
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    if raw_path is None:
        return {
            "status": "unavailable",
            "verdict": "unavailable",
            "summary": "No independent verifier evidence was supplied.",
            "provenance": None,
            "fresh": False,
        }
    path, relative = safe_project_path(target, raw_path, "independent verifier evidence path")
    if not path.is_file():
        raise RuntimeError(f"Independent verifier evidence does not exist: {relative}")
    payload = read_json_object(path, "independent verifier evidence")
    if payload.get("schema_version") != 1 or payload.get("role") != "independent-verifier":
        raise RuntimeError("Independent verifier evidence has invalid role or schema.")
    if payload.get("task_id") != task_id:
        raise RuntimeError("Independent verifier evidence is bound to a different task.")
    if payload.get("source_snapshot_digest") != source_snapshot.get("digest"):
        raise RuntimeError("Independent verifier evidence is bound to a different source snapshot.")
    verdict = payload.get("verdict")
    if verdict not in {"pass", "pass_with_caveats", "fail", "unable"}:
        raise RuntimeError("Independent verifier evidence has an invalid verdict.")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise RuntimeError("Independent verifier evidence requires a summary.")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        raise RuntimeError("Independent verifier checks must be a non-empty array.")
    normalized_checks: list[dict[str, str]] = []
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise RuntimeError(f"Independent verifier check {index} must be an object.")
        name = check.get("name")
        status = check.get("status")
        detail = check.get("detail", "")
        if not isinstance(name, str) or not name.strip() or status not in {
            "passed",
            "failed",
            "unable",
        }:
            raise RuntimeError(f"Independent verifier check {index} is invalid.")
        if not isinstance(detail, str):
            raise RuntimeError(f"Independent verifier check {index} has an invalid detail.")
        normalized_checks.append(
            redact_value({"name": name.strip(), "status": status, "detail": detail})
        )
    check_states = {check["status"] for check in normalized_checks}
    if verdict == "pass" and check_states != {"passed"}:
        raise RuntimeError("Independent verifier pass requires every check to pass.")
    if verdict == "pass_with_caveats" and "failed" in check_states:
        raise RuntimeError("Independent verifier caveated pass cannot contain failed checks.")
    if verdict == "fail" and "failed" not in check_states:
        raise RuntimeError("Independent verifier failure requires a failed check.")
    recorded_repository = _normalize_repository_binding(
        payload.get("repository"), "Independent verifier evidence"
    )
    fresh = recorded_repository == repository_fingerprint(target)
    return {
        "status": "available",
        "verdict": verdict,
        "summary": redact_text(summary.strip()),
        "checks": normalized_checks,
        "fresh": fresh,
        "provenance": {
            "role": "independent-verifier",
            "source_path": relative,
            "sha256": file_sha256(path),
            "task_id": task_id,
            "source_snapshot_digest": source_snapshot["digest"],
            "repository": recorded_repository,
        },
    }


def derive_outcome_status(
    depth: str,
    implementation_state: str,
    verification: list[dict[str, Any]],
    evidence_fresh: bool,
    independent: dict[str, Any],
    caveats: list[str],
) -> str:
    if independent.get("verdict") == "fail":
        return "FAILED_VERIFICATION"
    executed = [record for record in verification if record.get("status") != "skipped"]
    if any(record.get("status") in {"failed", "timed_out"} for record in executed):
        return "FAILED_VERIFICATION"
    if implementation_state == "partial":
        return "PARTIALLY_VERIFIED"
    if not evidence_fresh and executed:
        return "PARTIALLY_VERIFIED"
    required_levels = REQUIRED_LEVELS[depth]
    required_records = [
        record for record in verification if record.get("level") in required_levels
    ]
    passed = [record for record in required_records if record.get("status") == "passed"]
    skipped = [record for record in required_records if record.get("status") == "skipped"]
    if not passed:
        if depth == "FAST" and implementation_state in {"complete", "analysis"}:
            return "IMPLEMENTED"
        return "UNABLE_TO_VERIFY"
    covered_levels = {record["level"] for record in passed}
    if skipped or not required_levels.issubset(covered_levels):
        return "PARTIALLY_VERIFIED"
    if depth == "HIGH_RISK" and (
        independent.get("verdict") not in {"pass", "pass_with_caveats"}
        or not independent.get("fresh")
    ):
        return "PARTIALLY_VERIFIED"
    if caveats or independent.get("verdict") == "pass_with_caveats":
        return "VERIFIED_WITH_CAVEATS"
    return "VERIFIED"


def _claim_evidence_status(
    item: dict[str, Any],
    verification: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> str:
    refs = item.get("evidence_refs", [])
    if refs is None:
        refs = []
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise RuntimeError("Module evidence_refs must be an array of strings.")
    normalized_refs = [ref.strip() for ref in refs if ref.strip()]
    item["evidence_refs"] = normalized_refs
    if not normalized_refs:
        return "not_verified"
    for ref in normalized_refs:
        if ref.startswith("verification:"):
            level = ref.removeprefix("verification:")
            matching = [record for record in verification if record.get("level") == level]
            if not matching or any(record.get("status") != "passed" for record in matching):
                return "not_verified"
        elif ref.startswith("artifact:"):
            artifact_id = ref.removeprefix("artifact:")
            matching = [artifact for artifact in artifacts if artifact.get("id") == artifact_id]
            if not matching or any(artifact.get("status") != "available" for artifact in matching):
                return "not_verified"
        else:
            raise RuntimeError(f"Unsupported module evidence reference: {ref}")
    return "verified"


def normalize_module_claims(
    raw_modules: dict[str, Any],
    verification: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    outcome_status: str,
) -> dict[str, Any]:
    modules = redact_value(raw_modules)
    status_lists = {
        "ui": "states",
        "migration": "checks",
        "database": "checks",
        "review": "criteria",
        "performance": "measurements",
    }
    for module_name, list_name in status_lists.items():
        module = modules.get(module_name)
        if not isinstance(module, dict):
            continue
        claims = module.get(list_name, [])
        if not isinstance(claims, list):
            raise RuntimeError(f"modules.{module_name}.{list_name} must be an array.")
        for index, claim in enumerate(claims):
            if not isinstance(claim, dict):
                raise RuntimeError(
                    f"modules.{module_name}.{list_name}[{index}] must be an object."
                )
            claim.pop("status", None)
            claim.pop("evidence_status", None)
            claim["evidence_status"] = _claim_evidence_status(
                claim, verification, artifacts
            )
    review = modules.get("review")
    if isinstance(review, dict):
        review.pop("verdict", None)
        review["verdict"] = {
            "VERIFIED": "Canonical evidence is complete; ready for human merge review.",
            "VERIFIED_WITH_CAVEATS": "Ready for human merge review with the recorded caveats.",
            "IMPLEMENTED": "Implemented, but verification is still required before merge.",
            "PARTIALLY_VERIFIED": "Additional verification is required before merge.",
            "FAILED_VERIFICATION": "Not ready to merge; verification failed.",
            "UNABLE_TO_VERIFY": "Not ready to merge; verification evidence is unavailable.",
        }[outcome_status]
    return modules


def _artifact_extension(path: Path) -> str:
    suffix = path.suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,9}", suffix) else ".bin"


def collect_artifacts(
    target: Path,
    proof_dir: Path,
    raw_artifacts: list[Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    if len(raw_artifacts) > MAX_ARTIFACTS:
        raise RuntimeError(f"A proof may contain at most {MAX_ARTIFACTS} artifacts.")
    artifacts: list[dict[str, Any]] = []
    caveats: list[str] = []
    copied_bytes = 0
    destination_root = proof_dir / "artifacts"
    for index, raw in enumerate(raw_artifacts, start=1):
        if not isinstance(raw, dict):
            raise RuntimeError(f"artifacts[{index - 1}] must be an object.")
        artifact_id = str(raw.get("id", f"artifact-{index}")).strip()
        if not TASK_ID_PATTERN.fullmatch(artifact_id):
            raise RuntimeError(f"artifacts[{index - 1}].id is invalid.")
        label = raw.get("label")
        sensitivity = str(raw.get("sensitivity", "normal")).strip().lower()
        if not isinstance(label, str) or not label.strip():
            raise RuntimeError(f"artifacts[{index - 1}].label is required.")
        if sensitivity not in {"normal", "sensitive"}:
            raise RuntimeError(f"artifacts[{index - 1}].sensitivity is invalid.")
        path, relative = safe_project_path(target, raw.get("path"), "artifact path")
        record: dict[str, Any] = {
            "id": artifact_id,
            "label": redact_text(label.strip()),
            "kind": str(raw.get("kind", "other")).strip().lower(),
            "caption": redact_text(raw.get("caption", "")),
            "alt": redact_text(raw.get("alt", label.strip())),
            "sensitivity": sensitivity,
            "source_path": relative,
            "stored_path": None,
            "sha256": None,
            "media_type": None,
            "status": "missing",
        }
        if not path.exists():
            caveats.append(f"Evidence artifact is missing: {record['label']}.")
        elif not path.is_file():
            caveats.append(f"Evidence artifact is not a regular file: {record['label']}.")
        elif sensitivity == "sensitive":
            record["status"] = "withheld"
            record["sha256"] = file_sha256(path)
            caveats.append(f"Sensitive artifact was recorded but not copied: {record['label']}.")
        elif path.stat().st_size > MAX_ARTIFACT_BYTES:
            record["status"] = "too_large"
            caveats.append(
                f"Evidence artifact exceeded the {MAX_ARTIFACT_BYTES // (1024 * 1024)} MiB "
                f"copy limit: {record['label']}."
            )
        elif copied_bytes + path.stat().st_size > MAX_TOTAL_ARTIFACT_BYTES:
            record["status"] = "too_large"
            caveats.append(
                f"Evidence artifacts exceeded the {MAX_TOTAL_ARTIFACT_BYTES // (1024 * 1024)} MiB "
                f"total copy limit before: {record['label']}."
            )
        else:
            destination_root.mkdir(parents=True, exist_ok=True)
            filename = f"{index:03d}{_artifact_extension(path)}"
            destination = destination_root / filename
            shutil.copyfile(path, destination)
            record["status"] = "available"
            record["stored_path"] = f"artifacts/{filename}"
            record["sha256"] = file_sha256(destination)
            record["media_type"] = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            copied_bytes += destination.stat().st_size
        artifacts.append(record)
    return artifacts, caveats


def render_completion_brief(proof: dict[str, Any]) -> str:
    task = proof["task"]
    outcome = proof["outcome"]
    lines = [STATUS_LABELS[outcome["status"]], "", task["summary"]]
    delivered = task.get("delivered", [])
    changes = proof.get("changes", [])
    if task["depth"] == "FAST":
        if delivered or changes:
            lines.extend(["", "Changed"])
            lines.extend(str(item) for item in (delivered[:2] or [c["summary"] for c in changes[:2]]))
    elif delivered or changes:
        lines.extend(["", "What changed"])
        lines.extend(f"• {item}" for item in (delivered or [c["summary"] for c in changes[:5]]))
    verification = proof.get("verification", [])
    visible = [record for record in verification if record.get("status") != "skipped"]
    skipped = [record for record in verification if record.get("status") == "skipped"]
    if visible:
        lines.extend(["", "Verified"])
        for record in visible:
            marker = "✓" if record["status"] == "passed" else "✗"
            lines.append(f"• {marker} {record['label']}: {record['status'].replace('_', ' ')}")
    elif outcome["status"] != "IMPLEMENTED":
        lines.extend(["", "Verification", "• No executed checks were available."])
    worth_knowing = list(proof.get("caveats", []))
    if skipped:
        worth_knowing.append(f"{len(skipped)} verification level or check{' was' if len(skipped) == 1 else 's were'} not run.")
    if worth_knowing:
        lines.extend(["", "Worth knowing"])
        lines.extend(f"• {item}" for item in worth_knowing[:5])
    result = {
        "VERIFIED": "Ready for review.",
        "VERIFIED_WITH_CAVEATS": "Ready for review with the caveats above.",
        "IMPLEMENTED": "Implemented; review the change before relying on it.",
        "PARTIALLY_VERIFIED": "Additional verification is required.",
        "FAILED_VERIFICATION": "Not ready; verification failed.",
        "UNABLE_TO_VERIFY": "Verification is still required.",
    }[outcome["status"]]
    if task["depth"] != "FAST":
        lines.extend(["", f"Result: {result}"])
    return "\n".join(lines).rstrip() + "\n"


def should_generate_html(depth: str, task_types: Iterable[str], explicit_html: bool) -> bool:
    if depth in {"DEEP", "HIGH_RISK"}:
        return True
    return depth == "STANDARD" and (
        explicit_html or bool(set(task_types) & {"ui", "architecture", "migration"})
    )


def configured_proof_root(target: Path, explicit: Path | None = None) -> Path:
    target = target.expanduser().resolve()
    raw = explicit or PROOF_ROOT
    if explicit is None:
        config_path = target / ".ai-powerkit/project.json"
        if config_path.is_file() and not config_path.is_symlink():
            payload = read_json_object(config_path, "PowerKit project configuration")
            proof_config = payload.get("proof", {})
            if isinstance(proof_config, dict) and proof_config.get("output_directory") is not None:
                configured = proof_config["output_directory"]
                if not isinstance(configured, str) or not configured.strip():
                    raise RuntimeError("proof.output_directory must be a non-empty string.")
                raw = Path(configured)
    root = raw if raw.is_absolute() else target / raw
    try:
        relative = root.resolve().relative_to(target)
    except ValueError as exc:
        raise RuntimeError("Proof output directory must remain inside the project.") from exc
    if len(relative.parts) < 2 or relative.parts[0] != ".ai-powerkit":
        raise RuntimeError(
            "Proof output directory must be dedicated generated state under .ai-powerkit/."
        )
    current = target
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"Refusing symlinked proof output path: {current}")
    return root


def _risk_payload(raw_risks: list[Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for raw in raw_risks:
        if isinstance(raw, dict) and isinstance(raw.get("summary"), str) and raw["summary"].strip():
            result.append(
                {
                    "severity": redact_text(raw.get("severity", "unspecified")).lower(),
                    "summary": redact_text(raw["summary"]),
                    "mitigation": redact_text(raw.get("mitigation", "")),
                }
            )
    return result


def _safe_cleanup_temporary(root: Path, temporary: Path | None) -> None:
    """Remove only the exact, validated temporary proof child."""
    if temporary is None or not temporary.exists():
        return
    try:
        relative = temporary.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError("Refusing cleanup outside the proof root.") from exc
    if len(relative.parts) != 1 or not temporary.name.startswith("."):
        raise RuntimeError("Refusing cleanup of a non-temporary proof path.")
    shutil.rmtree(temporary)


def build_proof(
    target: Path,
    spec: dict[str, Any],
    evidence: dict[str, Any] | None,
    *,
    output_root: Path | None = None,
    replace: bool = False,
    explicit_html: bool = False,
    trust_current_run: bool = False,
) -> tuple[Path, dict[str, Any]]:
    from powerkit.proof_render import render_html_report

    target = target.expanduser().resolve()
    if not target.is_dir():
        raise RuntimeError(f"Target directory does not exist: {target}")
    task = spec["task"]
    root = configured_proof_root(target, output_root)
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise RuntimeError(f"Refusing symlinked proof output directory: {root}")
    final_dir = root / task["id"]
    if final_dir.exists() and not replace:
        raise RuntimeError(f"Proof already exists: {final_dir}. Use --replace after reviewing it.")
    if final_dir.is_symlink():
        raise RuntimeError(f"Refusing symlinked proof destination: {final_dir}")
    if final_dir.exists():
        _validate_removable_proof(root, final_dir, task["id"])
    source_snapshot = snapshot_changes(target, spec["changes"])
    verification, evidence_freshness = normalize_verification_evidence(
        target, evidence, trust_current_run=trust_current_run
    )
    independent = load_independent_verification(
        target,
        spec.get("independent_verification_path"),
        task_id=task["id"],
        source_snapshot=source_snapshot,
    )

    temporary: Path | None = Path(tempfile.mkdtemp(prefix=f".{task['id']}.", dir=root))
    try:
        artifacts, artifact_caveats = collect_artifacts(target, temporary, spec["artifacts"])
        caveats = list(spec["caveats"]) + artifact_caveats
        if task["depth"] == "HIGH_RISK" and (
            independent.get("verdict") not in {"pass", "pass_with_caveats"}
            or not independent.get("fresh")
        ):
            caveats.append(
                "Fresh, task-bound independent verifier evidence is required for HIGH_RISK proof."
            )
        status = derive_outcome_status(
            task["depth"],
            task["implementation_state"],
            verification,
            evidence_freshness["fresh"],
            independent,
            caveats,
        )
        proof: dict[str, Any] = {
            "schema_version": PROOF_SCHEMA_VERSION,
            "kind": "powerkit-proof",
            "generated_at": utc_now(),
            "task": task,
            "outcome": {
                "status": status,
                "label": STATUS_LABELS[status],
                "implementation_state": task["implementation_state"],
                "summary": task["summary"],
            },
            "scope": {
                "requested": task["requested"],
                "delivered": task["delivered"],
                "not_included": task["not_included"],
                "preserved": spec["preserved"],
            },
            "changes": spec["changes"],
            "verification": verification,
            "verification_evidence": evidence_freshness,
            "source_snapshot": source_snapshot,
            "runtime_evidence": [a for a in artifacts if a["kind"] == "runtime"],
            "visual_evidence": [a for a in artifacts if a["kind"] in {"screenshot", "diagram"}],
            "understand": spec["understand"],
            "modules": normalize_module_claims(
                spec["modules"], verification, artifacts, status
            ),
            "risk": {"items": _risk_payload(spec["risks"])},
            "caveats": caveats,
            "independent_verification": independent,
            "artifacts": artifacts,
            "privacy": {
                "command_output_stored": False,
                "environment_captured": False,
                "prompt_history_captured": False,
                "redaction": "sensitive mapping keys plus common credential, email, and phone patterns",
            },
            "presentation": {
                "completion_brief": {"path": "completion.txt", "status": "pending"},
                "report": {"path": None, "status": "not_requested", "error": None},
            },
        }
        atomic_write_text(temporary / "completion.txt", render_completion_brief(proof))
        proof["presentation"]["completion_brief"]["status"] = "generated"
        if should_generate_html(task["depth"], task["types"], explicit_html):
            proof["presentation"]["report"] = {
                "path": "report.html",
                "status": "pending",
                "error": None,
            }
            try:
                atomic_write_text(
                    temporary / "report.html",
                    render_html_report(proof, temporary, {"status": "current", "changed_files": []}),
                )
                proof["presentation"]["report"]["status"] = "generated"
            except Exception as exc:
                proof["presentation"]["report"]["status"] = "failed"
                proof["presentation"]["report"]["error"] = redact_text(exc)
        atomic_write_text(
            temporary / "proof.json", json.dumps(proof, indent=2, sort_keys=True) + "\n"
        )
        backup: Path | None = None
        if final_dir.exists():
            _validate_removable_proof(root, final_dir, task["id"])
            backup = Path(tempfile.mkdtemp(prefix=f".{task['id']}.backup.", dir=root))
            backup.rmdir()
            os.replace(final_dir, backup)
        try:
            os.replace(temporary, final_dir)
        except Exception:
            if backup is not None and backup.exists() and not final_dir.exists():
                os.replace(backup, final_dir)
            raise
        temporary = None
        _safe_cleanup_temporary(root, backup)
        return final_dir, proof
    finally:
        _safe_cleanup_temporary(root, temporary)


def _validate_proof_manifest(payload: dict[str, Any], proof_dir: Path) -> None:
    def require_string_list(value: object, label: str) -> None:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise RuntimeError(f"Invalid proof manifest {label}.")

    required = {
        "generated_at",
        "task",
        "outcome",
        "scope",
        "changes",
        "verification",
        "verification_evidence",
        "source_snapshot",
        "caveats",
        "independent_verification",
        "artifacts",
        "privacy",
        "presentation",
    }
    missing = sorted(field for field in required if field not in payload)
    if missing:
        raise RuntimeError(f"Invalid proof manifest; missing: {', '.join(missing)}")
    task = payload.get("task")
    if not isinstance(task, dict):
        raise RuntimeError("Invalid proof manifest task.")
    task_id = task.get("id")
    if not isinstance(task_id, str) or not TASK_ID_PATTERN.fullmatch(task_id):
        raise RuntimeError("Invalid proof manifest task id.")
    if proof_dir.name != task_id:
        raise RuntimeError("Proof directory does not match its manifest task id.")
    if task.get("depth") not in DEPTHS or task.get("implementation_state") not in IMPLEMENTATION_STATES:
        raise RuntimeError("Invalid proof manifest task policy.")
    if (
        not isinstance(task.get("types"), list)
        or not task["types"]
        or any(
            not isinstance(task_type, str)
            or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", task_type)
            for task_type in task["types"]
        )
    ):
        raise RuntimeError("Invalid proof manifest task types.")
    for field in ("title", "summary"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            raise RuntimeError(f"Invalid proof manifest task {field}.")
    for field in ("requested", "delivered", "not_included"):
        require_string_list(task.get(field), f"task {field}")
    outcome = payload.get("outcome")
    if (
        not isinstance(outcome, dict)
        or outcome.get("status") not in STATUS_LABELS
        or not isinstance(outcome.get("label"), str)
        or outcome.get("implementation_state") not in IMPLEMENTATION_STATES
        or not isinstance(outcome.get("summary"), str)
    ):
        raise RuntimeError("Invalid proof manifest outcome.")
    scope = payload.get("scope")
    if not isinstance(scope, dict):
        raise RuntimeError("Invalid proof manifest scope.")
    for field in ("requested", "delivered", "not_included", "preserved"):
        require_string_list(scope.get(field), f"scope {field}")
    changes = payload.get("changes")
    if not isinstance(changes, list):
        raise RuntimeError("Invalid proof manifest changes.")
    for index, change in enumerate(changes):
        if (
            not isinstance(change, dict)
            or not isinstance(change.get("path"), str)
            or not isinstance(change.get("summary"), str)
            or change.get("change_type") not in {"added", "modified", "deleted", "renamed"}
            or not isinstance(change.get("component"), str)
        ):
            raise RuntimeError(f"Invalid proof manifest change {index}.")
    snapshot = payload.get("source_snapshot")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("algorithm") != "sha256"
        or not isinstance(snapshot.get("digest"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", snapshot["digest"])
        or not isinstance(snapshot.get("files"), list)
    ):
        raise RuntimeError("Invalid proof manifest source snapshot.")
    _normalize_repository_binding(snapshot.get("repository"), "Proof source snapshot")
    for index, item in enumerate(snapshot["files"]):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or item.get("state") not in {"present", "deleted"}
            or (
                item.get("sha256") is not None
                and (
                    not isinstance(item.get("sha256"), str)
                    or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])
                )
            )
        ):
            raise RuntimeError(f"Invalid proof manifest source snapshot file {index}.")
    verification = payload.get("verification")
    if not isinstance(verification, list):
        raise RuntimeError("Invalid proof manifest verification records.")
    verification_fields = {
        "level",
        "label",
        "status",
        "reason",
        "command",
        "exit_code",
        "duration_seconds",
        "started_at",
        "provenance",
    }
    for index, record in enumerate(verification):
        if not isinstance(record, dict) or set(record) != verification_fields:
            raise RuntimeError(f"Invalid proof manifest verification record {index}.")
        _normalize_verification_record(record, index)
    for field, expected in (
        ("verification_evidence", dict),
        ("caveats", list),
        ("independent_verification", dict),
        ("artifacts", list),
        ("privacy", dict),
        ("presentation", dict),
    ):
        if not isinstance(payload.get(field), expected):
            raise RuntimeError(f"Invalid proof manifest {field}.")
    require_string_list(payload.get("caveats"), "caveats")
    if "understand" in payload and not isinstance(payload["understand"], list):
        raise RuntimeError("Invalid proof manifest understand section.")
    if "modules" in payload and not isinstance(payload["modules"], dict):
        raise RuntimeError("Invalid proof manifest modules.")
    if "risk" in payload and not isinstance(payload["risk"], dict):
        raise RuntimeError("Invalid proof manifest risk section.")
    for index, artifact in enumerate(payload["artifacts"]):
        if (
            not isinstance(artifact, dict)
            or not isinstance(artifact.get("id"), str)
            or not isinstance(artifact.get("label"), str)
            or artifact.get("status")
            not in {"available", "missing", "withheld", "too_large"}
        ):
            raise RuntimeError(f"Invalid proof manifest artifact {index}.")


def load_proof(proof_dir: Path) -> dict[str, Any]:
    payload = read_json_object(proof_dir / "proof.json", "proof manifest")
    if payload.get("kind") != "powerkit-proof":
        raise RuntimeError(f"Not a PowerKit proof: {proof_dir}")
    if payload.get("schema_version") != PROOF_SCHEMA_VERSION:
        raise RuntimeError(
            f"Unsupported proof schema {payload.get('schema_version')!r}; "
            "regenerate it with a compatible PowerKit release."
        )
    _validate_proof_manifest(payload, proof_dir)
    return payload


def proof_directories(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir() and not path.is_symlink() and (path / "proof.json").is_file()
        ),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )


def resolve_proof_directory(target: Path, task_id: str, output_root: Path | None = None) -> Path:
    root = configured_proof_root(target, output_root)
    if task_id == "latest":
        proofs = proof_directories(root)
        if not proofs:
            raise RuntimeError(f"No proofs exist under {root}")
        return proofs[0]
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise RuntimeError("Invalid proof task id.")
    proof_dir = root / task_id
    if proof_dir.is_symlink() or not proof_dir.is_dir():
        raise RuntimeError(f"Proof does not exist: {task_id}")
    return proof_dir


def _validate_removable_proof(root: Path, proof_dir: Path, expected_id: str) -> dict[str, Any]:
    if proof_dir.is_symlink() or not proof_dir.is_dir():
        raise RuntimeError(f"Refusing unsafe proof directory: {proof_dir}")
    try:
        relative = proof_dir.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError("Proof deletion target escapes the proof root.") from exc
    if len(relative.parts) != 1 or relative.name != expected_id:
        raise RuntimeError("Proof deletion target must be the matching direct child of the proof root.")
    proof = load_proof(proof_dir)
    manifest_id = proof.get("task", {}).get("id")
    if manifest_id != expected_id:
        raise RuntimeError(
            f"Refusing to remove proof directory {proof_dir}: manifest task id is {manifest_id!r}."
        )
    return proof


def refresh_report(target: Path, proof_dir: Path, proof: dict[str, Any]) -> Path:
    from powerkit.proof_render import render_html_report

    report = proof.get("presentation", {}).get("report", {})
    if not isinstance(report, dict) or report.get("path") != "report.html":
        raise RuntimeError("This proof has no HTML report.")
    path = proof_dir / "report.html"
    atomic_write_text(
        path,
        render_html_report(proof, proof_dir, proof_freshness(target, proof, proof_dir)),
    )
    return path


def open_report(target: Path, proof_dir: Path, proof: dict[str, Any]) -> Path:
    path = refresh_report(target, proof_dir, proof)
    webbrowser.open(path.resolve().as_uri())
    return path


def delete_proof(target: Path, root: Path, task_id: str) -> Path:
    proof_dir = resolve_proof_directory(target, task_id, output_root=root)
    _validate_removable_proof(root, proof_dir, proof_dir.name)
    shutil.rmtree(proof_dir)
    return proof_dir

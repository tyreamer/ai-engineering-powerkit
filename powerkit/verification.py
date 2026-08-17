"""Execute repository-defined verification and emit privacy-bounded evidence."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from powerkit.installer import atomic_write_text
from powerkit.privacy import redact_text


LEVELS = ("static", "targeted", "broader", "runtime")
EVIDENCE_FORMAT = "powerkit-verification-evidence"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def normalize_levels(values: Iterable[str]) -> tuple[str, ...]:
    levels = tuple(
        dict.fromkeys(str(value).strip().lower() for value in values if str(value).strip())
    )
    unknown = sorted(set(levels) - set(LEVELS))
    if unknown:
        raise RuntimeError(f"Unknown verification levels: {', '.join(unknown)}")
    if not levels:
        raise RuntimeError("At least one verification level is required.")
    return levels


def load_verification_config(path: Path) -> dict[str, list[dict[str, str]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid verification config {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Verification config must be a JSON object.")
    raw_verification = payload.get("verification", {})
    if not isinstance(raw_verification, dict):
        raise RuntimeError("Verification must be a JSON object.")

    result: dict[str, list[dict[str, str]]] = {}
    for level in LEVELS:
        raw_commands = raw_verification.get(level, [])
        if not isinstance(raw_commands, list):
            raise RuntimeError(f"verification.{level} must be an array.")
        commands: list[dict[str, str]] = []
        for index, raw in enumerate(raw_commands, start=1):
            if isinstance(raw, str):
                command = raw.strip()
                label = f"{level.title()} check {index}"
            elif isinstance(raw, dict):
                command_value = raw.get("command")
                label_value = raw.get("label")
                command = command_value.strip() if isinstance(command_value, str) else ""
                label = label_value.strip() if isinstance(label_value, str) else ""
                if not label:
                    label = f"{level.title()} check {index}"
            else:
                command = ""
                label = ""
            if not command:
                raise RuntimeError(f"verification.{level} contains an invalid command.")
            commands.append({"command": command, "label": redact_text(label)})
        result[level] = commands
    return result


def _run_git(target: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(target), *args],
        capture_output=True,
        check=False,
    )


def _proof_output_relative(target: Path) -> Path:
    default = Path(".ai-powerkit/proofs")
    config = target / ".ai-powerkit/project.json"
    if not config.is_file() or config.is_symlink():
        return default
    try:
        payload = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default
    proof = payload.get("proof", {}) if isinstance(payload, dict) else {}
    raw = proof.get("output_directory") if isinstance(proof, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        return default
    relative = PurePosixPath(raw.strip())
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return default
    if len(relative.parts) < 2 or relative.parts[0] != ".ai-powerkit":
        return default
    candidate = target.joinpath(*relative.parts)
    current = target
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return default
    try:
        candidate.resolve().relative_to(target.resolve())
    except ValueError:
        return default
    return Path(*relative.parts)


def _hash_git_output(target: Path, digest: Any, *args: str) -> bool:
    process = subprocess.Popen(
        ["git", "-C", str(target), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdout is not None
    try:
        for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
            digest.update(chunk)
    finally:
        process.stdout.close()
    return process.wait() == 0


def repository_fingerprint(target: Path) -> dict[str, Any]:
    """Digest Git HEAD, tracked changes, and non-ignored untracked content.

    Only the digest and commit are retained. File contents and environment values are
    never written into proof evidence.
    """
    head = _run_git(target, "rev-parse", "HEAD")
    if head.returncode != 0:
        return {"mode": "unavailable", "git_commit": None, "digest": None}

    proof_output = _proof_output_relative(target).as_posix()
    tracked_proof_output = _run_git(target, "ls-files", "--", proof_output)
    if tracked_proof_output.returncode != 0:
        return {"mode": "unavailable", "git_commit": None, "digest": None}
    untracked = _run_git(target, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode != 0:
        return {"mode": "unavailable", "git_commit": None, "digest": None}

    digest = hashlib.sha256()
    commit = head.stdout.decode("ascii", errors="replace").strip()
    digest.update(commit.encode("utf-8"))
    diff_args = ["diff", "--no-ext-diff", "--binary", "HEAD", "--", "."]
    if not tracked_proof_output.stdout.strip():
        diff_args.append(f":(exclude){proof_output}/**")
    diff_args.append(":(exclude).ai-powerkit/verification/**")
    if not _hash_git_output(target, digest, *diff_args):
        return {"mode": "unavailable", "git_commit": None, "digest": None}
    raw_paths = sorted(item for item in untracked.stdout.split(b"\0") if item)
    for raw_path in raw_paths:
        relative = Path(raw_path.decode("utf-8", errors="surrogateescape"))
        if (
            relative == Path(proof_output)
            or Path(proof_output) in relative.parents
            or relative.parts[:2] == (".ai-powerkit", "verification")
        ):
            continue
        path = target / relative
        digest.update(raw_path)
        if path.is_symlink():
            digest.update(b"symlink")
        elif path.is_file():
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(b"missing")
    return {"mode": "git-worktree", "git_commit": commit, "digest": digest.hexdigest()}


def _execute_command(
    command: str,
    target: Path,
    timeout: int,
    stream: bool,
) -> tuple[int | None, bool]:
    process = subprocess.Popen(
        command,
        cwd=target,
        shell=True,
        stdout=None if stream else subprocess.DEVNULL,
        stderr=None if stream else subprocess.DEVNULL,
        start_new_session=os.name == "posix",
    )
    try:
        return process.wait(timeout=timeout), False
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=1)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if process.poll() is None:
                process.wait()
        else:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if process.poll() is None:
                process.kill()
            process.wait()
        return None, True


def run_verification(
    target: Path,
    config_path: Path,
    levels: Iterable[str],
    *,
    timeout: int = 900,
    keep_going: bool = False,
    allow_empty: bool = False,
    stream: bool = True,
) -> tuple[dict[str, Any], int]:
    """Run configured commands and return canonical execution records plus an exit code."""
    target_lexical = Path(os.path.abspath(target.expanduser()))
    target = target_lexical.resolve()
    if not target.is_dir():
        raise RuntimeError(f"Target directory does not exist: {target}")
    config_path = config_path.expanduser()
    config_path = config_path if config_path.is_absolute() else target_lexical / config_path
    lexical_path = Path(os.path.abspath(config_path))
    try:
        relative_config = lexical_path.relative_to(target_lexical)
        current = target_lexical
    except ValueError:
        resolved_config = lexical_path.resolve(strict=False)
        try:
            relative_config = resolved_config.relative_to(target)
        except ValueError as exc:
            raise RuntimeError("Verification config must remain inside the project.") from exc
        current = target
    for part in relative_config.parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"Refusing symlinked verification config path: {current}")
    try:
        lexical_path.resolve(strict=False).relative_to(target)
    except ValueError as exc:
        raise RuntimeError("Verification config must remain inside the project.") from exc
    config_path = lexical_path
    if not config_path.is_file():
        raise RuntimeError(f"Verification config does not exist: {config_path}")
    if timeout <= 0:
        raise RuntimeError("Verification timeout must be positive.")

    requested = normalize_levels(levels)
    configured = load_verification_config(config_path)
    records: list[dict[str, Any]] = []
    executed = 0
    failures = 0
    first_failure_code = 1
    stop = False

    for level in requested:
        commands = configured[level]
        if not commands:
            records.append(
                {
                    "level": level,
                    "label": f"{level.title()} verification",
                    "status": "skipped",
                    "reason": "No command configured for this level.",
                    "command": None,
                    "exit_code": None,
                    "duration_seconds": None,
                    "started_at": None,
                    "provenance": "configured-command-runner",
                }
            )
            continue
        for item in commands:
            command = item["command"]
            if stop:
                records.append(
                    {
                        "level": level,
                        "label": item["label"],
                        "status": "skipped",
                        "reason": "Not run because an earlier check failed.",
                        "command": redact_text(command),
                        "exit_code": None,
                        "duration_seconds": None,
                        "started_at": None,
                        "provenance": "configured-command-runner",
                    }
                )
                continue
            executed += 1
            started_at = utc_now()
            if stream:
                print(f"\n[{level}] $ {redact_text(command)}", flush=True)
            started = time.monotonic()
            exit_code, timed_out = _execute_command(command, target, timeout, stream)
            duration = time.monotonic() - started
            if timed_out:
                status = "timed_out"
                reason = f"Timed out after {timeout} seconds."
            else:
                status = "passed" if exit_code == 0 else "failed"
                reason = None
            if stream:
                exit_label = "timeout" if exit_code is None else str(exit_code)
                print(f"[{level}] exit={exit_label} elapsed={duration:.1f}s")
            records.append(
                {
                    "level": level,
                    "label": item["label"],
                    "status": status,
                    "reason": reason,
                    "command": redact_text(command),
                    "exit_code": exit_code,
                    "duration_seconds": round(duration, 3),
                    "started_at": started_at,
                    "provenance": "configured-command-runner",
                }
            )
            if status != "passed":
                failures += 1
                if exit_code:
                    first_failure_code = exit_code
                if not keep_going:
                    stop = True

    payload = {
        "format": EVIDENCE_FORMAT,
        "schema_version": 1,
        "generated_at": utc_now(),
        "repository": repository_fingerprint(target),
        "requested_levels": list(requested),
        "records": records,
        "summary": {
            "executed": executed,
            "passed": sum(record["status"] == "passed" for record in records),
            "failed": failures,
            "skipped": sum(record["status"] == "skipped" for record in records),
        },
    }
    if executed == 0:
        return payload, 0 if allow_empty else 2
    if failures:
        return payload, first_failure_code if not keep_going else 1
    return payload, 0


def write_evidence(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_evidence(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid verification evidence {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("format") != EVIDENCE_FORMAT:
        raise RuntimeError(f"Unsupported verification evidence: {path}")
    if payload.get("schema_version") != 1 or not isinstance(payload.get("records"), list):
        raise RuntimeError(f"Unsupported verification evidence schema: {path}")
    return payload

#!/usr/bin/env python3
"""Block a very small set of clearly catastrophic shell commands.

The script reads a hook event JSON object from stdin. It is intentionally
conservative: team-specific policies such as force-push or git reset do not
belong in this shared guard.

Exit code 2 blocks a matching tool call in both Codex and Claude Code hook
flows. Malformed or missing hook events also fail closed; safe commands exit 0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from typing import Any

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "filesystem creation on a block device",
        re.compile(r"(?is)(?:^|[;&|]\s*)(?:sudo(?:\s+-\S+)*\s+)?(?:/[^\s]+/)?mkfs(?:\.[a-z0-9_-]+)?\s+[^;&|]*?/dev/(?:sd|nvme|vd|xvd|disk)[a-z0-9]+"),
    ),
    (
        "raw write to a block device",
        re.compile(r"(?is)(?:^|[;&|]\s*)(?:sudo\s+)?dd\s+[^;&|]*\bof=/dev/(?:sd|nvme|vd|xvd|disk)[a-z0-9]+"),
    ),
    (
        "direct redirection into a block device",
        re.compile(r"(?is)>\s*/dev/(?:sd|nvme|vd|xvd|disk)[a-z0-9]+"),
    ),
    (
        "shell fork bomb",
        re.compile(r"(?s):\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
    ),
    (
        "recursive forced removal of the Windows system drive",
        re.compile(
            r"(?is)(?:remove-item|del|erase|rd|rmdir)\b"
            r"(?=[^\r\n]*(?:-recurse|/s))(?=[^\r\n]*(?:-force|/q))"
            r"[^\r\n]*\bc:(?:\\+|/)(?:\*|[\"']|\s|$)"
        ),
    ),
    (
        "formatting the Windows system drive",
        re.compile(r"(?is)(?:^|[;&|]\s*)format(?:\.com)?\s+c:\s*(?:/|$)"),
    ),
)


def extract_command(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            return command
    if isinstance(tool_input, str):
        return tool_input
    command = payload.get("command")
    return command if isinstance(command, str) else None


def shell_segments(command: str) -> list[list[str]] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token and set(token) <= {";", "&", "|"}:
            if segments[-1]:
                segments.append([])
            continue
        segments[-1].append(token)
    return [segment for segment in segments if segment]


def unwrap_executable(segment: list[str]) -> tuple[str, list[str]] | None:
    index = 0
    assignment = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
    sudo_options_with_values = {"-C", "-D", "-g", "-h", "-p", "-R", "-T", "-u"}
    sudo_long_options_with_values = {
        "--chdir",
        "--close-from",
        "--group",
        "--host",
        "--prompt",
        "--role",
        "--type",
        "--user",
    }
    env_options_with_values = {"-C", "--chdir", "-u", "--unset"}

    while index < len(segment):
        while index < len(segment) and assignment.fullmatch(segment[index]):
            index += 1
        if index >= len(segment):
            return None

        executable = os.path.basename(segment[index]).lower()
        if executable == "env":
            index += 1
            while index < len(segment):
                option = segment[index]
                if assignment.fullmatch(option):
                    index += 1
                    continue
                if option == "--":
                    index += 1
                    break
                if not option.startswith("-") or option == "-":
                    break
                index += 1
                if option in env_options_with_values and index < len(segment):
                    index += 1
            continue

        if executable == "sudo":
            index += 1
            while index < len(segment) and segment[index].startswith("-"):
                option = segment[index]
                index += 1
                if option == "--":
                    break
                if (
                    option in sudo_options_with_values
                    or option in sudo_long_options_with_values
                ) and index < len(segment):
                    index += 1
            continue

        if executable in {"command", "builtin"}:
            index += 1
            while index < len(segment) and segment[index].startswith("-"):
                option = segment[index]
                index += 1
                if option in {"-v", "-V"}:
                    return None
                if option == "--":
                    break
            continue

        if executable == "exec":
            index += 1
            while index < len(segment) and segment[index].startswith("-"):
                option = segment[index]
                index += 1
                if option == "-a" and index < len(segment):
                    index += 1
                if option == "--":
                    break
            continue

        return executable, segment[index + 1 :]
    return None


def recursive_forced_rm_reason(command: str) -> str | None:
    segments = shell_segments(command)
    if segments is None:
        # PowerShell syntax is not POSIX shell syntax. Fall through to the
        # platform-neutral regex checks instead of blocking valid commands.
        return None
    home = os.path.normpath(os.path.expanduser("~"))

    def normalized_delete_target(target: str) -> str:
        without_glob = target[:-1] if target.endswith("*") else target
        for prefix in ("${HOME}", "$HOME", "~"):
            if without_glob == prefix or without_glob.startswith(prefix + "/"):
                suffix = without_glob[len(prefix) :].lstrip("/")
                return os.path.normpath(os.path.join(home, suffix))
        return os.path.normpath(without_glob)

    for segment in segments:
        unwrapped = unwrap_executable(segment)
        if not unwrapped:
            continue
        executable, arguments = unwrapped
        if executable in {"bash", "dash", "ksh", "sh", "zsh"}:
            for index, argument in enumerate(arguments[:-1]):
                if argument == "--":
                    break
                if (
                    argument.startswith("-")
                    and not argument.startswith("--")
                    and "c" in argument[1:]
                ):
                    nested_reason = recursive_forced_rm_reason(arguments[index + 1])
                    if nested_reason:
                        return nested_reason
        if executable not in {"rm", "rm.exe"}:
            continue

        recursive = False
        forced = False
        targets: list[str] = []
        parse_options = True
        for argument in arguments:
            if parse_options and argument == "--":
                parse_options = False
                continue
            if parse_options and argument.startswith("--"):
                recursive = recursive or argument == "--recursive"
                forced = forced or argument == "--force"
                continue
            if parse_options and argument.startswith("-") and argument != "-":
                flags = argument[1:]
                recursive = recursive or "r" in flags.lower()
                forced = forced or "f" in flags.lower()
                continue
            targets.append(argument)

        if not (recursive and forced):
            continue
        for target in targets:
            normalized = normalized_delete_target(target)
            if normalized in {os.path.normpath(os.sep), os.sep * 2}:
                return "recursive deletion of the filesystem root"
            if normalized == home:
                return "recursive deletion of the current user's home directory"
    return None


def blocked_reason(command: str) -> str | None:
    rm_reason = recursive_forced_rm_reason(command)
    if rm_reason:
        return rm_reason
    for label, pattern in PATTERNS:
        if pattern.search(command):
            return label
    return None


def run_self_test() -> int:
    safe = [
        "rm -rf ./build",
        "git reset --hard HEAD",
        "git push --force-with-lease",
        "dd if=/dev/zero of=./disk.img bs=1M count=1",
        "Remove-Item -Recurse -Force .\\build",
        "Get-ChildItem C:\\",
        "printf '%s' 'rm -rf /'",
    ]
    dangerous = [
        "rm -rf /",
        "sudo rm -fr /*",
        "rm -rf $HOME",
        "rm -r -f /",
        "rm --recursive --force /",
        "/bin/rm -rf /",
        "sudo -n rm -rf /",
        "sh -c 'rm -rf /'",
        "rm / -rf",
        "rm --no-preserve-root -rf /./",
        "rm -rf ${HOME}/.",
        "command rm --no-preserve-root -rf /",
        "rm -rf //",
        "builtin rm --no-preserve-root -rf /",
        "exec rm --no-preserve-root -rf /",
        "command sudo rm --no-preserve-root -rf /",
        "bash -lc 'rm --no-preserve-root -rf /'",
        "sh -xc 'rm --no-preserve-root -rf /'",
        "sudo env rm --no-preserve-root -rf /",
        "env -u HOME rm --no-preserve-root -rf /",
        "sudo mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/nvme0n1",
        "cat image > /dev/sdb",
        ":(){ :|:& };:",
        "format C: /q",
        "Remove-Item -Recurse -Force C:\\*",
        "Remove-Item C:\\* -Recurse -Force",
        "rd /s /q C:\\",
    ]
    failures: list[str] = []
    for command in safe:
        if blocked_reason(command):
            failures.append(f"false positive: {command}")
    for command in dangerous:
        if not blocked_reason(command):
            failures.append(f"missed dangerous command: {command}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"guard self-test passed ({len(safe)} safe, {len(dangerous)} blocked)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(
            "Blocked by AI Engineering PowerKit: invalid hook event JSON.",
            file=sys.stderr,
        )
        return 2

    command = extract_command(payload)
    if command is None or not command.strip():
        print(
            "Blocked by AI Engineering PowerKit: hook event contains no shell command.",
            file=sys.stderr,
        )
        return 2
    reason = blocked_reason(command)
    if reason:
        print(
            f"Blocked by AI Engineering PowerKit: {reason}. "
            "Run the operation manually only after reviewing the target and consequences.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

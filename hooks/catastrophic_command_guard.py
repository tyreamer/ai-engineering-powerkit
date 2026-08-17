#!/usr/bin/env python3
"""Block a very small set of clearly catastrophic shell commands.

The script reads a hook event JSON object from stdin. It is intentionally
conservative: team-specific policies such as force-push or git reset do not
belong in this shared guard.

Exit code 2 blocks a matching tool call in both Codex and Claude Code hook
flows. Safe or unrecognized inputs exit 0.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "recursive deletion of the filesystem root",
        re.compile(r"(?is)(?:^|[;&|]\s*)(?:sudo\s+)?rm\s+(?:-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\s+/(?:\s|$|\*)"),
    ),
    (
        "recursive deletion of the current user's home directory",
        re.compile(r"(?is)(?:^|[;&|]\s*)(?:sudo\s+)?rm\s+(?:-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\s+(?:~|\$HOME|\$\{HOME\})(?:\s|$|/\*)"),
    ),
    (
        "filesystem creation on a block device",
        re.compile(r"(?is)(?:^|[;&|]\s*)(?:sudo\s+)?mkfs(?:\.[a-z0-9_-]+)?\s+[^;&|]*?/dev/(?:sd|nvme|vd|xvd|disk)[a-z0-9]+"),
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
        re.compile(r"(?is)(?:remove-item|del|erase|rd|rmdir)\b[^\r\n]*\b(?:c:\\\\|c:/)(?:\*|\s|$)[^\r\n]*(?:-recurse|/s)[^\r\n]*(?:-force|/q)"),
    ),
    (
        "formatting the Windows system drive",
        re.compile(r"(?is)(?:^|[;&|]\s*)format(?:\.com)?\s+c:\s*(?:/|$)"),
    ),
)


def extract_command(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str):
            return command
    if isinstance(tool_input, str):
        return tool_input
    command = payload.get("command")
    return command if isinstance(command, str) else ""


def blocked_reason(command: str) -> str | None:
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
    ]
    dangerous = [
        "rm -rf /",
        "sudo rm -fr /*",
        "rm -rf $HOME",
        "sudo mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/nvme0n1",
        "cat image > /dev/sdb",
        ":(){ :|:& };:",
        "format C: /q",
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
        # Fail open on malformed hook data; the host should report hook errors.
        return 0

    command = extract_command(payload)
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

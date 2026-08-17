#!/usr/bin/env python3
"""Run repository-defined verification commands in order."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

LEVELS = ("static", "targeted", "broader", "runtime")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(".ai-powerkit/project.json"))
    parser.add_argument("--target", type=Path, default=Path("."))
    parser.add_argument("--levels", default="static,targeted")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--keep-going", action="store_true")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = target / config_path
    if not config_path.is_file():
        parser.error(f"config does not exist: {config_path}")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    verification = data.get("verification", {})
    requested = [item.strip() for item in args.levels.split(",") if item.strip()]
    unknown = sorted(set(requested) - set(LEVELS))
    if unknown:
        parser.error(f"unknown verification levels: {', '.join(unknown)}")

    failures = 0
    executed = 0
    for level in requested:
        commands = verification.get(level, [])
        if not isinstance(commands, list):
            parser.error(f"verification.{level} must be an array")
        for command in commands:
            if not isinstance(command, str) or not command.strip():
                parser.error(f"verification.{level} contains an invalid command")
            executed += 1
            print(f"\n[{level}] $ {command}", flush=True)
            started = time.monotonic()
            try:
                result = subprocess.run(
                    command,
                    cwd=target,
                    shell=True,
                    timeout=args.timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                failures += 1
                print(f"[{level}] timed out after {args.timeout}s", file=sys.stderr)
                if not args.keep_going:
                    return 1
                continue
            elapsed = time.monotonic() - started
            print(f"[{level}] exit={result.returncode} elapsed={elapsed:.1f}s")
            if result.returncode != 0:
                failures += 1
                if not args.keep_going:
                    return result.returncode or 1

    if executed == 0:
        print("No verification commands configured for the requested levels.")
        return 0
    if failures:
        print(f"Verification finished with {failures} failed command(s).", file=sys.stderr)
        return 1
    print(f"Verification passed: {executed} command(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

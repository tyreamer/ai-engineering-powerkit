#!/usr/bin/env python3
"""Run repository-defined verification commands in order."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from powerkit.verification import run_verification, write_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(".ai-powerkit/project.json"))
    parser.add_argument("--target", type=Path, default=Path("."))
    parser.add_argument("--levels", default="static,targeted")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--evidence-out", type=Path)
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    config_path = args.config if args.config.is_absolute() else target / args.config
    try:
        evidence, returncode = run_verification(
            target,
            config_path,
            [item.strip() for item in args.levels.split(",") if item.strip()],
            timeout=args.timeout,
            keep_going=args.keep_going,
            allow_empty=args.allow_empty,
        )
        if args.evidence_out:
            path = args.evidence_out if args.evidence_out.is_absolute() else target / args.evidence_out
            write_evidence(path, evidence)
    except RuntimeError as exc:
        parser.error(str(exc))
    summary = evidence["summary"]
    if summary["executed"] == 0:
        print("No verification commands configured for the requested levels.")
    elif summary["failed"]:
        print(f"Verification finished with {summary['failed']} failed command(s).", file=sys.stderr)
    else:
        print(f"Verification passed: {summary['executed']} command(s).")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())

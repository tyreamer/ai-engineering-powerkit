#!/usr/bin/env python3
"""Backward-compatible entry point for the PowerKit installer."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from powerkit.installer import (  # noqa: E402
    confined_manifest_path,
    main,
)


if __name__ == "__main__":
    exit_code = main()
    if exit_code == 0 and "--dry-run" not in sys.argv:
        import subprocess
        print("Installing PowerKit package into the Python environment...", file=sys.stderr)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--user", str(ROOT)],
                stdout=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as exc:
            print(f"Warning: Failed to install Python package: {exc}", file=sys.stderr)
    raise SystemExit(exit_code)
